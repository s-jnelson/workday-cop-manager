# Solution 07: Expense Policy Reviewer — Deployment Guide

**File:** `solutions/07_expense_policy_reviewer.py`
**Responsible Agent:** Extend Sub-agent
**Version:** 1.0 | **Date:** 2026-07-08

---

## 1. Overview

The Expense Policy Reviewer automates the review of Workday expense report lines against configurable company expense policy rules. A deterministic rule engine checks each expense line for policy violations across nine categories (per diems, receipt requirements, prohibited items, alcohol, personal expenses, weekend meals, etc.). Claude AI then synthesizes violations at the expense report level to provide an overall approval recommendation (APPROVE / REVIEW / REJECT) and a draft manager communication note.

**Use Case:** Finance teams and expense auditors can use this tool during the expense approval workflow — either as a standalone audit tool run against a Workday expense report export, or as the foundation for a Workday Extend-based expense policy enforcement integration.

**Value Delivered:**
- Replaces manual expense review spreadsheets with a consistent, auditable rule engine
- Separates policy enforcement (deterministic rules) from judgment calls (Claude AI) — each is appropriate for its task
- Produces structured outputs suitable for import back into Workday or presentation to managers
- Three-tier severity model (P1/P2/P3) allows AP teams to prioritize review effort
- Optional Excel output for client teams who prefer spreadsheet-based review workflows

---

## 2. Prerequisites

**Python Version:** 3.10 or higher

**Required Packages:**
```bash
pip install pandas anthropic
```

**Optional Packages:**
```bash
pip install openpyxl    # For Excel output (.xlsx workbook)
```

**API Key Setup (required for AI analysis; use --no-ai to skip):**
```bash
# Windows
set ANTHROPIC_API_KEY=sk-ant-api03-...

# macOS / Linux
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

The tool can run in rule-engine-only mode with `--no-ai`. In this mode, ANTHROPIC_API_KEY is not required and no external API calls are made.

**Input Data Format:**
The tool expects a CSV with the following columns, matching a standard Workday expense report export:

| Column | Required | Type | Notes |
|---|---|---|---|
| Expense_Report_ID | Yes | String | Groups lines into reports |
| Employee_ID | Yes | String | Worker identifier |
| Expense_Date | Yes | Date | Format: YYYY-MM-DD |
| Category | Yes | String | Workday expense item type |
| Amount | Yes | Decimal | Expense amount (assumes USD unless Currency specified) |
| Currency | No | String | ISO 4217; defaults to USD |
| Description | Yes | String | Expense description — used for keyword rules |
| Receipt_Attached | Yes | String | Y/N |
| Merchant | No | String | Vendor name |
| Cost_Center | No | String | Charging cost center |

---

## 3. Quick Start

```bash
# 1. Run with demo data (no API key needed in --no-ai mode)
python 07_expense_policy_reviewer.py --demo --no-ai

# 2. Run with demo data and AI analysis
export ANTHROPIC_API_KEY=sk-ant-...
python 07_expense_policy_reviewer.py --demo

# 3. Run against a real expense export
python 07_expense_policy_reviewer.py --input workday_expenses_export.csv
```

---

## 4. Usage — All CLI Flags

| Flag | Description | Example |
|---|---|---|
| `--input FILE` | Path to expense report CSV | `--input expenses.csv` |
| `--demo` | Use embedded demo data (15 sample rows, 5 reports) | `--demo` |
| `--no-ai` | Rule engine only — skip Claude analysis | `--no-ai` |
| `--policy FILE` | JSON file with policy overrides | `--policy client_policy.json` |
| `--output-dir DIR` | Directory for output files | `--output-dir ./output` |

**Custom policy JSON format:**
```json
{
  "meals_per_diem": 100,
  "hotel_per_diem": 300,
  "entertainment_limit": 200,
  "alcohol_prohibited": false,
  "receipt_required_above": 50,
  "max_single_expense": 10000,
  "prohibited_categories": ["Personal Care", "Gym"]
}
```
Only include keys you want to override — unspecified keys retain the default value.

**Full example:**
```bash
python 07_expense_policy_reviewer.py \
  --input q1_expenses.csv \
  --policy acme_corp_policy.json \
  --output-dir ./expense_review_q1 \
  --no-ai
