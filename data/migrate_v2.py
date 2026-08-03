#!/usr/bin/env python3
"""
migrate_v2.py — Non-destructive V2 governance migration for Workday CoP Manager data files.

Usage:  python migrate_v2.py

Idempotent: running multiple times produces the same result.
- Existing fields are NEVER overwritten (uses set-if-absent semantics).
- Status normalisation only fires on the original legacy values, so a
  second run finds normalised values and makes no changes.

Files processed (read + written in-place):
  data/consultants.json
  data/assets.json
  data/goals.json
  data/initiatives.json
  data/ai_use_cases.json
"""

import json
from pathlib import Path
from datetime import datetime, timezone

# ── Configuration ──────────────────────────────────────────────────────────────
DATA_DIR   = Path(__file__).parent
REVIEW_BY  = "2027-02-02"
CREATED_AT = "2026-01-01T00:00:00Z"
UPDATED_AT = "2026-08-02T00:00:00Z"
COP_OWNER  = {"id": "person_cop_manager", "name": "CoP Manager"}

FOCUS_AREA_TO_PILLAR: dict[str, str] = {
    "integrations": "Integrations",
    "conversion":   "Data & Conversion",
    "reporting":    "Reporting & Analytics",
    "extend":       "Extend",
}

ASSET_TYPE_TO_KIND: dict[str, str] = {
    "integration_template":  "template",
    "document_template":     "template",
    "conversion_template":   "template",
    "tooling":               "toolkit",
    "report_package":        "accelerator",
    "standards_document":    "playbook",
    "analytics_model":       "accelerator",
    "extend_application":    "accelerator",
}

# Status normalisation maps (legacy value → governed value).
# Only legacy values are listed — normalised values are not present in these
# maps, so a second run finds the new value, gets no match, and is a no-op.
ASSET_STATUS_MAP: dict[str, str] = {
    "published":   "active",
    "in_progress": "draft",
}
INITIATIVE_STATUS_MAP: dict[str, str] = {
    "planning": "draft",
    # "active" stays "active" — intentionally absent
}
AI_STATUS_MAP: dict[str, str] = {
    "deployed":       "active",
    "in_development": "active",
    "planning":       "draft",
}


# ── Generic helpers ────────────────────────────────────────────────────────────

def _set_if_absent(obj: dict, key: str, value: object) -> bool:
    """Set obj[key] = value only when the key does not already exist.
    Returns True when the field was actually added."""
    if key not in obj:
        obj[key] = value
        return True
    return False


def _pillar(focus_area: str) -> str:
    """Map a focus_area string to the matching pillar name."""
    return FOCUS_AREA_TO_PILLAR.get(focus_area, "Technical Strategy & Architecture")


def _summary(rec: dict) -> str:
    """Return the first 200 chars of description, or fall back to title/name."""
    text = rec.get("description") or rec.get("title") or rec.get("name") or ""
    return str(text)[:200]


def _tally(counter: dict[str, int], keys: list[str]) -> None:
    """Increment per-field counts in a running tally dict."""
    for k in keys:
        counter[k] = counter.get(k, 0) + 1


# ── Common governance fields ───────────────────────────────────────────────────

def _add_common(rec: dict, object_type: str) -> list[str]:
    """Add the seven governance fields shared by every record type.
    Returns the list of field names that were actually added."""
    added: list[str] = []
    for key, val in [
        ("object_type", object_type),
        ("reviewBy",    REVIEW_BY),
        ("visibility",  "org"),
        ("createdAt",   CREATED_AT),
        ("updatedAt",   UPDATED_AT),
        ("sourceUrl",   ""),
        ("summary",     _summary(rec)),
    ]:
        if _set_if_absent(rec, key, val):
            added.append(key)
    return added


# ── Per-type migration functions ───────────────────────────────────────────────

def migrate_consultant(rec: dict) -> list[str]:
    added = _add_common(rec, "person")

    fa   = rec.get("focus_area", "")
    util = rec.get("utilization_pct", 0)

    if util >= 85:
        availability = "staffed"
    elif util >= 70:
        availability = "rolling-off"
    else:
        availability = "available"

    for key, val in [
        ("pillar",       _pillar(fa)),
        ("tags",         [fa] if fa else []),
        ("owner",        {"id": rec["id"], "name": rec["name"]}),
        ("skills",       [{"name": m, "level": 3} for m in rec.get("modules", [])]),
        ("industries",   ["Financial Services"]),
        ("availability", availability),
    ]:
        if _set_if_absent(rec, key, val):
            added.append(key)

    return added


