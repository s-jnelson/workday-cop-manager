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
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse
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


def _get_live_groq_key() -> str:
    """Read Groq API key from config file first, then env var."""
    cfg = _load_config()
    key = cfg.get("groq_api_key", "")
    if not key:
        key = os.environ.get("GROQ_API_KEY", "")
    return key if key.startswith("gsk_") and len(key) > 20 else ""


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
async def get_consultants(
    focus_area: str = "all",
    skill: str = "",
    availability: str = "",
    certification: str = "",
    include_deprecated: bool = False,
):
    data = _load("consultants.json") or []
    if not include_deprecated:
        data = [c for c in data if c.get("status", "active") != "deprecated"]
    if focus_area != "all":
        data = [c for c in data if c.get("focus_area") == focus_area]
    if skill:
        data = [c for c in data if any(
            skill.lower() in s.get("name", "").lower() for s in c.get("skills", [])
        ) or any(skill.lower() in m.lower() for m in c.get("modules", []))]
    if availability:
        data = [c for c in data if c.get("availability") == availability]
    if certification:
        data = [c for c in data if any(
            certification.lower() in cert.lower() for cert in c.get("certifications", [])
        )]
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
    skills: list[dict] = []          # [{name, level}] — level 1-5
    industries: list[str] = []
    availability: str = "staffed"    # "available" | "rolling-off" | "staffed"
    email: str = ""
    enterprise_id: str = ""
    project_assignments: list[dict] = []
    ai_use_case_ids: list[str] = []
    initiative_ids: list[str] = []


@app.post("/api/consultants")
async def create_consultant(body: ConsultantBody):
    data = _load("consultants.json") or []
    new_c = {"id": str(_uuid.uuid4()), "updated_by": "", **body.model_dump()}
    data.append(new_c)
    _save("consultants.json", data)
    return new_c


@app.put("/api/consultants/{consultant_id}")
async def update_consultant(consultant_id: str, body: ConsultantBody):
    import datetime
    data = _load("consultants.json") or []
    for i, c in enumerate(data):
        if c.get("id") == consultant_id or c.get("name") == consultant_id:
            # Merge: preserve governance fields not in ConsultantBody
            merged = {k: v for k, v in c.items() if k not in body.model_dump()}
            merged.update({"id": c.get("id", consultant_id), "updatedAt": datetime.datetime.now().isoformat()})
            merged.update(body.model_dump())
            data[i] = merged
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
async def get_assets(
    focus_area: str = "all",
    status: str = "all",
    asset_kind: str = "all",
    pillar: str = "all",
    include_deprecated: bool = False,
):
    data = _load("assets.json") or []
    if not include_deprecated:
        data = [a for a in data if a.get("status", "active") != "deprecated"]
    if focus_area != "all":
        data = [a for a in data if a.get("focus_area") == focus_area]
    if status != "all":
        data = [a for a in data if a.get("status") == status]
    if asset_kind != "all":
        data = [a for a in data if a.get("asset_kind") == asset_kind]
    if pillar != "all":
        data = [a for a in data if a.get("pillar") == pillar]
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
    asset_kind: str = "template"      # template | playbook | toolkit | accelerator | reference
    sourceUrl: str = ""               # canonical location (link, don't copy)
    relatedMethodologyIds: list[str] = []   # phase keys: plan|build|test|deploy|stabilize
    relatedInitiativeIds: list[str] = []
    reuseCount: int = 0
    contributed_by: str = ""          # contributor name/email for contribution flow
    needs_review: bool = False        # True = submitted via contribution flow, not yet reviewed


@app.post("/api/assets")
async def create_asset(body: AssetBody):
    data = _load("assets.json") or []
    new_a = {"id": str(_uuid.uuid4()), "updated_by": "", **body.model_dump()}
    data.append(new_a)
    _save("assets.json", data)
    return new_a


