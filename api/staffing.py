"""
Staffing S&D report processor for the Workday Finance CoP dashboard.

Processes WBG Supply and Assignments tabs from the standard Workday Supply &
Demand Excel report. Writes two separate data stores:
  - data/staffing_roster.json   : updated on every import (import-safe fields)
  - data/staffing_manual.json   : NEVER overwritten by imports (user edits only)
"""

from __future__ import annotations

import io
import json
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"
ROSTER_FILE = DATA_DIR / "staffing_roster.json"
MANUAL_FILE = DATA_DIR / "staffing_manual.json"

_write_lock = threading.Lock()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load(path: Path) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(path: Path, data: Any) -> None:
    with _write_lock:
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and pd.isna(val):
        return ""
    return str(val).strip()


def _parse_date(val) -> str | None:
    """Parse date value → ISO YYYY-MM-DD string, or None if blank/invalid."""
    s = _str(val)
    if not s or s.lower() in ("nan", "nat"):
        return None
    # Reject the Excel epoch placeholder (Jan 1 1900)
    for bad in ("01/01/1900", "1900-01-01", "01-jan-1900"):
        if s.lower().startswith(bad[:5]):
            return None
    for fmt in ("%d-%b-%Y", "%d-%b-%y", "%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _parse_pct(val) -> float:
    """Parse Percent Allocated value → float 0-100 (blank/NaN → 0)."""
    if val is None:
        return 0.0
    if isinstance(val, float) and pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace("%", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


# ── Core processor ─────────────────────────────────────────────────────────────

def process_sd_report(file_bytes: bytes) -> dict:
    """
    Process an S&D Excel report from raw bytes.

    Steps:
      1. Read WBG Supply — all workers in the supply pool.
      2. Read Assignments (header row=1) — one row per calendar assignment.
      3. Include only Finance L3 workers from Assignments, plus any supply
         workers absent from Assignments entirely.
      4. Group Assignments by Personnel Number, sum Percent Allocated.
      5. Merge supply-level metadata.
      6. Persist to staffing_roster.json (manual fields untouched).

    Returns a summary dict with counts and the full roster list.
    """
    xl = pd.ExcelFile(io.BytesIO(file_bytes))
    today = date.today().isoformat()

    # ── Step 1: WBG Supply ──────────────────────────────────────────────────
    supply_df = xl.parse("WBG Supply")
    supply: dict[str, dict] = {}
    for _, row in supply_df.iterrows():
        pnum = _str(row.get("Resource Personnel #"))
        if not pnum:
            continue
        supply[pnum] = {
            "personnel_number": pnum,
            "name": _str(row.get("Resource Full Name")),
            "enterprise_id": _str(row.get("Resource Enterprise ID")),
            "job_profile": _str(row.get("Resource Job Profile")),
            "management_level": _str(row.get("Resource Management Level")),
            "location": _str(row.get("Resource Location")),
            "metro_city": _str(row.get("Resource Metro City")),
            "org_l3": _str(row.get("Resource Org Unit Level 3")),
            "org_l4": _str(row.get("Resource Org Unit Level 4")),
            "certifications": _str(row.get("Resource Certification")),
            "staffable_status": _str(row.get("Resource Staffable Status")),
            "staffable_pct": _str(row.get("Resource % Staffable")),
            "general_comments": _str(row.get("Resource General Comments")),
        }

    # ── Step 2: Assignments (real header is in sheet row 2, pandas row 1) ──
    assign_df = xl.parse("Assignments", header=1)

    # Strip trailing spaces from the Entity L3 column (known issue in export)
    l3_col = "Employee Deployed to Entity L3"
    if l3_col in assign_df.columns:
        assign_df[l3_col] = assign_df[l3_col].fillna("").str.strip()

    # All personnel numbers present anywhere in Assignments
    all_assign_pnums: set[str] = set(
        _str(p)
        for p in assign_df["Personnel Number"].dropna()
        if _str(p)
    )

    # ── Step 3: Filter Assignments to Finance ──────────────────────────────
    finance_mask = assign_df[l3_col].str.lower() == "finance"
    finance_df = assign_df[finance_mask].copy()

    # ── Step 4: Build one roster record per personnel number ───────────────
    roster: dict[str, dict] = {}

    for pnum_raw, group in finance_df.groupby("Personnel Number"):
        pnum = _str(pnum_raw)
        if not pnum:
            continue

        first = group.iloc[0]
        assignments: list[dict] = []
        total_pct = 0.0

        for _, arow in group.iterrows():
            pct = _parse_pct(arow.get("Percent Allocated", 0))
            start = _parse_date(arow.get("Calendar Start Date"))
            end = _parse_date(arow.get("Calendar End Date"))
            assignments.append({
                "client": _str(arow.get("Client")),
                "project": _str(arow.get("Project")),
                "calendar_start": start,
                "calendar_end": end,
                "percent_allocated": pct,
                "calendar_entry": _str(arow.get("Calendar Entry")),
                "role_id": _str(arow.get("Role ID")),
            })
            total_pct += pct

        # Sort descending by start date so the most recent is first
        assignments.sort(key=lambda a: a.get("calendar_start") or "0000", reverse=True)
        current = assignments[0] if assignments else {}

        record: dict = {
            "personnel_number": pnum,
            "name": _str(first.get("Employee Name")),
            "email": _str(first.get("Employee Email")),
            "entity_l3": _str(first.get("Employee Deployed to Entity L3")),
            "job_profile": _str(first.get("Employee Job Profile")),
            "level": _str(first.get("Employee Level")),
            "level_group": _str(first.get("Employee Level Group")),
            "metro_city": _str(first.get("Employee Metro City")),
            "country": _str(first.get("Employee Country/Territory")),
            "in_assignments": True,
            "in_supply": pnum in supply,
            "assignments": assignments,
            # Card quick-display fields
            "current_client": current.get("client", ""),
            "current_project": current.get("project", ""),
            "current_start": current.get("calendar_start"),
            "current_end": current.get("calendar_end"),
            "current_pct": current.get("percent_allocated", 0),
            "total_pct": total_pct,
            "last_import": today,
        }

        # Supplement with supply metadata where available
        if pnum in supply:
            sup = supply[pnum]
            for k in ("management_level", "location", "certifications",
                      "staffable_status", "staffable_pct", "general_comments",
                      "enterprise_id", "org_l3", "org_l4"):
                record[k] = sup.get(k, "")
            if not record["name"]:
                record["name"] = sup["name"]
            if not record["metro_city"]:
                record["metro_city"] = sup["metro_city"]

        roster[pnum] = record

    # ── Step 5: Supply-only workers (not in Assignments at all) ────────────
    for pnum, sup in supply.items():
        if pnum not in all_assign_pnums:
            roster[pnum] = {
                "personnel_number": pnum,
                "name": sup["name"],
                "email": "",
                "entity_l3": sup.get("org_l3", ""),
                "job_profile": sup.get("job_profile", ""),
                "level": "",
                "level_group": "",
                "metro_city": sup.get("metro_city", ""),
                "country": "",
                "in_assignments": False,
                "in_supply": True,
                "assignments": [],
                "current_client": "",
                "current_project": "",
                "current_start": None,
                "current_end": None,
                "current_pct": 0,
                "total_pct": 0,
                "management_level": sup.get("management_level", ""),
                "location": sup.get("location", ""),
                "enterprise_id": sup.get("enterprise_id", ""),
                "certifications": sup.get("certifications", ""),
                "staffable_status": sup.get("staffable_status", ""),
                "staffable_pct": sup.get("staffable_pct", ""),
                "general_comments": sup.get("general_comments", ""),
                "org_l3": sup.get("org_l3", ""),
                "org_l4": sup.get("org_l4", ""),
                "last_import": today,
            }

    # ── Step 6: Persist ────────────────────────────────────────────────────
    _save(ROSTER_FILE, list(roster.values()))

    return {
        "total": len(roster),
        "finance_workers": sum(1 for r in roster.values() if r.get("in_assignments")),
        "supply_only": sum(1 for r in roster.values() if not r.get("in_assignments")),
        "report_date": today,
        "roster": list(roster.values()),
    }


# ── Public API helpers ─────────────────────────────────────────────────────────

def get_merged_roster() -> list[dict]:
    """Return the roster with manual fields overlaid (read-only merge)."""
    roster: list[dict] = _load(ROSTER_FILE) or []
    manual: dict = _load(MANUAL_FILE) or {}
    result = []
    for r in roster:
        pnum = r.get("personnel_number", "")
        m = manual.get(pnum, {})
        result.append({
            **r,
            "specialties": m.get("specialties", ""),
            "interests": m.get("interests", ""),
            "notes": m.get("notes", ""),
            "role_type": m.get("role_type", []),
            "capabilities": m.get("capabilities", []),
        })
    # Sort: Finance workers first, then alphabetically by name
    result.sort(key=lambda r: (0 if r.get("in_assignments") else 1, r.get("name", "").lower()))
    return result


MANUAL_FIELDS = {"specialties", "interests", "notes", "role_type", "capabilities"}


def update_manual(personnel_number: str, fields: dict) -> dict:
    """
    Persist manual fields for one worker.
    Only keys in MANUAL_FIELDS are written; all others are ignored.
    Returns the updated manual record for that worker.
    """
    manual: dict = _load(MANUAL_FILE) or {}
    manual.setdefault(personnel_number, {})
    for k, v in fields.items():
        if k in MANUAL_FIELDS:
            manual[personnel_number][k] = v
    _save(MANUAL_FILE, manual)
    return manual[personnel_number]


def get_report_data(
    name: str = "",
    entity_l3: str = "",
    client: str = "",
    role_type: str = "",
    capabilities: str = "",
    min_pct: float = 0,
    max_pct: float = 500,
    in_supply_only: bool = False,
) -> list[dict]:
    """Return filtered roster list for the report view."""
    roster = get_merged_roster()

    if name:
        n = name.lower()
        roster = [r for r in roster if n in r.get("name", "").lower()]
    if entity_l3:
        roster = [r for r in roster if entity_l3.lower() in r.get("entity_l3", "").lower()]
    if client:
        c = client.lower()
        roster = [r for r in roster if c in r.get("current_client", "").lower()]
    if role_type:
        roster = [r for r in roster if role_type in r.get("role_type", [])]
    if capabilities:
        cap_list = [c.strip() for c in capabilities.split(",") if c.strip()]
        roster = [r for r in roster if any(c in r.get("capabilities", []) for c in cap_list)]
    if in_supply_only:
        roster = [r for r in roster if not r.get("in_assignments")]
    roster = [r for r in roster if min_pct <= r.get("total_pct", 0) <= max_pct]

    return roster
