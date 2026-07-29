"""
Authentication, user management, and audit logging for the CoP Manager.

Pure stdlib — no external dependencies required.

Roles (lowest -> highest):  viewer | editor | admin
- viewer : read-only access to all data; can use the AI agent
- editor : all viewer access + create/update/delete data records
- admin  : all editor access + user management + audit log

Environment variables:
  COP_SECRET_KEY      — JWT signing secret (REQUIRED in production)
  COP_ALLOWED_DOMAIN  — e.g. "accenture.com" to restrict registration to one email domain
"""

from __future__ import annotations
import base64
import hashlib
import hmac as _hmac
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ── Config ────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "users.db"
SECRET_KEY = os.environ.get("COP_SECRET_KEY", "cop-dev-secret-CHANGE-IN-PRODUCTION")
TOKEN_TTL_HOURS = int(os.environ.get("COP_TOKEN_TTL_HOURS", "72"))
ALLOWED_DOMAIN = os.environ.get("COP_ALLOWED_DOMAIN", "").lower().strip()

ROLE_RANKS: dict[str, int] = {"viewer": 0, "editor": 1, "admin": 2}
VALID_ROLES = set(ROLE_RANKS)
VALID_AREAS = {"integrations", "conversion", "reporting", "extend", ""}

# ── JWT ───────────────────────────────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    rem = len(s) % 4
    if rem:
        s += "=" * (4 - rem)
    return base64.urlsafe_b64decode(s)


def create_token(payload: dict) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body_data = {
        **payload,
        "exp": int(time.time()) + TOKEN_TTL_HOURS * 3600,
        "iat": int(time.time()),
    }
    body = _b64url(json.dumps(body_data).encode())
    msg = f"{header}.{body}".encode()
    sig = _b64url(_hmac.new(SECRET_KEY.encode(), msg, hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"


def verify_token(token: str) -> dict:
    try:
        header, body, sig = token.strip().split(".")
        msg = f"{header}.{body}".encode()
        expected = _b64url(_hmac.new(SECRET_KEY.encode(), msg, hashlib.sha256).digest())
        if not _hmac.compare_digest(sig, expected):
            raise ValueError("Invalid signature")
        payload = json.loads(_b64url_decode(body))
        if payload.get("exp", 0) < time.time():
            raise ValueError("Token expired — please log in again")
        return payload
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Malformed token: {e}") from e


# ── Password hashing (PBKDF2-HMAC-SHA256, 260 000 iterations) ────────────────

def hash_password(password: str) -> str:
    salt = os.urandom(32).hex()
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000).hex()
    return f"{salt}:{h}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":", 1)
        new_h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000).hex()
        return _hmac.compare_digest(h, new_h)
    except Exception:
        return False


# ── SQLite ────────────────────────────────────────────────────────────────────

def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with _db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id           TEXT PRIMARY KEY,
                email        TEXT UNIQUE NOT NULL,
                name         TEXT NOT NULL,
                role         TEXT NOT NULL DEFAULT 'viewer',
                focus_area   TEXT NOT NULL DEFAULT '',
                password_hash TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                last_login   TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                ts             TEXT NOT NULL,
                user_email     TEXT NOT NULL,
                user_name      TEXT NOT NULL,
                action         TEXT NOT NULL,
                resource_type  TEXT NOT NULL,
                resource_id    TEXT NOT NULL DEFAULT '',
                resource_title TEXT NOT NULL DEFAULT '',
                detail         TEXT NOT NULL DEFAULT ''
            );
        """)


# ── User operations ───────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _user_count() -> int:
    with _db() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def get_user_by_email(email: str) -> dict | None:
    with _db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict | None:
    with _db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_all_users() -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT id,email,name,role,focus_area,created_at,last_login FROM users ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]


def create_user(
    email: str, name: str, password: str, role: str = "viewer", focus_area: str = ""
) -> dict:
    email = email.lower().strip()
    if ALLOWED_DOMAIN and not email.endswith(f"@{ALLOWED_DOMAIN}"):
        raise ValueError(f"Registration is restricted to @{ALLOWED_DOMAIN} addresses")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if get_user_by_email(email):
        raise ValueError("An account with that email already exists")
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}")

    # First user always becomes admin
    if _user_count() == 0:
        role = "admin"

    uid = str(uuid.uuid4())
    with _db() as conn:
        conn.execute(
            "INSERT INTO users (id,email,name,role,focus_area,password_hash,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (uid, email, name, role, focus_area, hash_password(password), _now()),
        )
    return {"id": uid, "email": email, "name": name, "role": role, "focus_area": focus_area}


def update_user(user_id: str, role: str, focus_area: str = "") -> dict | None:
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}")
    with _db() as conn:
        conn.execute(
            "UPDATE users SET role=?, focus_area=? WHERE id=?",
            (role, focus_area, user_id),
        )
        row = conn.execute(
            "SELECT id,email,name,role,focus_area,created_at,last_login FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def delete_user(user_id: str) -> bool:
    with _db() as conn:
        return conn.execute("DELETE FROM users WHERE id=?", (user_id,)).rowcount > 0


def touch_login(email: str) -> None:
    with _db() as conn:
        conn.execute("UPDATE users SET last_login=? WHERE email=?", (_now(), email.lower()))


# ── Audit log ─────────────────────────────────────────────────────────────────

def audit(
    user: dict,
    action: str,
    resource_type: str,
    resource_id: str = "",
    resource_title: str = "",
    detail: str = "",
) -> None:
    try:
        with _db() as conn:
            conn.execute(
                "INSERT INTO audit_log "
                "(ts,user_email,user_name,action,resource_type,resource_id,resource_title,detail) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    _now(),
                    user.get("email", ""),
                    user.get("name", ""),
                    action,
                    resource_type,
                    resource_id,
                    resource_title,
                    detail,
                ),
            )
    except Exception:
        pass  # Audit failures must never break the main operation


def get_audit_log(limit: int = 200) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── FastAPI dependencies ───────────────────────────────────────────────────────

_security = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_security),
) -> dict:
    if not creds:
        raise HTTPException(401, "Authentication required — please log in")
    try:
        return verify_token(creds.credentials)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc


async def require_editor(user: dict = Depends(get_current_user)) -> dict:
    if ROLE_RANKS.get(user.get("role", ""), -1) < ROLE_RANKS["editor"]:
        raise HTTPException(403, "Editor or Admin role required to modify data")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin role required")
    return user