@app.put("/api/assets/{asset_id}")
async def update_asset(asset_id: str, body: AssetBody):
    import datetime
    data = _load("assets.json") or []
    for i, a in enumerate(data):
        if a.get("id") == asset_id or a.get("name") == asset_id:
            # Merge: preserve governance fields not in AssetBody
            merged = {k: v for k, v in a.items() if k not in body.model_dump()}
            merged.update({"id": a.get("id", asset_id), "updatedAt": datetime.datetime.now().isoformat()})
            merged.update(body.model_dump())
            data[i] = merged
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
async def get_ai_use_cases(
    status: str = "all",
    stage: str = "all",
    focus_area: str = "all",
    include_deprecated: bool = False,
):
    data = _load("ai_use_cases.json") or []
    if not include_deprecated:
        data = [uc for uc in data if uc.get("status", "active") != "deprecated"]
    if status != "all":
        data = [uc for uc in data if uc.get("status") == status]
    if stage != "all":
        data = [uc for uc in data if uc.get("stage") == stage]
    if focus_area != "all":
        data = [uc for uc in data if uc.get("focus_area") == focus_area]
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
    history: list[dict] = []  # [{role: "user"|"assistant", content: "..."}]


@app.post("/api/agent/query")
async def query_agent(body: AgentQuery):
    """Send a query to the appropriate agent. Returns AgentAnswer with citations."""
    from agents.base_agent import _get_anthropic_key, _get_groq_key, _get_ollama_model, BaseAgent

    query_id = str(_uuid.uuid4())
    has_key = bool(_get_anthropic_key())
    has_groq = bool(_get_groq_key())
    has_ollama = bool(_get_ollama_model())

    # Only fall back to rule-based when no LLM backend is available at all
    if not has_key and not has_groq and not has_ollama:
        from agents.rule_based_agent import query as rule_query
        response = rule_query(body.query)
        _save_gap(body.query, [])
        return {
            "response": response,
            "answer": response,
            "citations": [],
            "unanswered": True,
            "query_id": query_id,
            "agent_used": "rule_based",
            "mode": "offline",
        }

    try:
        # Fresh orchestrator per request — prevents history leaking between users
        cop = CoPOrchestrator(api_key=_get_live_anthropic_key())
        force = None if body.agent == "auto" else body.agent
        history = body.history or []
        loop = asyncio.get_event_loop()
        raw_response = await loop.run_in_executor(
            _PROC_POOL,
            lambda: cop.run(body.query, force_agent=force, history=history, verbose=False),
        )

        # Extract structured citation block appended by the LLM
        answer, citations, unanswered = BaseAgent.extract_citations(raw_response)

        # Log content gap when agent couldn't find a grounded answer
        if unanswered:
            closest = [c.get("title", "") for c in citations if c.get("title")]
            _save_gap(body.query, closest)

        backend = "anthropic" if has_key else ("groq" if has_groq else "ollama")
        return {
            "response": answer,       # backward-compat key
            "answer": answer,
            "citations": citations,
            "unanswered": unanswered,
            "query_id": query_id,
            "agent_used": body.agent,
            "backend": backend,
        }
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

    # Solutions that need an AI API — accept Anthropic or Groq
    if sol.get("requires_api") and not _get_live_anthropic_key() and not _get_live_groq_key():
        async def no_key():
            yield f"⚠  {sol['description']} requires an AI API key.\n\n"
            yield "Add one in Settings:\n"
            yield "  • Groq (free): https://console.groq.com  — keys start with gsk_\n"
            yield "  • Anthropic Claude: https://console.anthropic.com  — keys start with sk-ant-\n\n"
            yield "After saving a key in Settings, reload this page and try again.\n"
        return StreamingResponse(no_key(), media_type="text/plain; charset=utf-8")

    stdin_text: str | None = sol.get("stdin_text")

    def _run_script() -> tuple[str, int]:
        """Run the solution script synchronously in a thread (Windows-safe)."""
        cmd = [sys.executable, str(script)] + list(sol["args"])
        # Build env with API keys injected so scripts can use whichever is available
        script_env = os.environ.copy()
        live_anthro = _get_live_anthropic_key()
        live_groq = _get_live_groq_key()
        if live_anthro:
            script_env["ANTHROPIC_API_KEY"] = live_anthro
        if live_groq:
            script_env["GROQ_API_KEY"] = live_groq
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if stdin_text else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(SOLUTIONS_DIR),
            env=script_env,
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


