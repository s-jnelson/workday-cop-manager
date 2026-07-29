"""
Rule-based fallback agent for the Workday Finance Tech CoP Manager.

Answers common questions directly from the local JSON data files without
any LLM API calls. Used automatically when ANTHROPIC_API_KEY is not set.
"""

from __future__ import annotations
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def _load(filename: str) -> dict | list:
    path = DATA_DIR / filename
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _match(query: str, *keywords: str) -> bool:
    q = query.lower()
    return any(kw in q for kw in keywords)


# ── Response formatters ────────────────────────────────────────────────────────

def _practice_summary() -> str:
    m = _load("metrics.json")
    ps = m.get("practice_summary", {})
    dm = m.get("deployment_metrics", {})
    qm = m.get("quality_metrics", {})
    fh = m.get("focus_area_health", {})

    lines = [
        "PRACTICE HEALTH SUMMARY",
        f"  Team:               {ps.get('total_consultants', '?')} consultants",
        f"  Active projects:    {ps.get('active_projects', '?')}",
        f"  Methodology adopt.: {ps.get('methodology_adoption_pct', '?')}% (target 80%)",
        f"  Avg utilization:    {ps.get('avg_utilization_pct', '?')}%",
        f"  Assets published:   {ps.get('assets_published', '?')} ({ps.get('assets_in_progress', '?')} in progress)",
        "",
        "DEPLOYMENT METRICS",
        f"  Current avg timeline:  {dm.get('avg_deployment_weeks_current', '?')} weeks",
        f"  Baseline:              {dm.get('avg_deployment_weeks_baseline', '?')} weeks",
        f"  Reduction so far:      {dm.get('reduction_pct', '?')}% (target 20%)",
        f"  Cutover success rate:  {dm.get('cutover_success_rate_pct', '?')}%",
        "",
        "QUALITY",
        f"  Defect escape rate:    {qm.get('defect_escape_rate_pct', '?')}% (target {qm.get('target_defect_escape_pct', '?')}%)",
        f"  Client satisfaction:   {qm.get('avg_client_satisfaction', '?')}/10 (target {qm.get('target_client_satisfaction', '?')})",
        "",
        "FOCUS AREA HEALTH",
    ]
    for area, data in fh.items():
        status = data.get("health", "?").upper()
        score = data.get("score", "?")
        risks = data.get("open_risks", 0)
        lines.append(f"  {area.capitalize():<16} {status:<10} Score: {score}  Open risks: {risks}")

    return "\n".join(lines)


def _consultants(query: str) -> str:
    people = _load("consultants.json")
    if not isinstance(people, list):
        return "No consultant data available."

    # Filter by focus area if mentioned
    area = None
    for fa in ("integrations", "conversion", "reporting", "extend"):
        if fa in query.lower():
            area = fa
            break

    if area:
        people = [p for p in people if p.get("focus_area") == area]
        header = f"{area.capitalize()} team ({len(people)} consultant{'s' if len(people) != 1 else ''}):"
    else:
        header = f"Full team roster ({len(people)} consultants):"

    lines = [header]
    for p in people:
        certs = ", ".join(p.get("certifications", []))
        mods = ", ".join(p.get("modules", []))
        lines.append(
            f"\n  {p['name']} — {p.get('level', '')} | {p.get('focus_area', '').capitalize()}"
            f"\n    Location:   {p.get('location', 'N/A')}"
            f"\n    Experience: {p.get('years_experience', '?')} years | Utilization: {p.get('utilization_pct', '?')}%"
            f"\n    Certs:      {certs or 'None listed'}"
            f"\n    Modules:    {mods or 'N/A'}"
        )
    return "\n".join(lines)


