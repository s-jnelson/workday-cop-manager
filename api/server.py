"""
FastAPI backend — serves dashboard data and agent interaction endpoints.

Run: uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations
import asyncio
import json
import os
import subprocess
import sys
import threading
import uuid as _uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from orchestrator import CoPOrchestrator

_PROC_POOL = ThreadPoolExecutor(max_workers=20, thread_name_prefix="ai-runner")
_write_lock = threading.Lock()  # Serialise JSON file writes for concurrent access

DATA_DIR      = Path(__file__).parent.parent / "data"
DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard"
SOLUTIONS_DIR = Path(__file__).parent.parent / "assets" / "files" / "ai" / "solutions"
CONFIG_FILE   = DATA_DIR / "config.json"

# Demo-mode configuration for each AI solution (safe to run without client data)
SOLUTION_DEMO_MAP: dict[str, dict] = {
    "01": {
        "file": "01_invoice_exception_classifier.py",
        "args": ["--demo", "--no-ai"],
        "description": "AI Invoice Exception Classifier",
        "requires_api": False,
    },
    "02": {
        "file": "02_financial_anomaly_detector.py",
        "args": ["--demo", "--no-narrative"],
        "description": "Financial Anomaly Detector",
        "requires_api": False,
    },
    "03": {
        "file": "03_integration_error_diagnostics.py",
        "args": ["--stdin", "--no-ai"],
        "description": "Integration Error Diagnostics",
        "requires_api": False,
        # Sample Workday error piped to stdin
        "stdin_text": (
            "ERROR: Integration 'GL_Journal_Export' failed — "
            "ISU 'ISU_GL_Export' received HTTP 403 Forbidden from Workday. "
            "Domain security policy 'Get: Integration Events' is not assigned to this ISU. "
            "Additionally: XSLT transform failed at line 42 — "
            "element 'journal_entry' not declared in schema 'JournalEntry.xsd'."
        ),
    },
    "04": {
        "file": "04_nl_financial_query.py",
        "args": ["--demo"],
        "description": "Natural Language Financial Query",
        "requires_api": True,
    },
    "05": {
        "file": "05_supplier_risk_scorer.py",
        "args": ["--demo", "--no-ai"],
        "description": "Supplier Risk Scorer",
        "requires_api": False,
    },
    "06": {
        "file": "06_conversion_mapping_assistant.py",
        "args": ["--demo"],
        "description": "Conversion Data Mapping Assistant",
        "requires_api": True,
    },
    "07": {
        "file": "07_expense_policy_reviewer.py",
        "args": ["--demo", "--no-ai"],
        "description": "Expense Policy Reviewer",
        "requires_api": False,
    },
    "08": {
        "file": "08_address_banking_validator/launch_demo.py",
        "args": [],
        "description": "Workday Address & Banking Data Validator",
        "requires_api": False,
    },
}

app = FastAPI(
    title="Workday Finance Tech CoP Manager",
    description="Practice management API for the Workday Finance & Technical Community of Practice",
    version="2.0.0",
)


@app.on_event("startup")
async def _startup():
    pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount dashboard static files
if DASHBOARD_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="static")

def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config(data: dict) -> None:
    with _write_lock:
        CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _get_live_anthropic_key() -> str:
    """Read Anthropic API key from config file first, then env var."""
    cfg = _load_config()
    key = cfg.get("anthropic_api_key", "")
    if not key:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
    return key


def _load(filename: str):
    path = DATA_DIR / filename
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save(filename: str, data) -> None:
    with _write_lock:
        path = DATA_DIR / filename
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ── Focus area score computation ───────────────────────────────────────────────

_DECREASE_KEYWORDS = ("reduce", "below", "<", "less than", "cut", "defect")


def _goal_progress(goal: dict) -> float:
    """Return 0.0-1.0 completion fraction for a single goal."""
    status = goal.get("status", "in_progress")
    if status == "complete":
        return 1.0
    if status == "planning":
        return 0.05  # committed but not yet started
    target = float(goal.get("target_value") or 1)
    current = float(goal.get("current_value", 0))
    title = goal.get("title", "").lower()
    is_decrease = any(k in title for k in _DECREASE_KEYWORDS)
    if is_decrease:
        return 1.0 if current <= target else 0.0
    return min(current / target, 1.0) if target > 0 else 0.0


def _compute_focus_area_scores(goals: dict, consultants: list, existing_health: dict) -> dict:
    """
    Compute a 0-100 health score for each focus area from live data.

    Score = base(60)
          + goal_progress_pts  (0-20): avg completion across all area sub-goals
          + utilization_pts    (0-10): avg consultant utilization vs 80% optimal
          + milestone_pts      (0-10): completed goals / total goals
          - risk_deduction     (0-20): 5 pts per open risk, capped at 20
    Clamped to [40, 100].
    health: "good" >= 70 | "at_risk" >= 55 | "critical" < 55
    """
    AREAS = ["integrations", "conversion", "reporting", "extend"]
    subagent_goals = goals.get("subagent_goals", {})
    result = {}

    for area in AREAS:
        area_goals = subagent_goals.get(area, [])
        area_consultants = [c for c in consultants if c.get("focus_area") == area]
        open_risks = (existing_health.get(area) or {}).get("open_risks", 0)

        if area_goals:
            pcts = [_goal_progress(g) for g in area_goals]
            avg_pct = sum(pcts) / len(pcts)
            complete_count = sum(1 for g in area_goals if g.get("status") == "complete")
            total_goals = len(area_goals)
        else:
            avg_pct, complete_count, total_goals = 0.0, 0, 0

        goal_pts = round(avg_pct * 20, 1)
        milestone_pts = round((complete_count / max(total_goals, 1)) * 10, 1)

        if area_consultants:
            avg_util = sum(c.get("utilization_pct", 0) for c in area_consultants) / len(area_consultants)
        else:
            avg_util = 0.0
        util_pts = round(min(avg_util / 80.0, 1.0) * 10, 1)

        risk_penalty = min(open_risks * 5, 20)
        raw = 60 + goal_pts + util_pts + milestone_pts - risk_penalty
        score = max(40, min(100, round(raw)))
        health = "good" if score >= 70 else "at_risk" if score >= 55 else "critical"

        result[area] = {
            "score": score,
            "health": health,
            "open_risks": open_risks,
            "score_breakdown": {
                "base": 60,
                "goal_progress_pts": goal_pts,
                "utilization_pts": util_pts,
                "milestone_pts": milestone_pts,
                "risk_deduction": -risk_penalty,
                "avg_goal_pct": round(avg_pct * 100, 1),
                "avg_utilization_pct": round(avg_util, 1),
                "goals_complete": complete_count,
                "goals_total": total_goals,
            },
        }

    return result


# ── Dashboard entry point ──────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def serve_dashboard():
    index = DASHBOARD_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "Workday Finance Tech CoP Manager API — dashboard not found"}


# ── Data endpoints (no LLM calls) ─────────────────────────────────────────────

@app.get("/api/metrics")
async def get_metrics():
    data = _load("metrics.json")
    if data is None:
        raise HTTPException(404, "Run python data/init_data.py to initialize data stores")
    goals = _load("goals.json") or {}
    consultants = _load("consultants.json") or []
    data["focus_area_health"] = _compute_focus_area_scores(
        goals, consultants, data.get("focus_area_health", {})
    )
    return data


@app.get("/api/goals")
async def get_goals():
    data = _load("goals.json")
    if data is None:
        raise HTTPException(404, "Data not initialized")
    return data


@app.get("/api/initiatives")
async def get_initiatives(status: str = "all"):
    data = _load("initiatives.json") or []
    if status != "all":
        data = [i for i in data if i.get("status") == status]
    return data


class InitiativeBody(BaseModel):
    title: str
    description: str = ""
    type: str = "deployment_methodology"
    status: str = "planning"
    priority: str = "medium"
    owner: str = "CoP Manager"
    start_date: str = ""
    target_completion: str = ""
    focus_areas: list[str] = []
    deliverables: list[str] = []
    progress_pct: int = 0
    related_goals: list[str] = []
    related_consultants: list[str] = []
    related_assets: list[str] = []
    related_ai: list[str] = []
    notes: str = ""


@app.post("/api/initiatives")
async def create_initiative(body: InitiativeBody):
    data = _load("initiatives.json") or []
    new_item = {"id": str(_uuid.uuid4()), "created_by": "", "updated_by": "", **body.model_dump()}
    data.append(new_item)
    _save("initiatives.json", data)
    return new_item


@app.put("/api/initiatives/{init_id}")
async def update_initiative(init_id: str, body: InitiativeBody):
    data = _load("initiatives.json") or []
    for idx, item in enumerate(data):
        if item.get("id") == init_id:
            data[idx] = {"id": init_id, "created_by": item.get("created_by", ""), "updated_by": "", **body.model_dump()}
            _save("initiatives.json", data)
            return data[idx]
    raise HTTPException(404, "Initiative not found")


@app.delete("/api/initiatives/{init_id}")
async def delete_initiative(init_id: str):
    data = _load("initiatives.json") or []
    target = next((i for i in data if i.get("id") == init_id), None)
    data = [i for i in data if i.get("id") != init_id]
    _save("initiatives.json", data)
    return {"deleted": init_id}


@app.get("/api/consultants")
async def get_consultants(focus_area: str = "all"):
    data = _load("consultants.json") or []
    if focus_area != "all":
        data = [c for c in data if c.get("focus_area") == focus_area]
    return data


class ConsultantBody(BaseModel):
    name: str
    level: str = "Consultant"
    focus_area: str = "integrations"
    location: str = ""
    years_experience: int = 1
    utilization_pct: int = 0
    active_projects: int = 0
    modules: list[str] = []
    certifications: list[str] = []


@app.post("/api/consultants")
async def create_consultant(body: ConsultantBody):
    data = _load("consultants.json") or []
    new_c = {"id": str(_uuid.uuid4()), "updated_by": "", **body.model_dump()}
    data.append(new_c)
    _save("consultants.json", data)
    return new_c


@app.put("/api/consultants/{consultant_id}")
async def update_consultant(consultant_id: str, body: ConsultantBody):
    data = _load("consultants.json") or []
    for i, c in enumerate(data):
        if c.get("id") == consultant_id or c.get("name") == consultant_id:
            data[i] = {"id": c.get("id", consultant_id), "updated_by": "", **body.model_dump()}
            _save("consultants.json", data)
            return data[i]
    raise HTTPException(404, "Consultant not found")


@app.delete("/api/consultants/{consultant_id}")
async def delete_consultant(consultant_id: str):
    data = _load("consultants.json") or []
    target = next((c for c in data if c.get("id") == consultant_id or c.get("name") == consultant_id), None)
    filtered = [c for c in data if c.get("id") != consultant_id and c.get("name") != consultant_id]
    _save("consultants.json", filtered)
    return {"deleted": consultant_id}


@app.get("/api/assets")
async def get_assets(focus_area: str = "all", status: str = "all"):
    data = _load("assets.json") or []
    if focus_area != "all":
        data = [a for a in data if a.get("focus_area") == focus_area]
    if status != "all":
        data = [a for a in data if a.get("status") == status]
    return data


class AssetBody(BaseModel):
    name: str
    description: str = ""
    focus_area: str = "integrations"
    type: str = "document_template"
    format: str = ""
    status: str = "draft"
    version: str = "1.0"
    deployments: int = 0
    file_path: str | None = None
    file_note: str = ""
    tags: list[str] = []


@app.post("/api/assets")
async def create_asset(body: AssetBody):
    data = _load("assets.json") or []
    new_a = {"id": str(_uuid.uuid4()), "updated_by": "", **body.model_dump()}
    data.append(new_a)
    _save("assets.json", data)
    return new_a


@app.put("/api/assets/{asset_id}")
async def update_asset(asset_id: str, body: AssetBody):
    data = _load("assets.json") or []
    for i, a in enumerate(data):
        if a.get("id") == asset_id or a.get("name") == asset_id:
            data[i] = {"id": a.get("id", asset_id), "updated_by": "", **body.model_dump()}
            _save("assets.json", data)
            return data[i]
    raise HTTPException(404, "Asset not found")


@app.delete("/api/assets/{asset_id}")
async def delete_asset(asset_id: str):
    data = _load("assets.json") or []
    target = next((a for a in data if a.get("id") == asset_id or a.get("name") == asset_id), None)
    filtered = [a for a in data if a.get("id") != asset_id and a.get("name") != asset_id]
    _save("assets.json", filtered)
    return {"deleted": asset_id}


@app.get("/api/ai-use-cases")
async def get_ai_use_cases(status: str = "all"):
    data = _load("ai_use_cases.json") or []
    if status != "all":
        data = [uc for uc in data if uc.get("status") == status]
    return data


class AiUseCaseBody(BaseModel):
    title: str
    description: str = ""
    focus_area: str = "integrations"
    status: str = "planning"
    client_deployed: bool = False
    internal_use: bool = True
    estimated_roi: str = ""
    technology: list[str] = []
    file_path: str | None = None
    app_url: str | None = None
    guide_path: str | None = None
    sample_data_path: str | None = None
    readiness_rating: int | None = None
    readiness_notes: str = ""
    responsible_agent: str = ""
    clients: list[str] = []


@app.post("/api/ai-use-cases")
async def create_ai_use_case(body: AiUseCaseBody):
    data = _load("ai_use_cases.json") or []
    new_uc = {"id": str(_uuid.uuid4()), "updated_by": "", **body.model_dump()}
    data.append(new_uc)
    _save("ai_use_cases.json", data)
    return new_uc


@app.put("/api/ai-use-cases/{uc_id}")
async def update_ai_use_case(uc_id: str, body: AiUseCaseBody):
    data = _load("ai_use_cases.json") or []
    for i, uc in enumerate(data):
        if uc.get("id") == uc_id:
            data[i] = {"id": uc_id, "updated_by": "", **body.model_dump()}
            _save("ai_use_cases.json", data)
            return data[i]
    raise HTTPException(404, f"Use case {uc_id} not found")


@app.delete("/api/ai-use-cases/{uc_id}")
async def delete_ai_use_case(uc_id: str):
    data = _load("ai_use_cases.json") or []
    target = next((uc for uc in data if uc.get("id") == uc_id), None)
    filtered = [uc for uc in data if uc.get("id") != uc_id]
    if len(filtered) == len(data):
        raise HTTPException(404, f"Use case {uc_id} not found")
    _save("ai_use_cases.json", filtered)
    return {"deleted": uc_id}


# ── Goal CRUD endpoints ────────────────────────────────────────────────────────

class GoalBody(BaseModel):
    title: str
    description: str = ""
    target_value: float = 0
    current_value: float = 0
    unit: str = "percent"
    due_date: str = ""
    owner: str = ""
    status: str = "in_progress"
    kpi: str = ""
    sub_goals: list[str] = []
    success_criteria: list[str] = []
    composition: list[str] = []
    how_to_achieve: list[str] = []
    requirements: list[str] = []


def _goals_data():
    return _load("goals.json") or {"practice_goals": [], "subagent_goals": {}}


@app.post("/api/goals/practice")
async def add_practice_goal(body: GoalBody):
    data = _goals_data()
    new_goal = {"id": str(_uuid.uuid4()), "updated_by": "", **body.model_dump()}
    data.setdefault("practice_goals", []).append(new_goal)
    _save("goals.json", data)
    return new_goal


@app.put("/api/goals/practice/{goal_id}")
async def update_practice_goal(goal_id: str, body: GoalBody):
    data = _goals_data()
    goals = data.get("practice_goals", [])
    for i, g in enumerate(goals):
        if g.get("id") == goal_id:
            goals[i] = {"id": goal_id, "updated_by": "", **body.model_dump()}
            _save("goals.json", data)
            return goals[i]
    raise HTTPException(404, f"Goal {goal_id} not found")


@app.delete("/api/goals/practice/{goal_id}")
async def delete_practice_goal(goal_id: str):
    data = _goals_data()
    goals = data.get("practice_goals", [])
    target = next((g for g in goals if g.get("id") == goal_id), None)
    filtered = [g for g in goals if g.get("id") != goal_id]
    if len(filtered) == len(goals):
        raise HTTPException(404, f"Goal {goal_id} not found")
    data["practice_goals"] = filtered
    _save("goals.json", data)
    return {"deleted": goal_id}


@app.post("/api/goals/{area}")
async def add_area_goal(area: str, body: GoalBody):
    data = _goals_data()
    data.setdefault("subagent_goals", {}).setdefault(area, [])
    new_goal = {"id": str(_uuid.uuid4()), "updated_by": "", **body.model_dump()}
    data["subagent_goals"][area].append(new_goal)
    _save("goals.json", data)
    return new_goal


@app.put("/api/goals/{area}/{goal_id}")
async def update_area_goal(area: str, goal_id: str, body: GoalBody):
    data = _goals_data()
    goals = data.get("subagent_goals", {}).get(area, [])
    for i, g in enumerate(goals):
        if g.get("id") == goal_id:
            data["subagent_goals"][area][i] = {"id": goal_id, "updated_by": "", **body.model_dump()}
            _save("goals.json", data)
            return data["subagent_goals"][area][i]
    raise HTTPException(404, f"Goal {goal_id} not found in {area}")


@app.delete("/api/goals/{area}/{goal_id}")
async def delete_area_goal(area: str, goal_id: str):
    data = _goals_data()
    goals = data.get("subagent_goals", {}).get(area, [])
    target = next((g for g in goals if g.get("id") == goal_id), None)
    filtered = [g for g in goals if g.get("id") != goal_id]
    if len(filtered) == len(goals):
        raise HTTPException(404, f"Goal {goal_id} not found in {area}")
    data["subagent_goals"][area] = filtered
    _save("goals.json", data)
    return {"deleted": goal_id}


@app.get("/api/dashboard")
async def get_dashboard_data():
    """All dashboard data in one call to minimize round trips."""
    metrics = _load("metrics.json")
    goals = _load("goals.json") or {}
    consultants = _load("consultants.json") or []
    if metrics:
        metrics["focus_area_health"] = _compute_focus_area_scores(
            goals, consultants, metrics.get("focus_area_health", {})
        )
    return {
        "metrics": metrics,
        "goals": goals,
        "initiatives": _load("initiatives.json"),
        "consultants": consultants,
        "assets": _load("assets.json"),
        "ai_use_cases": _load("ai_use_cases.json"),
    }


# ── Agent interaction endpoints ────────────────────────────────────────────────

class AgentQuery(BaseModel):
    query: str
    agent: str = "auto"  # auto | main | integrations | conversion | reporting | extend


@app.post("/api/agent/query")
async def query_agent(body: AgentQuery):
    """Send a query to the appropriate agent and get a response."""
    from agents.base_agent import _get_anthropic_key, _get_ollama_model

    has_key = bool(_get_anthropic_key())
    has_ollama = bool(_get_ollama_model())

    # Only fall back to rule-based when neither LLM backend is available
    if not has_key and not has_ollama:
        from agents.rule_based_agent import query as rule_query
        response = rule_query(body.query)
        return {"response": response, "agent_used": "rule_based", "mode": "offline"}

    try:
        # Create a fresh orchestrator per request — prevents conversation history
        # from leaking between concurrent users sharing the same agent instance.
        cop = CoPOrchestrator(api_key=_get_live_anthropic_key())
        force = None if body.agent == "auto" else body.agent
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            _PROC_POOL,
            lambda: cop.run(body.query, force_agent=force, verbose=False),
        )
        from agents.base_agent import _get_groq_key
        if has_key:
            backend = "anthropic"
        elif _get_groq_key():
            backend = "groq"
        else:
            backend = "ollama"
        return {"response": response, "agent_used": body.agent, "backend": backend}
    except Exception as e:
        raise HTTPException(500, f"Agent error: {str(e)}")


@app.post("/api/agent/status-reports")
async def collect_status_reports():
    """Trigger all sub-agents to generate status reports."""
    try:
        cop = CoPOrchestrator(api_key=_get_live_anthropic_key())
        reports = cop.collect_all_status_reports(verbose=False)
        return {"reports": reports}
    except Exception as e:
        raise HTTPException(500, f"Status report error: {str(e)}")


# ── AI Solution Runner ────────────────────────────────────────────────────────

@app.post("/api/ai/run/{solution_id}")
async def run_ai_solution(solution_id: str):
    """Stream demo output from an AI solution script."""
    sol = SOLUTION_DEMO_MAP.get(solution_id)
    if not sol:
        raise HTTPException(404, f"Solution '{solution_id}' not in map. Valid: {list(SOLUTION_DEMO_MAP)}")

    script = SOLUTIONS_DIR / sol["file"]
    if not script.exists():
        raise HTTPException(404, f"Script file not found: {sol['file']}")

    # Solutions that need Claude API — check for key
    if sol.get("requires_api") and not _get_live_anthropic_key():
        async def no_key():
            yield f"⚠  {sol['description']} requires ANTHROPIC_API_KEY\n\n"
            yield "Steps to enable:\n"
            yield "  1. Get a key at https://console.anthropic.com\n"
            yield "  2. export ANTHROPIC_API_KEY='sk-ant-...'\n"
            yield "  3. Restart: python main.py --serve\n\n"
            yield "You can still ⬇ download the script and run it locally once the key is set.\n"
        return StreamingResponse(no_key(), media_type="text/plain; charset=utf-8")

    stdin_text: str | None = sol.get("stdin_text")

    def _run_script() -> tuple[str, int]:
        """Run the solution script synchronously in a thread (Windows-safe)."""
        cmd = [sys.executable, str(script)] + list(sol["args"])
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if stdin_text else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(SOLUTIONS_DIR),
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            if stdin_text:
                stdout, _ = proc.communicate(input=stdin_text, timeout=120)
            else:
                stdout, _ = proc.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return "\n\n─── TIMEOUT: script exceeded 120 s ───\n", -1
        return stdout, proc.returncode

    async def stream():
        loop = asyncio.get_event_loop()
        try:
            output, rc = await loop.run_in_executor(_PROC_POOL, _run_script)
            yield output
            yield f"\n\n─── Exit code: {rc} ───\n"
        except Exception as exc:
            yield f"\n\n─── ERROR: {type(exc).__name__}: {exc} ───\n"

    return StreamingResponse(stream(), media_type="text/plain; charset=utf-8")


# ── Config / API-key management ───────────────────────────────────────────────

class ConfigBody(BaseModel):
    anthropic_api_key: str | None = None
    groq_api_key: str | None = None
    render_api_key: str | None = None


def _mask(key: str) -> str:
    if not key or len(key) < 12:
        return ""
    return key[:8] + "…" + key[-4:]


@app.get("/api/config")
async def get_config():
    cfg = _load_config()
    anthro = cfg.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
    groq   = cfg.get("groq_api_key")      or os.environ.get("GROQ_API_KEY", "")
    render = cfg.get("render_api_key")    or os.environ.get("RENDER_API_KEY", "")
    return {
        "anthropic_api_key_set": bool(anthro),
        "anthropic_api_key_preview": _mask(anthro),
        "groq_api_key_set": bool(groq),
        "groq_api_key_preview": _mask(groq),
        "render_api_key_set": bool(render),
        "render_api_key_preview": _mask(render),
    }


@app.post("/api/config")
async def save_config(body: ConfigBody):
    import datetime
    cfg = _load_config()
    for field, env_name in [("anthropic_api_key", "ANTHROPIC_API_KEY"), ("groq_api_key", "GROQ_API_KEY"), ("render_api_key", "RENDER_API_KEY")]:
        val = getattr(body, field)
        if val is not None:
            stripped = val.strip()
            if stripped:
                cfg[field] = stripped
                os.environ[env_name] = stripped  # apply immediately to running process
            else:
                cfg.pop(field, None)
    cfg["updated_at"] = datetime.datetime.now().isoformat()
    _save_config(cfg)

    # Fire-and-forget: push API keys to Render env vars for persistence across redeploys
    render_persisted = False
    try:
        loop = asyncio.get_event_loop()
        render_persisted = await loop.run_in_executor(_PROC_POOL, lambda: _push_to_render_env_vars(cfg))
    except Exception:
        pass

    return {"saved": True, "render_persisted": render_persisted}


def _get_render_key() -> str:
    cfg = _load_config()
    return cfg.get("render_api_key") or os.environ.get("RENDER_API_KEY", "")


def _push_to_render_env_vars(cfg: dict) -> bool:
    """Push API keys to Render service env vars so they survive redeploys. Returns True on success."""
    import urllib.request as _req
    render_key = cfg.get("render_api_key") or os.environ.get("RENDER_API_KEY", "")
    if not render_key:
        return False

    vars_to_push = {}
    if cfg.get("anthropic_api_key"):
        vars_to_push["ANTHROPIC_API_KEY"] = cfg["anthropic_api_key"]
    if cfg.get("groq_api_key"):
        vars_to_push["GROQ_API_KEY"] = cfg["groq_api_key"]
    if not vars_to_push:
        return False

    try:
        # Get service ID
        svc_req = _req.Request(
            "https://api.render.com/v1/services?limit=20",
            headers={"Authorization": f"Bearer {render_key}", "Accept": "application/json"},
        )
        with _req.urlopen(svc_req, timeout=10) as resp:
            services = json.loads(resp.read())
        svc = next(
            (s["service"] for s in services if "cop-manager" in s["service"].get("name", "").lower()),
            services[0]["service"] if services else None,
        )
        if not svc:
            return False
        svc_id = svc["id"]

        # Fetch current env vars to avoid wiping unrelated vars
        env_req = _req.Request(
            f"https://api.render.com/v1/services/{svc_id}/env-vars",
            headers={"Authorization": f"Bearer {render_key}", "Accept": "application/json"},
        )
        with _req.urlopen(env_req, timeout=10) as resp:
            current = json.loads(resp.read())
        env_map = {item["envVar"]["key"]: item["envVar"]["value"] for item in current if "envVar" in item}
        env_map.update(vars_to_push)

        put_body = json.dumps([{"key": k, "value": v} for k, v in env_map.items()]).encode()
        put_req = _req.Request(
            f"https://api.render.com/v1/services/{svc_id}/env-vars",
            data=put_body,
            headers={
                "Authorization": f"Bearer {render_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="PUT",
        )
        with _req.urlopen(put_req, timeout=10):
            pass
        return True
    except Exception:
        return False


@app.get("/api/render/status")
async def render_status():
    import urllib.request as _req
    key = _get_render_key()
    if not key:
        raise HTTPException(400, "Render API key not configured — add it in Settings")
    try:
        request = _req.Request(
            "https://api.render.com/v1/services?limit=10",
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        )
        with _req.urlopen(request, timeout=10) as resp:
            services = json.loads(resp.read())
        # Find a service matching our app name
        svc = next(
            (s["service"] for s in services if "cop-manager" in s["service"].get("name", "").lower()),
            services[0]["service"] if services else None,
        )
        if not svc:
            return {"found": False, "services": [s["service"]["name"] for s in services]}
        return {
            "found": True,
            "id": svc["id"],
            "name": svc["name"],
            "status": svc.get("suspended", "not_suspended"),
            "url": svc.get("serviceDetails", {}).get("url", ""),
            "updated_at": svc.get("updatedAt", ""),
        }
    except Exception as exc:
        raise HTTPException(502, f"Render API error: {exc}")


@app.post("/api/render/deploy")
async def render_deploy():
    import urllib.request as _req
    key = _get_render_key()
    if not key:
        raise HTTPException(400, "Render API key not configured — add it in Settings")
    try:
        # First get the service id
        request = _req.Request(
            "https://api.render.com/v1/services?limit=10",
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        )
        with _req.urlopen(request, timeout=10) as resp:
            services = json.loads(resp.read())
        svc = next(
            (s["service"] for s in services if "cop-manager" in s["service"].get("name", "").lower()),
            services[0]["service"] if services else None,
        )
        if not svc:
            raise HTTPException(404, "cop-manager service not found in Render account")
        svc_id = svc["id"]
        deploy_req = _req.Request(
            f"https://api.render.com/v1/services/{svc_id}/deploys",
            data=b"{}",
            headers={
                "Authorization": f"Bearer {key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with _req.urlopen(deploy_req, timeout=10) as resp:
            deploy = json.loads(resp.read())
        return {"triggered": True, "deploy_id": deploy.get("id"), "status": deploy.get("status")}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Render deploy error: {exc}")


# ── Status endpoint (used as Render health check) ─────────────────────────────

@app.get("/api/status")
async def status():
    return {"status": "ok", "service": "Workday Finance Tech CoP Manager"}


# ── Health & metadata ──────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Workday Finance Tech CoP Manager"}


@app.get("/api/focus-areas")
async def focus_areas():
    return {
        "focus_areas": [
            {"id": "integrations", "label": "Integrations", "description": "Studio, Core Connectors, EIB, RaaS, REST/SOAP APIs"},
            {"id": "conversion", "label": "Conversion & Methodology", "description": "iLoad, data migration, cutover planning, post-cutover reconciliation"},
            {"id": "reporting", "label": "Reporting & Report Design", "description": "Custom Reports, Matrix, Composite, Prism Analytics, Discovery Boards"},
            {"id": "extend", "label": "Workday Extend Solutions", "description": "App Design, Orchestrations, Custom BOs, AI-augmented Extend patterns"},
        ]
    }