```

---

## 5. Input Data Format

**Column Definitions:**

- **Expense_Report_ID** — Groups individual expense lines into a single report for AI analysis and summary. Use the Workday Expense Report ID.
- **Employee_ID** — Worker ID. Used in output files; not used in rule logic.
- **Expense_Date** — Must be parseable as a date. Used for weekend meal detection.
- **Category** — Maps to Workday Expense Item type. Rules check for Meals, Hotel, Entertainment, Personal Care, Gym categories by substring match.
- **Amount** — Numeric expense amount. USD assumed. Multi-currency comparison is not yet implemented (amounts compared as-is to USD thresholds).
- **Currency** — ISO 4217 code. Preserved in output but not used for conversion.
- **Description** — Free-text field. Scanned for alcohol keywords, personal keywords, and business justification terms (for weekend meals).
- **Receipt_Attached** — Y/N or Yes/No or True/False. Missing receipt triggers P1 (>$500) or P2 ($25–$500) violation.
- **Merchant** — Preserved in output but not used in rule logic currently.
- **Cost_Center** — Preserved in output but not used in rule logic currently.

**Example row:**
```
ER-2024-001,EMP-101,2024-03-15,Meals,45.00,USD,Lunch with client - project kickoff,Y,The Capital Grille,CC-Finance
```

**Validation rules:**
- Expenses with non-numeric Amount values are skipped with a warning
- Expense_Date parsing failure means weekend meal rules are not applied for that row
- Rows with missing Expense_Report_ID are grouped under "UNKNOWN"

---

## 6. Output Description

**`<base_name>_policy_violations.csv`** — One row per violation with:
- All expense line identifiers preserved
- `Violation_Rule` — machine-readable rule name
- `Severity` — P1 / P2 / P3
- `Violation_Detail` — human-readable explanation
- `Suggested_Action` — recommended AP team action

**`<base_name>_report_summary.csv`** — One row per expense report with:
- `Expense_Report_ID`, `Employee_ID`, `Total_Amount`, `Expense_Line_Count`
- `P1_Count`, `P2_Count`, `P3_Count`, `Total_Violations`
- `recommendation` — APPROVE / REVIEW / REJECT (AI or rule-based fallback)
- `rationale` — Claude's explanation of the recommendation
- `manager_note` — Draft manager communication (Claude-generated)

**`<base_name>_expense_review.xlsx`** — Excel workbook with two sheets (requires openpyxl):
- Sheet 1: All violations
- Sheet 2: Report summary with recommendations

**Severity Definitions:**

| Severity | Meaning | Examples |
|---|---|---|
| P1 | Immediate action required; likely do not reimburse | Prohibited items, missing receipt >$500, over max single expense |
| P2 | Review required; partial reimbursement likely | Over per diem, missing receipt $25–$499, alcohol |
| P3 | Advisory flag; manager discretion | Weekend meal no justification, over entertainment limit |

**Recommendation Logic:**
- **APPROVE** — No P1 or P2 violations (rule-based) or Claude confirms violations are minor/explainable
- **REVIEW** — P2 violations present; requires manager review before approval
- **REJECT** — P1 violations present; Claude confirms violations are genuine

---

## 7. Integration with Workday

**Extracting Expense Data from Workday:**

*Via Custom Report (RaaS):*
1. In Workday, navigate to **Reports** > Create a custom report on **Expense Report Lines** business object
2. Include columns matching the input format
3. Filter by status (e.g., In Progress, Pending Approval) to get active reports
4. Enable RaaS: **Actions** > **Web Service** > **View URLs**

*Via EIB Outbound:*
1. Configure an outbound EIB using **Get Expense Reports** web service
2. Schedule to run nightly or trigger on status change events

*Via Workday REST API:*
```python
# Workday REST API for expense reports
# GET /api/expenseManagement/v1/expenseReports
# Authentication: OAuth 2.0 (recommended) or Basic Auth
import requests
headers = {"Authorization": f"Bearer {access_token}"}
response = requests.get(
    "https://wd2-services1.myworkday.com/ccx/api/expenseManagement/v1/expenseReports",
    headers=headers,
    params={"status": "Pending_Approval"}
)
```

**Loading Results Back into Workday:**

Option 1 — Manual: AP reviewers use the `_report_summary.csv` to make approval decisions in Workday manually

Option 2 — Workday Extend: Build a Workday Extend app that:
- Runs the rule engine as a REST endpoint
- Stores violation flags as custom fields on Expense Report
- Surfaces the AI recommendation in the expense approval task

Option 3 — Integration: Use the EIB or REST API to update custom fields on Expense Report Lines with violation flags

**Recommended Architecture for Production:**
```
Workday Scheduled Report (RaaS nightly export)
        |
        v
    SFTP / Blob Storage
        |
        v
Python Script (07_expense_policy_reviewer.py)
        |
        +---> violations.csv --> Power BI Dashboard
        +---> summary.csv -----> AP Team SharePoint
        +---> expense_review.xlsx --> Manager Email Attachment