def _goals(query: str) -> str:
    data = _load("goals.json")
    sections = []

    for section_key, section_label in [
        ("practice_goals", "PRACTICE GOALS"),
        ("integrations_goals", "INTEGRATIONS GOALS"),
        ("conversion_goals", "CONVERSION GOALS"),
        ("reporting_goals", "REPORTING GOALS"),
        ("extend_goals", "EXTEND GOALS"),
    ]:
        goals = data.get(section_key, [])
        if not goals:
            continue
        # Filter by focus area if query is specific
        skip = False
        for fa in ("integrations", "conversion", "reporting", "extend"):
            if fa in query.lower() and fa not in section_key and section_key != "practice_goals":
                skip = True
                break
        if skip:
            continue

        block = [f"\n{section_label}"]
        for g in goals:
            cur = g.get("current_value", "?")
            tgt = g.get("target_value", "?")
            unit = g.get("unit", "")
            pct = round(cur / tgt * 100) if tgt and cur != "?" else "?"
            status = g.get("status", "?").replace("_", " ").upper()
            block.append(
                f"  [{status}] {g['title']}"
                f"\n    Progress: {cur}{unit} / {tgt}{unit} ({pct}%)"
                f"\n    Due: {g.get('due_date', 'N/A')} | Owner: {g.get('owner', 'N/A')}"
            )
        sections.append("\n".join(block))

    return "\n".join(sections) if sections else "No goal data available."


def _initiatives(query: str) -> str:
    items = _load("initiatives.json")
    if not isinstance(items, list):
        return "No initiative data available."

    lines = [f"ACTIVE INITIATIVES ({len(items)} total)\n"]
    for ini in items:
        status = ini.get("status", "?").upper()
        priority = ini.get("priority", "?").upper()
        prog = ini.get("progress_pct", None)
        prog_str = f" | {prog}% complete" if prog is not None else ""
        deliverables = ini.get("deliverables", [])
        lines.append(
            f"  [{priority}] {ini['title']}"
            f"\n    Status: {status}{prog_str}"
            f"\n    Owner: {ini.get('owner', 'N/A')} | Due: {ini.get('target_completion', 'N/A')}"
            f"\n    {ini.get('description', '')[:120]}..."
        )
        if deliverables:
            lines.append(f"    Deliverables: {', '.join(deliverables[:3])}" +
                         (f" (+{len(deliverables)-3} more)" if len(deliverables) > 3 else ""))
        lines.append("")
    return "\n".join(lines)


def _assets(query: str) -> str:
    items = _load("assets.json")
    if not isinstance(items, list):
        return "No asset data available."

    area = None
    for fa in ("integrations", "conversion", "reporting", "extend"):
        if fa in query.lower():
            area = fa
            break

    filtered = [a for a in items if not area or a.get("focus_area") == area]
    label = f"{area.capitalize()} assets" if area else "All assets"
    published = [a for a in filtered if a.get("status") == "published"]
    draft = [a for a in filtered if a.get("status") != "published"]

    lines = [f"{label} — {len(filtered)} total ({len(published)} published, {len(draft)} in draft)\n"]
    for a in filtered:
        deploys = a.get("deployments", 0)
        lines.append(
            f"  [{a.get('status', '?').upper()}] {a['name']}"
            f"\n    Type: {a.get('type', 'N/A')} | Format: {a.get('format', 'N/A')}"
            f"\n    Deployments: {deploys} | Version: {a.get('version', 'N/A')}"
            f"\n    {a.get('description', '')[:100]}..."
            f""
        )
    return "\n".join(lines)


def _ai_use_cases(query: str) -> str:
    items = _load("ai_use_cases.json")
    if not isinstance(items, list):
        return "No AI use case data available."

    area = None
    for fa in ("integrations", "conversion", "reporting", "extend"):
        if fa in query.lower():
            area = fa
            break

    filtered = [uc for uc in items if not area or uc.get("focus_area") == area]
    deployed = [uc for uc in filtered if uc.get("status") == "deployed"]
    in_dev = [uc for uc in filtered if uc.get("status") == "in_development"]

    lines = [
        f"AI USE CASES — {len(filtered)} total | {len(deployed)} deployed | {len(in_dev)} in development\n"
    ]
    for uc in filtered:
        status = uc.get("status", "?").replace("_", " ").upper()
        client = "CLIENT DEPLOYED" if uc.get("client_deployed") else ""
        rating = "★" * uc.get("readiness_rating", 0)
        roi = uc.get("estimated_roi", "")
        lines.append(
            f"  [{status}] {uc['title']} {client}"
            f"\n    Readiness: {rating} | Area: {uc.get('focus_area', '?').capitalize()}"
        )
        if roi:
            lines.append(f"    ROI: {roi}")
        lines.append(f"    {uc.get('description', '')[:100]}...")
        lines.append("")
    return "\n".join(lines)