# ── Taxonomy ──────────────────────────────────────────────────────────────────

@app.get("/api/taxonomy")
async def get_taxonomy():
    """Return the controlled vocabulary for all CoP object fields."""
    tax_file = DATA_DIR / "taxonomy.json"
    if not tax_file.exists():
        raise HTTPException(404, "taxonomy.json not found — run data/init_data.py")
    return json.loads(tax_file.read_text(encoding="utf-8"))


# ── Governance ────────────────────────────────────────────────────────────────

def _all_objects() -> list[dict]:
    """Collect every content object from all data files into a flat list."""
    objects: list[dict] = []
    for fname, otype in [("assets.json", "asset"), ("consultants.json", "person"),
                         ("initiatives.json", "initiative"), ("ai_use_cases.json", "aiUseCase")]:
        records = _load(fname) or []
        for r in records:
            r.setdefault("object_type", otype)
            objects.append(r)
    goals_data = _load("goals.json") or {}
    for g in goals_data.get("practice_goals", []):
        g.setdefault("object_type", "goal")
        objects.append(g)
    for area, goals in goals_data.get("subagent_goals", {}).items():
        for g in goals:
            g.setdefault("object_type", "goal")
            objects.append(g)
    return objects


@app.get("/api/governance/review-due")
async def governance_review_due():
    """Return all active objects whose reviewBy date has passed."""
    import datetime
    today = datetime.date.today().isoformat()
    overdue = []
    for obj in _all_objects():
        if obj.get("status") == "deprecated":
            continue
        review_by = obj.get("reviewBy", "")
        if review_by and review_by < today:
            overdue.append({
                "id": obj.get("id"),
                "title": obj.get("title") or obj.get("name", ""),
                "object_type": obj.get("object_type"),
                "owner": obj.get("owner"),
                "reviewBy": review_by,
                "days_overdue": (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(review_by)).days,
            })
    overdue.sort(key=lambda x: x["days_overdue"], reverse=True)
    return {"count": len(overdue), "items": overdue}


@app.get("/api/governance/deprecated")
async def governance_deprecated():
    """Return all deprecated objects (excluded from default views)."""
    items = [obj for obj in _all_objects() if obj.get("status") == "deprecated"]
    return {"count": len(items), "items": items}


class DeprecateBody(BaseModel):
    reason: str = ""


@app.post("/api/governance/deprecate/{object_type}/{object_id}")
async def deprecate_object(object_type: str, object_id: str, body: DeprecateBody):
    """Mark an object as deprecated. Removes it from default views and agent context."""
    import datetime
    file_map = {
        "asset": "assets.json",
        "person": "consultants.json",
        "initiative": "initiatives.json",
        "aiUseCase": "ai_use_cases.json",
    }
    fname = file_map.get(object_type)
    if not fname:
        raise HTTPException(400, f"Cannot deprecate object_type '{object_type}'. Valid: {list(file_map)}")
    data = _load(fname) or []
    for i, obj in enumerate(data):
        if obj.get("id") == object_id:
            data[i]["status"] = "deprecated"
            data[i]["deprecatedAt"] = datetime.datetime.now().isoformat()
            if body.reason:
                data[i]["deprecationReason"] = body.reason
            _save(fname, data)
            return {"deprecated": True, "id": object_id, "object_type": object_type}
    raise HTTPException(404, f"{object_type} '{object_id}' not found")


@app.post("/api/governance/restore/{object_type}/{object_id}")
async def restore_object(object_type: str, object_id: str):
    """Restore a deprecated object back to active status."""
    file_map = {
        "asset": "assets.json",
        "person": "consultants.json",
        "initiative": "initiatives.json",
        "aiUseCase": "ai_use_cases.json",
    }
    fname = file_map.get(object_type)
    if not fname:
        raise HTTPException(400, f"Cannot restore object_type '{object_type}'")
    data = _load(fname) or []
    for i, obj in enumerate(data):
        if obj.get("id") == object_id:
            data[i]["status"] = "active"
            data[i].pop("deprecatedAt", None)
            data[i].pop("deprecationReason", None)
            _save(fname, data)
            return {"restored": True, "id": object_id}
    raise HTTPException(404, f"{object_type} '{object_id}' not found")


