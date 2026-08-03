"""
SharePoint integration — Microsoft Graph API via urllib (no SDK required).

To activate:
  1. Register an Azure app (App Registration) with Sites.ReadWrite.All permission.
  2. Grant admin consent in Azure AD.
  3. Save tenant_id, client_id, client_secret, and site_url via POST /api/sharepoint/config.
"""

from __future__ import annotations
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
_CONFIG_FILE = DATA_DIR / "config.json"

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_TOKEN_URL_TMPL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


def _load_sp_config() -> dict:
    if not _CONFIG_FILE.exists():
        return {}
    try:
        cfg = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        return cfg.get("sharepoint", {})
    except Exception:
        return {}


def is_configured() -> bool:
    cfg = _load_sp_config()
    return all(cfg.get(k) for k in ("site_url", "tenant_id", "client_id", "client_secret"))


def _get_token(cfg: dict) -> str:
    """Obtain an OAuth2 client-credentials access token from Azure AD."""
    token_url = _TOKEN_URL_TMPL.format(tenant_id=cfg["tenant_id"])
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "scope": "https://graph.microsoft.com/.default",
    }).encode()
    req = urllib.request.Request(token_url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=15) as resp:
        token_data = json.loads(resp.read().decode())
    access_token = token_data.get("access_token")
    if not access_token:
        raise RuntimeError(f"Token request failed: {token_data.get('error_description', token_data)}")
    return access_token


def _graph_get(token: str, path: str) -> dict:
    """Make an authenticated GET request to MS Graph."""
    url = f"{_GRAPH_BASE}{path}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def _resolve_site_id(cfg: dict, token: str) -> str:
    """
    Resolve the Graph site ID from a SharePoint site URL.
    e.g. https://tenant.sharepoint.com/sites/FinTechCoP
         → tenant.sharepoint.com:/sites/FinTechCoP
    """
    site_url = cfg["site_url"].rstrip("/")
    parsed = urllib.parse.urlparse(site_url)
    hostname = parsed.hostname  # e.g. tenant.sharepoint.com
    path = parsed.path           # e.g. /sites/FinTechCoP
    result = _graph_get(token, f"/sites/{hostname}:{path}")
    return result["id"]


def test_connection() -> dict:
    cfg = _load_sp_config()
    if not is_configured():
        return {"ok": False, "message": "SharePoint not configured — add credentials in Settings.", "site_url": None}
    try:
        token = _get_token(cfg)
        site_id = _resolve_site_id(cfg, token)
        site_data = _graph_get(token, f"/sites/{site_id}")
        return {
            "ok": True,
            "message": f"Connected to {site_data.get('displayName', cfg['site_url'])}",
            "site_url": cfg["site_url"],
            "site_id": site_id,
        }
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return {"ok": False, "message": f"Graph API error {e.code}: {body[:200]}", "site_url": cfg.get("site_url")}
    except Exception as exc:
        return {"ok": False, "message": str(exc), "site_url": cfg.get("site_url")}


def list_documents(library: str = "Documents") -> dict:
    """
    List files in the SharePoint document library.
    Returns {"ok": bool, "documents": [...], "message": str}
    """
    cfg = _load_sp_config()
    if not is_configured():
        return {"ok": False, "documents": [], "message": "SharePoint not configured."}
    try:
        token = _get_token(cfg)
        site_id = _resolve_site_id(cfg, token)
        # List children of the root drive
        data = _graph_get(token, f"/sites/{site_id}/drive/root/children")
        docs = []
        for item in data.get("value", []):
            if item.get("file"):  # skip folders
                docs.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "webUrl": item.get("webUrl"),
                    "size": item.get("size"),
                    "lastModified": item.get("lastModifiedDateTime"),
                    "mimeType": item.get("file", {}).get("mimeType"),
                })
        return {"ok": True, "documents": docs, "count": len(docs), "message": f"Found {len(docs)} documents."}
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return {"ok": False, "documents": [], "message": f"Graph API error {e.code}: {body[:200]}"}
    except Exception as exc:
        return {"ok": False, "documents": [], "message": str(exc)}


def sync_asset(asset: dict) -> str | None:
    """Upload/update a single asset to SharePoint. Returns the document URL or None."""
    if not is_configured():
        return None
    # Placeholder for file upload — requires actual file bytes
    return None


def sync_all_assets(assets: list[dict]) -> dict:
    """Bulk-sync all assets to SharePoint."""
    if not is_configured():
        return {"synced": 0, "failed": 0, "errors": ["SharePoint not configured"]}
    return {"synced": 0, "failed": 0, "errors": ["File upload requires local file paths — link sync only."]}


def get_document_url(object_id: str, object_type: str) -> str | None:
    return None