def migrate_asset(rec: dict) -> list[str]:
    added = _add_common(rec, "asset")

    fa   = rec.get("focus_area", "")
    kind = ASSET_TYPE_TO_KIND.get(rec.get("type", ""), "reference")

    for key, val in [
        ("pillar",                _pillar(fa)),
        # "tags" intentionally omitted — keep existing tags unchanged
        ("owner",                 COP_OWNER),
        ("asset_kind",            kind),
        ("reuseCount",            rec.get("deployments", 0)),
        ("relatedMethodologyIds", []),
        ("relatedInitiativeIds",  []),
    ]:
        if _set_if_absent(rec, key, val):
            added.append(key)

    # Normalise status (idempotent: only legacy values trigger a change)
    old_status = rec.get("status", "")
    new_status = ASSET_STATUS_MAP.get(old_status)
    if new_status is not None:
        rec["status"] = new_status
        added.append(f"status: {old_status!r}->{new_status!r}")

    return added


def migrate_goal(rec: dict, pillar: str, tags: list[str]) -> list[str]:
    added = _add_common(rec, "goal")

    for key, val in [
        ("pillar", pillar),
        ("tags",   [t for t in tags if t]),
    ]:
        if _set_if_absent(rec, key, val):
            added.append(key)

    # Convert plain-string owner to governed dict
    if isinstance(rec.get("owner"), str):
        rec["owner"] = COP_OWNER
        added.append("owner: str->dict")

    return added


def migrate_initiative(rec: dict) -> list[str]:
    added    = _add_common(rec, "initiative")
    first_fa = (rec.get("focus_areas") or [""])[0]
    status   = rec.get("status", "")
    progress = rec.get("progress_pct", 0)

    # Health: planning always "on-track"; otherwise driven by progress
    if status == "planning":
        health = "on-track"
    elif progress >= 60:
        health = "on-track"
    elif progress >= 30:
        health = "at-risk"
    else:
        health = "off-track"

    for key, val in [
        ("pillar",     _pillar(first_fa)),
        ("tags",       [t for t in [rec.get("type", ""), rec.get("priority", "")] if t]),
        ("health",     health),
        ("objective",  rec.get("title", "")),
        ("keyResults", [{"text": d, "progress": 0} for d in rec.get("deliverables", [])]),
    ]:
        if _set_if_absent(rec, key, val):
            added.append(key)

    # Convert plain-string owner to governed dict
    if isinstance(rec.get("owner"), str):
        rec["owner"] = COP_OWNER
        added.append("owner: str->dict")

    # Normalise status
    old_status = rec.get("status", "")
    new_status = INITIATIVE_STATUS_MAP.get(old_status)
    if new_status is not None:
        rec["status"] = new_status
        added.append(f"status: {old_status!r}->{new_status!r}")

    return added


def migrate_ai_use_case(rec: dict) -> list[str]:
    added  = _add_common(rec, "aiUseCase")
    fa     = rec.get("focus_area", "")
    status = rec.get("status", "")

    # Derive lifecycle stage from current status
    if status == "deployed":
        stage = "adopted"
    elif status == "in_development":
        stage = "piloting"
    elif status == "planning":
        stage = "validated"
    else:
        stage = "idea"

    # Data readiness from readiness_rating
    rr = rec.get("readiness_rating")
    if rr is None:
        data_readiness = "amber"
    elif rr >= 4:
        data_readiness = "green"
    elif rr >= 3:
        data_readiness = "amber"
    else:
        data_readiness = "red"

    pairs: list[tuple[str, object]] = [
        ("pillar",        _pillar(fa)),
        ("tags",          [fa] if fa else []),
        ("owner",         COP_OWNER),
        ("stage",         stage),
        ("dataReadiness", data_readiness),
    ]
    if "estimated_roi" in rec:
        pairs.append(("expectedValue", rec["estimated_roi"]))

    for key, val in pairs:
        if _set_if_absent(rec, key, val):
            added.append(key)

    # Normalise status
    old_status = rec.get("status", "")
    new_status = AI_STATUS_MAP.get(old_status)
    if new_status is not None:
        rec["status"] = new_status
        added.append(f"status: {old_status!r}->{new_status!r}")

    return added


# ── File I/O ───────────────────────────────────────────────────────────────────

def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Report formatting ──────────────────────────────────────────────────────────