# ── Content gaps (Agent "not found" log) ─────────────────────────────────────

GAPS_FILE = DATA_DIR / "content_gaps.json"
FEEDBACK_FILE = DATA_DIR / "agent_feedback.json"
STRATEGY_DOCS_FILE = DATA_DIR / "strategy_docs.json"
REUSE_FILE = DATA_DIR / "asset_reuse_events.json"
MEMORY_FILE = DATA_DIR / "agent_memory.json"
METHODOLOGY_FILE = Path(__file__).parent.parent / "methodology" / "deployment_methodology.json"


def _load_gaps() -> list:
    if not GAPS_FILE.exists():
        return []
    try:
        return json.loads(GAPS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_gap(query: str, closest_matches: list[str]) -> None:
    import datetime
    gaps = _load_gaps()
    gaps.append({
        "id": str(_uuid.uuid4()),
        "query": query,
        "timestamp": datetime.datetime.now().isoformat(),
        "closest_matches": closest_matches,
        "resolved": False,
    })
    with _write_lock:
        GAPS_FILE.write_text(json.dumps(gaps, indent=2), encoding="utf-8")


@app.get("/api/governance/gaps")
async def get_content_gaps(resolved: bool = False):
    """Return logged content gaps from Agent queries that found no grounded answer."""
    gaps = _load_gaps()
    if not resolved:
        gaps = [g for g in gaps if not g.get("resolved", False)]
    return {"count": len(gaps), "items": gaps}


@app.post("/api/governance/gaps/{gap_id}/resolve")
async def resolve_gap(gap_id: str):
    """Mark a content gap as resolved."""
    gaps = _load_gaps()
    for g in gaps:
        if g.get("id") == gap_id:
            g["resolved"] = True
            with _write_lock:
                GAPS_FILE.write_text(json.dumps(gaps, indent=2), encoding="utf-8")
            return {"resolved": True}
    raise HTTPException(404, "Gap not found")


# ── SharePoint integration config ─────────────────────────────────────────────

class SharePointConfigBody(BaseModel):
    site_url: str | None = None
    tenant_id: str | None = None
    client_id: str | None = None
    client_secret: str | None = None


@app.get("/api/sharepoint/status")
async def sharepoint_status():
    """Return SharePoint connection status."""
    from api.integrations.sharepoint import is_configured, test_connection
    configured = is_configured()
    if not configured:
        cfg = _load_config().get("sharepoint", {})
        return {
            "configured": False,
            "site_url": cfg.get("site_url", ""),
            "message": "Add SharePoint credentials in Settings to enable document sync.",
        }
    result = await asyncio.get_event_loop().run_in_executor(_PROC_POOL, test_connection)
    return {"configured": True, **result}


@app.post("/api/sharepoint/config")
async def save_sharepoint_config(body: SharePointConfigBody):
    """Save SharePoint connection settings (stored in config.json, gitignored)."""
    import datetime
    cfg = _load_config()
    sp = cfg.get("sharepoint", {})
    for field in ["site_url", "tenant_id", "client_id", "client_secret"]:
        val = getattr(body, field)
        if val is not None:
            stripped = val.strip()
            if stripped:
                sp[field] = stripped
            else:
                sp.pop(field, None)
    cfg["sharepoint"] = sp
    cfg["updated_at"] = datetime.datetime.now().isoformat()
    _save_config(cfg)
    return {"saved": True, "configured": all(sp.get(k) for k in ("site_url", "tenant_id", "client_id", "client_secret"))}


# ── Agent feedback ────────────────────────────────────────────────────────────

class FeedbackBody(BaseModel):
    query_id: str
    query: str
    answer: str
    rating: str  # "up" | "down"


@app.post("/api/agent/feedback")
async def submit_feedback(body: FeedbackBody):
    """Save a thumbs-up or thumbs-down rating for an agent answer."""
    import datetime
    if body.rating not in ("up", "down"):
        raise HTTPException(400, "rating must be 'up' or 'down'")
    feedback: list = []
    if FEEDBACK_FILE.exists():
        try:
            feedback = json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
        except Exception:
            feedback = []
    feedback.append({
        "id": str(_uuid.uuid4()),
        "query_id": body.query_id,
        "query": body.query,
        "answer": body.answer[:500],
        "rating": body.rating,
        "timestamp": datetime.datetime.now().isoformat(),
    })
    with _write_lock:
        FEEDBACK_FILE.write_text(json.dumps(feedback, indent=2), encoding="utf-8")
    return {"saved": True}


@app.get("/api/agent/feedback")
async def get_feedback():
    """Return recent agent feedback with up/down counts."""
    feedback: list = []
    if FEEDBACK_FILE.exists():
        try:
            feedback = json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    up = sum(1 for f in feedback if f.get("rating") == "up")
    down = sum(1 for f in feedback if f.get("rating") == "down")
    return {"count": len(feedback), "up": up, "down": down, "items": feedback[-50:]}


# ── Agent memory (cross-session Q&A history) ──────────────────────────────────

class MemoryBody(BaseModel):
    query_id: str
    query: str
    answer: str
    citations: list[dict] = []


def _load_memory() -> list:
    if not MEMORY_FILE.exists():
        return []
    try:
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


@app.get("/api/agent/memory")
async def get_memory(limit: int = 20):
    """Return recent agent Q&A pairs for context injection."""
    entries = _load_memory()
    return {"count": len(entries), "items": entries[-limit:]}


@app.post("/api/agent/memory")
async def save_memory(body: MemoryBody):
    """Persist a Q&A exchange so the agent can reference it in future sessions."""
    import datetime
    entries = _load_memory()
    entries.append({
        "id": str(_uuid.uuid4()),
        "query_id": body.query_id,
        "query": body.query,
        "answer": body.answer[:800],
        "citations": body.citations[:5],
        "timestamp": datetime.datetime.now().isoformat(),
    })
    # Rolling window — keep last 50 entries
    entries = entries[-50:]
    with _write_lock:
        MEMORY_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return {"saved": True, "total": len(entries)}


# ── Strategy documents ────────────────────────────────────────────────────────

class StrategyDocBody(BaseModel):
    title: str
    description: str = ""
    pillar: str = ""
    status: str = "active"
    owner: str | dict = "CoP Manager"
    sourceUrl: str = ""
    summary: str = ""
    visibility: str = "internal"
    linkedInitiativeIds: list[str] = []
    tags: list[str] = []


def _load_strategy_docs() -> list:
    if not STRATEGY_DOCS_FILE.exists():
        return []
    try:
        return json.loads(STRATEGY_DOCS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


@app.get("/api/strategy-docs")
async def get_strategy_docs(status: str = "all"):
    docs = _load_strategy_docs()
    if status != "all":
        docs = [d for d in docs if d.get("status") == status]
    return docs


@app.post("/api/strategy-docs")
async def create_strategy_doc(body: StrategyDocBody):
    import datetime
    docs = _load_strategy_docs()
    now = datetime.datetime.now().isoformat()
    review_by = (datetime.date.today().replace(year=datetime.date.today().year + 1)).isoformat()
    doc = {
        "id": str(_uuid.uuid4()),
        "object_type": "strategyDoc",
        "createdAt": now,
        "updatedAt": now,
        "reviewBy": review_by,
        **body.model_dump(),
    }
    docs.append(doc)
    with _write_lock:
        STRATEGY_DOCS_FILE.write_text(json.dumps(docs, indent=2), encoding="utf-8")
    return doc


@app.put("/api/strategy-docs/{doc_id}")
async def update_strategy_doc(doc_id: str, body: StrategyDocBody):
    import datetime
    docs = _load_strategy_docs()
    for i, d in enumerate(docs):
        if d.get("id") == doc_id:
            docs[i] = {**d, "updatedAt": datetime.datetime.now().isoformat(), **body.model_dump()}
            with _write_lock:
                STRATEGY_DOCS_FILE.write_text(json.dumps(docs, indent=2), encoding="utf-8")
            return docs[i]
    raise HTTPException(404, "Strategy doc not found")


@app.delete("/api/strategy-docs/{doc_id}")
async def delete_strategy_doc(doc_id: str):
    docs = _load_strategy_docs()
    filtered = [d for d in docs if d.get("id") != doc_id]
    if len(filtered) == len(docs):
        raise HTTPException(404, "Strategy doc not found")
    with _write_lock:
        STRATEGY_DOCS_FILE.write_text(json.dumps(filtered, indent=2), encoding="utf-8")
    return {"deleted": doc_id}


# ── Asset reuse tracking ──────────────────────────────────────────────────────

class ReuseBody(BaseModel):
    engagement_ref: str = ""


@app.post("/api/assets/{asset_id}/reuse")
async def record_asset_reuse(asset_id: str, body: ReuseBody = ReuseBody()):
    """Increment reuseCount on an asset and log the usage event."""
    import datetime
    data = _load("assets.json") or []
    updated_asset = None
    for i, a in enumerate(data):
        if a.get("id") == asset_id:
            data[i]["reuseCount"] = data[i].get("reuseCount", 0) + 1
            data[i]["deployments"] = data[i]["reuseCount"]
            data[i]["updatedAt"] = datetime.datetime.now().isoformat()
            updated_asset = data[i]
            break
    if not updated_asset:
        raise HTTPException(404, f"Asset {asset_id} not found")
    _save("assets.json", data)

    events: list = []
    if REUSE_FILE.exists():
        try:
            events = json.loads(REUSE_FILE.read_text(encoding="utf-8"))
        except Exception:
            events = []
    events.append({
        "id": str(_uuid.uuid4()),
        "assetId": asset_id,
        "assetName": updated_asset.get("name", ""),
        "engagementRef": body.engagement_ref,
        "timestamp": datetime.datetime.now().isoformat(),
    })
    with _write_lock:
        REUSE_FILE.write_text(json.dumps(events, indent=2), encoding="utf-8")

    return {"recorded": True, "asset_id": asset_id, "reuse_count": updated_asset["reuseCount"]}


@app.get("/api/assets/{asset_id}/reuse")
async def get_asset_reuse(asset_id: str):
    """Return reuse events for a specific asset."""
    events: list = []
    if REUSE_FILE.exists():
        try:
            events = json.loads(REUSE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"asset_id": asset_id, "events": [e for e in events if e.get("assetId") == asset_id]}


# ── Methodology phases ────────────────────────────────────────────────────────

@app.get("/api/methodology/phases")
async def get_methodology_phases():
    """Return methodology phases from JSON, dynamically linking matching assets."""
    if not METHODOLOGY_FILE.exists():
        raise HTTPException(404, "methodology/deployment_methodology.json not found")
    try:
        method_data = json.loads(METHODOLOGY_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(500, f"Could not read methodology file: {exc}")

    assets = [a for a in (_load("assets.json") or []) if a.get("status") != "deprecated"]

    # Default phase→asset-type mapping for assets with no explicit relatedMethodologyIds
    _default_phase_types: dict[str, list[str]] = {
        "plan":      ["standards_document", "document_template"],
        "build":     ["integration_template", "conversion_template", "report_package",
                      "extend_application", "tooling", "analytics_model"],
        "test":      [],
        "deploy":    [],
        "stabilize": [],
    }

    phases = method_data.get("phases", [])
    for phase in phases:
        key = phase.get("key", "")
        # Explicit links take priority
        explicit = [a for a in assets if key in (a.get("relatedMethodologyIds") or [])]
        # Fallback: match by default type mapping if no explicit links for this phase
        default_types = _default_phase_types.get(key, [])
        fallback = [a for a in assets if a.get("type") in default_types and key not in (a.get("relatedMethodologyIds") or []) and a not in explicit]
        linked = explicit + fallback[:6]  # cap fallback at 6 to avoid noise
        phase["linked_assets"] = [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "asset_kind": a.get("asset_kind", a.get("type", "")),
                "focus_area": a.get("focus_area"),
                "status": a.get("status"),
                "sourceUrl": a.get("sourceUrl", ""),
            }
            for a in linked
        ]

    return method_data


# ── SharePoint document sync ──────────────────────────────────────────────────

@app.get("/api/sharepoint/documents")
async def list_sharepoint_documents():
    """List documents from the configured SharePoint library via MS Graph."""
    from api.integrations.sharepoint import is_configured, list_documents
    if not is_configured():
        raise HTTPException(400, "SharePoint not configured — add credentials in Settings.")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_PROC_POOL, list_documents)
    return result


@app.post("/api/sharepoint/sync")
async def sync_sharepoint():
    """
    Pull documents from SharePoint and match them against CoP assets.
    Updates sourceUrl on matched assets and returns a summary.
    """
    from api.integrations.sharepoint import is_configured, list_documents
    if not is_configured():
        raise HTTPException(400, "SharePoint not configured.")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_PROC_POOL, list_documents)
    if not result.get("ok"):
        raise HTTPException(502, result.get("message", "SharePoint error"))

    docs = result.get("documents", [])
    assets = _load("assets.json") or []
    matched = 0
    for doc in docs:
        doc_name_lower = doc.get("name", "").lower().rsplit(".", 1)[0]
        for asset in assets:
            if asset.get("sourceUrl"):
                continue  # already linked — don't overwrite
            asset_name_lower = asset.get("name", "").lower()
            if doc_name_lower and (doc_name_lower in asset_name_lower or asset_name_lower in doc_name_lower):
                asset["sourceUrl"] = doc.get("webUrl", "")
                matched += 1
                break
    if matched:
        _save("assets.json", assets)
    return {"ok": True, "documents_found": len(docs), "assets_linked": matched}