```

---

## 8. Agent Readiness Assessment

*Written from the perspective of the Extend Sub-agent*

**Production Readiness: ★★★★☆**

**What's Ready for Immediate Use:**
- Nine policy rules are fully implemented and tested with demo data
- Three-severity model (P1/P2/P3) matches real-world AP review prioritization
- `--no-ai` mode runs without any API dependencies — suitable for client environments with internet restrictions
- `--policy` flag allows zero-code policy customization via JSON
- Excel output works immediately if openpyxl is installed
- Claude's per-report analysis (recommendation + manager note) is high quality and production-usable

**What Needs Customization Per Client:**
- **Policy values:** Every client has different per diem rates, receipt thresholds, and prohibited categories. The `--policy` flag handles this, but the client's T&E policy document must be reviewed to set correct values before go-live.
- **Category names:** The rule engine matches categories by substring (e.g., checks if "Meals" appears in the Category field). If the client's Workday tenant uses different expense item names, update the `MEAL_CATEGORIES`, `HOTEL_CATEGORIES`, and `ENTERTAINMENT_CATEGORIES` lists.
- **Currency handling:** The current tool compares all amounts as-is to USD thresholds. International clients need a currency conversion step added.
- **Keyword lists:** The `ALCOHOL_KEYWORDS` and `PERSONAL_KEYWORDS` lists are English-only. Multi-language descriptions require expansion.
- **Weekend business justification:** The keywords used to detect business purpose in weekend meals are conservative. Client-specific terms (internal project names, client names) should be added.

**Known Limitations:**
- No multi-currency support — all amounts compared to USD thresholds without conversion
- Keyword-based detection (alcohol, personal items) can produce false positives on legitimate expenses with overlapping terms
- The per diem limits are daily, but the tool does not aggregate multiple meal expenses on the same day — each expense line is evaluated independently
- Claude analysis is called per expense report (grouped by Expense_Report_ID) only when P1/P2 violations exist — reports with only P3 violations do not get AI analysis
- No integration with Workday's delegation or approval hierarchy — routing logic must be implemented separately

**Recommended Next Steps Before Client Deployment:**
1. Obtain client T&E policy document and translate all limits/rules to `--policy` JSON format
2. Review the client's Workday expense item categories and update `MEAL_CATEGORIES` etc. accordingly
3. Run `--demo --no-ai` to verify rule engine output format
4. Run `--demo` with API key to verify Claude analysis quality
5. Run against a sample of real (approved) historical expenses to tune false positive rate
6. Define the AP team's workflow for consuming the output (manual review, Power BI, or Extend app)

---

## 9. Deployment Checklist

- [ ] Python 3.10+ installed
- [ ] `pip install pandas anthropic openpyxl` completed
- [ ] `ANTHROPIC_API_KEY` set (if using AI analysis)
- [ ] `--demo --no-ai` run successfully
- [ ] `--demo` (with AI) run successfully and recommendation quality reviewed
- [ ] Client T&E policy document reviewed and `--policy` JSON file created
- [ ] Client's Workday expense item category names verified and updated in script if needed
- [ ] Currency handling requirement assessed (single vs. multi-currency client)
- [ ] Expense report CSV export from Workday tested and column names verified
- [ ] `--input <client_sample>` run against historical approved expenses to tune false positive rate
- [ ] Output files reviewed with client AP team lead
- [ ] Excel output (`openpyxl`) tested and format approved by client
- [ ] Production scheduling mechanism configured (nightly RaaS export + script run)
- [ ] Escalation workflow documented (who reviews P1 violations, what's the SLA)
- [ ] Runbook created for AP team with screenshots

---

## 10. Practice Sharing Guidelines

**Sharing within the CoP:**
- The `--demo` output makes an excellent live demo in CoP sessions — run it on screen, walk through the P1 violations, and show the Claude manager note
- This tool is particularly resonant with Finance AP/AR leads who recognize the manual effort it replaces
- Share the `DEFAULT_POLICY` dict in CoP discussions — it often triggers useful conversations about how different clients define "policy"

**Sharing with Clients:**
- Lead with the `--no-ai` demo first — showing the deterministic rule engine builds trust before introducing the AI layer
- The manager note generated by Claude is a crowd-pleaser in demos — show a P1 violation and the resulting note side by side
- Be explicit that the AI recommendation is an input to human judgment, not a final decision
- Remind clients that policy customization via `--policy` JSON means they own the policy definition — IT does not need to re-deploy the script when policy changes

**Extending via Workday Extend:**
- This solution is the natural foundation for a Workday Extend-based expense compliance app
- The rule engine can be exposed as a REST microservice (wrap in FastAPI or Flask) and called from a Workday Extend orchestration
- Contact the Extend Sub-agent lead to discuss the Workday Extend integration pattern before building

**Contributing Improvements:**
- Additional rule categories (mileage, per diem accumulation, duplicate detection) are welcome contributions
- If you tune the Claude prompt for better recommendation quality on a specific client's data, share the improved prompt with the CoP AI working group
