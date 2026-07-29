"""
CoP Dashboard Server — serves static dashboard files and proxies AI calls.

Supports two backends (auto-detected, no restart needed between queries):
  1. Anthropic Claude — set ANTHROPIC_API_KEY in .env
  2. Ollama (local)  — install from ollama.ai, then: ollama pull llama3.2

Usage:
    python dashboard_server.py
    (or via .claude/launch.json "CoP Dashboard" entry)
"""
import http.server
import json
import mimetypes
import os
import socketserver
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PORT = int(os.environ.get("PORT", os.environ.get("DASHBOARD_PORT", "3030")))
DASHBOARD_DIR = Path(__file__).parent / "dashboard"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
API_SERVER_URL = os.environ.get("API_SERVER_URL", "http://localhost:8000")

# Paths handled locally — everything else under /api/ proxies to FastAPI
_LOCAL_API_PATHS = {"/api/status", "/api/search", "/api/claude"}


def _load_dotenv() -> None:
    """Load variables from .env file if not already in environment."""
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()


def _get_anthropic_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return key if key.startswith("sk-ant-") and len(key) > 20 else ""


def _get_ollama_model() -> str:
    """Return the best available Ollama model, or empty string if Ollama is not running."""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/tags",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
        models = [m["name"] for m in data.get("models", [])]
        if not models:
            return ""
        # Honour explicit env override
        preferred = os.environ.get("OLLAMA_MODEL", "")
        if preferred:
            match = next((m for m in models if m.startswith(preferred)), None)
            if match:
                return match
        # Prefer common capable models in priority order
        for pref in ["llama3.2", "llama3.1", "llama3", "mistral", "qwen2.5", "gemma2", "phi3"]:
            match = next((m for m in models if m.startswith(pref)), None)
            if match:
                return match
        return models[0]
    except Exception:
        return ""