# ── Staffing Roster endpoints ──────────────────────────────────────────────────

class StaffingManualBody(BaseModel):
    specialties: str = ""
    interests: str = ""
    notes: str = ""
    role_type: list[str] = []        # ["Technical", "Functional"]
    capabilities: list[str] = []     # ["Data", "Integrations", "Reporting", ...]


@app.post("/api/staffing/import")
async def import_staffing(file: UploadFile = File(...)):
    """
    Accept an S&D Excel report upload, process WBG Supply + Assignments tabs,
    and update staffing_roster.json. Manual fields in staffing_manual.json
    are never touched.
    """
    from api.staffing import process_sd_report
    content = await file.read()
    try:
        result = process_sd_report(content)
        return result
    except Exception as exc:
        import traceback
        raise HTTPException(status_code=400, detail=f"Failed to process file: {exc}\n{traceback.format_exc()}")


@app.get("/api/staffing/roster")
async def get_staffing_roster():
    """Return the staffing roster merged with manual fields."""
    from api.staffing import get_merged_roster
    return get_merged_roster()


@app.post("/api/staffing/manual/{personnel_number}")
async def update_staffing_manual(personnel_number: str, body: StaffingManualBody):
    """
    Update the protected manual fields for one worker.
    These fields survive every S&D re-import unchanged.
    """
    from api.staffing import update_manual
    result = update_manual(personnel_number, body.model_dump())
    return result