def _deployment_metrics() -> str:
    m = _load("metrics.json")
    dm = m.get("deployment_metrics", {})
    trend = m.get("monthly_trend", [])

    lines = [
        "DEPLOYMENT PERFORMANCE",
        f"  Current avg deployment:  {dm.get('avg_deployment_weeks_current', '?')} weeks",
        f"  Baseline avg deployment: {dm.get('avg_deployment_weeks_baseline', '?')} weeks",
        f"  Reduction achieved:      {dm.get('reduction_pct', '?')}% (target: 20%)",
        f"  Projects on methodology: {dm.get('projects_on_methodology', '?')} / {dm.get('total_active_projects', '?')}",
        f"  Cutover success rate:    {dm.get('cutover_success_rate_pct', '?')}%",
        f"    ({dm.get('cutover_successes', '?')} successes out of {dm.get('cutover_attempts', '?')} attempts)",
        "",
        "MONTHLY TREND (methodology adoption %)",
    ]
    for t in trend[-4:]:
        lines.append(
            f"  {t['month']}:  adoption {t['methodology_adoption']}%  "
            f"reuse {t['asset_reuse']}%  satisfaction {t['client_satisfaction']}/10"
        )
    return "\n".join(lines)


def _help_text() -> str:
    return (
        "I'm the CoP Manager assistant running in offline mode (no LLM API required).\n"
        "I can answer questions about:\n\n"
        "  • Practice health & KPIs  — 'practice summary', 'how are we doing'\n"
        "  • Team / consultants      — 'who is on the team', 'integrations consultants'\n"
        "  • Goals & progress        — 'goals', 'targets', 'what are we trying to achieve'\n"
        "  • Active initiatives      — 'initiatives', 'what are we working on'\n"
        "  • Assets & accelerators   — 'assets', 'templates', 'what tools do we have'\n"
        "  • AI use cases            — 'AI use cases', 'automation initiatives'\n"
        "  • Deployment metrics      — 'deployment timeline', 'cutover success rate'\n\n"
        "Note: To enable full conversational AI, set ANTHROPIC_API_KEY in your environment."
    )


# ── Router ─────────────────────────────────────────────────────────────────────

def query(question: str) -> str:
    q = question.strip()
    if not q:
        return _help_text()

    if _match(q, "help", "what can you", "what do you know", "capabilities", "what can i ask"):
        return _help_text()

    if _match(q, "consultant", "team", "staff", "member", "who is", "who's on", "roster",
              "people", "headcount", "utilization"):
        return _consultants(q)

    if _match(q, "goal", "target", "objective", "kpi", "achieve", "progress toward"):
        return _goals(q)

    if _match(q, "initiative", "program", "what are we working", "current work",
              "accelerator program", "projects"):
        return _initiatives(q)

    if _match(q, "asset", "template", "library", "reusable", "accelerator", "tool kit",
              "what tools", "what do we have"):
        return _assets(q)

    if _match(q, "ai use case", "ai initiative", "automation", "machine learning",
              "artificial intelligence", "invoice", "anomaly", "classifier"):
        return _ai_use_cases(q)

    if _match(q, "deploy", "deployment", "timeline", "cutover", "go-live", "weeks",
              "how long", "schedule"):
        return _deployment_metrics()

    if _match(q, "metric", "health", "performance", "summary", "overall", "status",
              "how are we", "how is the", "quality", "satisfaction", "defect"):
        return _practice_summary()

    # Default: show practice summary with a note
    return (
        _practice_summary()
        + "\n\n—\nTip: Ask about 'team', 'goals', 'initiatives', 'assets', or 'AI use cases' for more detail."
    )