def _web_search(query: str) -> list:
    """
    Search for relevant content.
    Step 1: DuckDuckGo Instant Answer API (good for general concepts).
    Step 2: Always supplement with curated Workday-specific resource links
            derived from query keywords — guarantees sources even when DDG
            returns nothing for specialist technical queries.
    """
    results: list = []
    q_lower = query.lower()

    # ── Step 1: DuckDuckGo Instant Answer ──────────────────────────────────
    try:
        encoded = urllib.parse.quote_plus(query)
        url = (
            f"https://api.duckduckgo.com/?q={encoded}"
            "&format=json&no_html=1&skip_disambig=1&t=CoPHub"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "CoPKnowledgeHub/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())

        if data.get("AbstractText") and data.get("AbstractURL"):
            results.append({
                "title": data.get("Heading") or query,
                "url": data["AbstractURL"],
                "snippet": data["AbstractText"][:500],
                "source": data.get("AbstractSource", "DuckDuckGo"),
            })

        for item in data.get("RelatedTopics", []):
            if not isinstance(item, dict):
                continue
            if item.get("FirstURL") and item.get("Text"):
                results.append({
                    "title": item["Text"][:80],
                    "url": item["FirstURL"],
                    "snippet": item["Text"][:350],
                    "source": "DuckDuckGo",
                })
            if len(results) >= 4:
                break

        for item in data.get("Results", []):
            if not isinstance(item, dict):
                continue
            if item.get("FirstURL") and item.get("Text"):
                results.append({
                    "title": item["Text"][:80],
                    "url": item["FirstURL"],
                    "snippet": item["Text"][:350],
                    "source": "DuckDuckGo",
                })
            if len(results) >= 4:
                break
    except Exception:
        pass  # non-fatal — fall through to curated links

    # ── Step 2: Curated Workday resource links (always included) ────────────
    curated: list = []

    if any(kw in q_lower for kw in ["studio", "xslt", "integration", "eib", "connector", "raas", "soap", "rest", "isu", "peci", "wmft"]):
        curated.append({
            "title": "Workday Studio & Integration — Workday Community",
            "url": "https://community.workday.com/articles/workday-studio",
            "snippet": "Official Studio integration guides covering XSLT, Java, EIB, Core Connectors, RaaS, REST/SOAP APIs, ISU security, and monitoring patterns.",
            "source": "Workday Community",
        })
        curated.append({
            "title": "Workday Integration Design Patterns — Workday Developer Docs",
            "url": "https://developer.workday.com/en-US/documentation/",
            "snippet": "Workday developer documentation for integration APIs, REST endpoints, and SOAP web services.",
            "source": "Workday Developer Portal",
        })

    if any(kw in q_lower for kw in ["report", "prism", "analytics", "dashboard", "matrix", "composite", "birt", "calculated field", "discovery"]):
        curated.append({
            "title": "Workday Report Design Guide — Workday Community",
            "url": "https://community.workday.com/articles/report-design",
            "snippet": "Custom Reports, Matrix Reports, Composite Reports, Prism Analytics, Discovery Boards, Calculated Fields, and BIRT reporting documentation.",
            "source": "Workday Community",
        })

    if any(kw in q_lower for kw in ["extend", "orchestration", "custom app", "business object", "validation", "related action"]):
        curated.append({
            "title": "Workday Extend Developer Documentation",
            "url": "https://developer.workday.com/en-US/documentation/workday-extend/",
            "snippet": "Official Workday Extend docs covering app design lifecycle, orchestrations, custom business objects, validation rules, and related actions.",
            "source": "Workday Developer Portal",
        })

    if any(kw in q_lower for kw in ["conversion", "iload", "migration", "cutover", "data load", "spreadsheet import", "mock"]):
        curated.append({
            "title": "Workday Data Conversion Methodology — Workday Community",
            "url": "https://community.workday.com/articles/data-conversion",
            "snippet": "Data conversion best practices: iLoad templates, spreadsheet import, object dependency ordering, mock conversion runs, cutover sequencing, and reconciliation.",
            "source": "Workday Community",
        })

    if any(kw in q_lower for kw in ["financial", "gl", "journal", "accounts payable", "accounts receivable", "procurement", "expense", "banking", "fixed asset", "revenue", "tax", "budget"]):
        curated.append({
            "title": "Workday Financial Management — Workday Community",
            "url": "https://community.workday.com/financial-management",
            "snippet": "Workday Financials resources covering GL, AP, AR, Fixed Assets, Expenses, Procurement, Banking, Revenue, Tax, and Financial Reporting.",
            "source": "Workday Community",
        })

    if any(kw in q_lower for kw in ["security", "domain", "role", "permission", "isu", "audit", "sod"]):
        curated.append({
            "title": "Workday Security — Roles, Domains & Policies",
            "url": "https://community.workday.com/articles/workday-security",
            "snippet": "Workday security configuration: domain security policies, security groups, role-based access, ISU setup, and audit trails.",
            "source": "Workday Community",
        })

    # Workday Community search always provided as a catch-all
    curated.append({
        "title": f"Search Workday Community: \"{query[:60]}\"",
        "url": f"https://community.workday.com/search?query={urllib.parse.quote_plus(query)}",
        "snippet": "Search Workday Community for official documentation, implementation guides, and peer discussions on this topic.",
        "source": "Workday Community",
    })

    # Merge: add curated links that aren't already in DDG results
    seen = {r["url"] for r in results}
    for item in curated:
        if item["url"] not in seen:
            results.append(item)
            seen.add(item["url"])
        if len(results) >= 6:
            break

    return results[:6]


def _detect_backend() -> tuple:
    """Return (backend, model) for the best available backend."""
    key = _get_anthropic_key()
    if key:
        return "anthropic", ANTHROPIC_MODEL
    model = _get_ollama_model()
    if model:
        return "ollama", model
    return "none", ""


class DashboardHandler(http.server.BaseHTTPRequestHandler):

    # ── helpers ──────────────────────────────────────────────────────────────

    def _send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── CORS preflight ────────────────────────────────────────────────────────

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    # ── Static file serving ───────────────────────────────────────────────────

    def do_GET(self) -> None:
        url_path = self.path.split("?")[0]

        # Proxy non-local /api/* requests to FastAPI
        if url_path.startswith("/api/") and url_path not in _LOCAL_API_PATHS:
            self._proxy_api()
            return

        if url_path == "/api/status":
            backend, model = _detect_backend()
            self._send_json(200, {
                "configured": backend != "none",
                "backend": backend,
                "model": model,
            })
            return

        if url_path == "/api/search":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            query = qs.get("q", [""])[0].strip()
            if not query:
                self._send_json(400, {"error": "Missing ?q= parameter"})
                return
            results = _web_search(query)
            self._send_json(200, {"results": results, "query": query})
            return

        if url_path == "/":
            url_path = "/index.html"

        # Resolve and guard against path-traversal
        try:
            target = (DASHBOARD_DIR / url_path.lstrip("/")).resolve()
            if not str(target).startswith(str(DASHBOARD_DIR.resolve())):
                self.send_response(403)
                self.end_headers()
                return
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        if target.exists() and target.is_file():
            data = target.read_bytes()
            mime, _ = mimetypes.guess_type(str(target))
            self.send_response(200)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    # ── AI proxy ──────────────────────────────────────────────────────────────

    def do_PUT(self) -> None:
        self._proxy_api()

    def do_DELETE(self) -> None:
        self._proxy_api()

    def do_POST(self) -> None:
        url_path = self.path.split("?")[0]

        # Proxy non-local /api/* requests to FastAPI
        if url_path.startswith("/api/") and url_path not in _LOCAL_API_PATHS:
            self._proxy_api()
            return

        if self.path != "/api/claude":
            self.send_response(404)
            self.end_headers()
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception as exc:
            self._send_json(400, {"error": f"Bad request body: {exc}"})
            return

        backend, model = _detect_backend()

        if backend == "anthropic":
            self._proxy_anthropic(body, model)
        elif backend == "ollama":
            self._proxy_ollama(body, model)
        else:
            self._send_json(503, {
                "error": (
                    "No AI backend available. "
                    "Option A: Install Ollama (ollama.ai) and run `ollama pull llama3.2`. "
                    "Option B: Add ANTHROPIC_API_KEY=sk-ant-… to .env and restart the server."
                )
            })

    def _proxy_anthropic(self, body: dict, model: str) -> None:
        api_key = _get_anthropic_key()
        payload = {
            "model": model,
            "max_tokens": min(int(body.get("max_tokens", 3000)), 8192),
            "system": body.get("system", ""),
            "messages": [{"role": "user", "content": body.get("user", "")}],
        }
        try:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                self._send_json(200, {"text": result["content"][0]["text"], "backend": "anthropic"})
        except urllib.error.HTTPError as exc:
            err = exc.read().decode("utf-8", errors="replace")
            self._send_json(exc.code, {"error": f"Anthropic API {exc.code}: {err[:300]}"})
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})

    def _proxy_ollama(self, body: dict, model: str) -> None:
        messages = []
        sys_prompt = body.get("system", "")
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})
        messages.append({"role": "user", "content": body.get("user", "")})

        # Ollama on CPU generates ~10-15 tokens/sec. Cap output to keep calls
        # within the 120-second window. Large max_tokens values (4000, 5000) would
        # take 5-8 minutes and always timeout.
        requested = int(body.get("max_tokens", 3000))
        num_predict = min(requested, 700)

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": num_predict,
                "temperature": 0.2,
            },
        }
        try:
            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"content-type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                text = result.get("message", {}).get("content", "")
                self._send_json(200, {"text": text, "backend": "ollama", "model": model})
        except Exception as exc:
            err = str(exc)
            if "timed out" in err.lower():
                self._send_json(504, {
                    "error": (
                        "Ollama timed out generating the response. "
                        "Try a shorter question, or add ANTHROPIC_API_KEY to .env for full-length responses."
                    )
                })
            else:
                self._send_json(500, {"error": f"Ollama error: {err}"})

    def _proxy_api(self) -> None:
        """Forward any /api/* request to the FastAPI server on port 8000."""
        target_url = API_SERVER_URL + self.path
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else None

            # Forward all headers except Host
            fwd_headers = {}
            for key, val in self.headers.items():
                if key.lower() not in ("host", "content-length"):
                    fwd_headers[key] = val
            if body:
                fwd_headers["Content-Length"] = str(len(body))

            req = urllib.request.Request(
                target_url,
                data=body,
                headers=fwd_headers,
                method=self.command,
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                self.send_response(resp.status)
                for key, val in resp.headers.items():
                    if key.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(key, val)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            self.send_response(exc.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        except Exception as exc:
            self._send_json(502, {"error": f"API proxy error: {exc}"})

    def log_message(self, fmt, *args):  # silence access log
        pass


class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def _start_api_server() -> None:
    """Start the FastAPI agent/data server on port 8000 as a background process."""
    import subprocess
    project_dir = Path(__file__).parent
    try:
        subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "api.server:app",
                "--host", "0.0.0.0",
                "--port", "8000",
                "--log-level", "warning",
            ],
            cwd=str(project_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("API server     ->  http://localhost:8000  (agents + data CRUD)")
    except Exception as exc:
        print(f"API server     ->  FAILED to start: {exc}")


def main() -> None:
    if not DASHBOARD_DIR.exists():
        print(f"ERROR: Dashboard directory not found: {DASHBOARD_DIR}", file=sys.stderr)
        sys.exit(1)

    backend, model = _detect_backend()
    print(f"CoP Dashboard  ->  http://localhost:{PORT}")
    if backend == "anthropic":
        print(f"AI backend     ->  Anthropic Claude ({model})")
    elif backend == "ollama":
        print(f"AI backend     ->  Ollama local ({model})")
    else:
        print("AI backend     ->  NOT CONFIGURED")
        print("                   Option A: Install Ollama (ollama.ai) + run `ollama pull llama3.2`")
        print("                   Option B: Set ANTHROPIC_API_KEY in .env and restart")

    _start_api_server()

    server = ThreadedServer(("", PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