@app.get("/api/staffing/report")
async def get_staffing_report(
    fmt: str = "json",
    name: str = "",
    entity_l3: str = "",
    client: str = "",
    role_type: str = "",
    capabilities: str = "",
    min_pct: float = 0,
    max_pct: float = 500,
    in_supply_only: bool = False,
):
    """
    Return filtered staffing data. fmt=csv returns a downloadable CSV.
    """
    from api.staffing import get_report_data
    data = get_report_data(
        name=name, entity_l3=entity_l3, client=client,
        role_type=role_type, capabilities=capabilities,
        min_pct=min_pct, max_pct=max_pct, in_supply_only=in_supply_only,
    )

    if fmt == "csv":
        import csv, io as _io
        buf = _io.StringIO()
        fields = [
            "name", "personnel_number", "email", "entity_l3", "job_profile",
            "level_group", "management_level", "metro_city", "country",
            "current_client", "current_project", "current_start", "current_end",
            "current_pct", "total_pct",
            "role_type", "capabilities", "specialties", "interests", "notes",
            "in_assignments", "in_supply", "staffable_status", "last_import",
        ]
        w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in data:
            row = dict(r)
            row["role_type"] = ", ".join(r.get("role_type") or [])
            row["capabilities"] = ", ".join(r.get("capabilities") or [])
            w.writerow(row)
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="staffing_report.csv"'},
        )

    return data