def _section(lines: list[str], filename: str, count: int,
             tally: dict[str, int]) -> None:
    lines.append(f"\n  {filename}  ({count} record(s))")
    lines.append("  " + "-" * 50)
    if tally:
        for field, n in sorted(tally.items()):
            lines.append(f"    + {field:<40} {n:>3} record(s)")
    else:
        lines.append("    (no changes — already up to date)")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    run_ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = [
        "=" * 68,
        "  Workday CoP Manager — V2 Governance Migration Report",
        f"  Run at: {run_ts}",
        "=" * 68,
    ]

    # ── consultants.json ──────────────────────────────────────────────────────
    consultants: list[dict] = _load(DATA_DIR / "consultants.json")
    tally: dict[str, int] = {}
    for rec in consultants:
        _tally(tally, migrate_consultant(rec))
    _save(DATA_DIR / "consultants.json", consultants)
    _section(lines, "consultants.json", len(consultants), tally)

    # ── assets.json ───────────────────────────────────────────────────────────
    assets: list[dict] = _load(DATA_DIR / "assets.json")
    tally = {}
    for rec in assets:
        _tally(tally, migrate_asset(rec))
    _save(DATA_DIR / "assets.json", assets)
    _section(lines, "assets.json", len(assets), tally)

    # ── goals.json ────────────────────────────────────────────────────────────
    goals_data: dict = _load(DATA_DIR / "goals.json")
    tally = {}
    total_goals = 0

    for rec in goals_data.get("practice_goals", []):
        _tally(tally, migrate_goal(
            rec,
            pillar="Technical Strategy & Architecture",
            tags=[rec.get("kpi", "")],
        ))
        total_goals += 1

    for area, area_goals in goals_data.get("subagent_goals", {}).items():
        for rec in area_goals:
            _tally(tally, migrate_goal(rec, pillar=_pillar(area), tags=[area]))
            total_goals += 1

    _save(DATA_DIR / "goals.json", goals_data)
    _section(lines, "goals.json", total_goals, tally)

    # ── initiatives.json ──────────────────────────────────────────────────────
    initiatives: list[dict] = _load(DATA_DIR / "initiatives.json")
    tally = {}
    for rec in initiatives:
        _tally(tally, migrate_initiative(rec))
    _save(DATA_DIR / "initiatives.json", initiatives)
    _section(lines, "initiatives.json", len(initiatives), tally)

    # ── ai_use_cases.json ─────────────────────────────────────────────────────
    ai_use_cases: list[dict] = _load(DATA_DIR / "ai_use_cases.json")
    tally = {}
    for rec in ai_use_cases:
        _tally(tally, migrate_ai_use_case(rec))
    _save(DATA_DIR / "ai_use_cases.json", ai_use_cases)
    _section(lines, "ai_use_cases.json", len(ai_use_cases), tally)

    # ── Human review items ────────────────────────────────────────────────────
    lines.append("\n" + "=" * 68)
    lines.append("  ITEMS REQUIRING HUMAN REVIEW")
    lines.append("=" * 68)

    # Flatten all records for sourceUrl audit
    practice_goals: list[dict]          = goals_data.get("practice_goals", [])
    subagent_goals_flat: list[dict]     = [
        g for area_goals in goals_data.get("subagent_goals", {}).values()
        for g in area_goals
    ]
    all_records: list[dict] = (
        consultants + assets + initiatives + ai_use_cases +
        practice_goals + subagent_goals_flat
    )
    empty_url_count = sum(1 for r in all_records if r.get("sourceUrl", "") == "")
    lines.append(
        f"\n[sourceUrl]  {empty_url_count}/{len(all_records)} records have an empty sourceUrl.\n"
        f"             Add a SharePoint or OneDrive URL to each item."
    )

    # Records where owner is the generic CoP Manager placeholder
    lines.append("\n[owner = 'CoP Manager']  Assign a named person where possible:")
    flagged = 0

    def _flag(kind: str, title: str) -> None:
        nonlocal flagged
        lines.append(f"  {kind:<14} {title[:54]}")
        flagged += 1

    for rec in assets:
        if isinstance(rec.get("owner"), dict) and rec["owner"].get("id") == "person_cop_manager":
            _flag("asset", rec.get("name", rec.get("id", "?")))

    for rec in initiatives:
        if isinstance(rec.get("owner"), dict) and rec["owner"].get("id") == "person_cop_manager":
            _flag("initiative", rec.get("title", rec.get("id", "?")))

    for rec in ai_use_cases:
        if isinstance(rec.get("owner"), dict) and rec["owner"].get("id") == "person_cop_manager":
            _flag("ai_use_case", rec.get("title", rec.get("id", "?")))

    for rec in practice_goals:
        if isinstance(rec.get("owner"), dict) and rec["owner"].get("id") == "person_cop_manager":
            _flag("goal", rec.get("title", rec.get("id", "?")))

    for area, area_goals in goals_data.get("subagent_goals", {}).items():
        for rec in area_goals:
            if isinstance(rec.get("owner"), dict) and rec["owner"].get("id") == "person_cop_manager":
                _flag(f"goal/{area}", rec.get("title", rec.get("id", "?")))

    if flagged == 0:
        lines.append("  (none — all records have a named owner)")

    # AI use cases where stage suggests deployment but client_deployed is False
    lines.append("\n[ai_use_case stage/client mismatch]  Verify deployment status:")
    mismatch = 0
    for rec in ai_use_cases:
        stage     = rec.get("stage", "")
        deployed  = rec.get("client_deployed", False)
        if stage in ("adopted", "piloting") and not deployed:
            lines.append(
                f"  {rec.get('title','?')[:60]}\n"
                f"    stage={stage!r} but client_deployed=False"
            )
            mismatch += 1
    if mismatch == 0:
        lines.append("  (none)")

    lines.append(
        f"\nSummary: {empty_url_count} missing sourceUrl  |  "
        f"{flagged} generic owners  |  "
        f"{mismatch} stage/deployment mismatches"
    )
    lines.append("\nMigration complete.\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
