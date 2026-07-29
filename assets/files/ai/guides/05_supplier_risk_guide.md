# Solution 05: Supplier Risk Scorer — Deployment Guide

**File:** `solutions/05_supplier_risk_scorer.py`
**Responsible Agent:** Integrations Sub-agent
**Version:** 1.0 | **Date:** 2026-07-08

---

## 1. Overview

The Supplier Risk Scorer ingests Workday supplier master data (exported as CSV) and automatically scores each supplier across four risk dimensions: data completeness, payment terms exposure, geographic sanctions risk, and payment method risk. Each supplier receives a score from 0–100 and is classified as LOW / MEDIUM / HIGH / CRITICAL.

**Use Case:** Finance CoP practitioners can run this tool during supplier onboarding reviews, periodic audit cycles, or pre-close supplier hygiene checks to surface high-risk vendors before payments are released.

**Value Delivered:**
- Replaces manual spreadsheet-based supplier review processes
- Provides consistent, defensible risk classification
- Optionally generates Claude AI narratives for HIGH/CRITICAL suppliers — ready to attach to audit documentation or escalation emails
- Outputs structured CSVs that can be loaded back into Workday as worker-reported data or used in Power BI dashboards

---

## 2. Prerequisites

**Python Version:** 3.10 or higher

**Required Packages:**
```bash
pip install pandas
```

**Optional Packages (for AI narratives):**
```bash
pip install anthropic
```

**API Key Setup (for AI narratives):**
```bash
# Windows
set ANTHROPIC_API_KEY=sk-ant-api03-...

# macOS / Linux
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

**Input Data Format:**
The tool expects a CSV with the following columns from the Workday Supplier Master iLoad template:

| Column | Required | Type | Notes |
|---|---|---|---|
| Supplier_ID | Yes | String | Unique identifier |
| Supplier_Name | Yes | String | Legal name |
| Supplier_Category | No | String | Missing triggers score deduction |
| Tax_ID | No | String | EIN/TIN — missing = 10-point deduction |
| Default_Currency | No | String | ISO 4217 (USD, EUR…) |
| Payment_Terms_Days | No | Integer | Number of days; blank = moderate risk |
| Preferred_Payment_Type | No | String | ACH, Wire, Check, EFT |
| Address_Country | No | String | Full country name; missing = risk deduction |

Columns can be in any order. Extra columns are ignored.

---

## 3. Quick Start

```bash
# 1. Run with demo data (no input file or API key needed)
python 05_supplier_risk_scorer.py --demo

# 2. Run against a real supplier export
python 05_supplier_risk_scorer.py --input workday_suppliers_export.csv

# 3. Run with AI narratives enabled
export ANTHROPIC_API_KEY=sk-ant-...
python 05_supplier_risk_scorer.py --input workday_suppliers_export.csv
```

---

## 4. Usage — All CLI Flags

| Flag | Description | Example |
|---|---|---|
| `--input FILE` | Path to supplier master CSV | `--input suppliers.csv` |
| `--demo` | Use embedded 8-row sample data | `--demo` |
| `--no-ai` | Skip Claude narrative generation | `--no-ai` |
| `--country-risk FILE` | Load custom country risk JSON | `--country-risk risk_lists.json` |
| `--output-dir DIR` | Directory for output files | `--output-dir ./output` |

**Custom Country Risk JSON format:**
```json
{
  "high_risk": ["Russia", "Iran", "North Korea"],
  "medium_risk": ["Afghanistan", "Iraq", "Libya"]
}
```

**Full example with all options:**
```bash
python 05_supplier_risk_scorer.py \
  --input suppliers_2026Q1.csv \
  --country-risk custom_risk_lists.json \
  --output-dir ./risk_output \
  --no-ai
```

---

## 5. Input Data Format

**Column Definitions:**

- **Supplier_ID** — Workday supplier reference ID (e.g., `SUP-00123`). Used as the primary identifier in output files.
- **Supplier_Name** — Legal registered name. Appears in all output files and AI narratives.
- **Supplier_Category** — Workday supplier category reference value. Missing reduces completeness score by 3 points.
- **Tax_ID** — EIN or TIN in `XX-XXXXXXX` format. Missing reduces completeness score by 10 points (highest deduction).
- **Default_Currency** — ISO 4217 currency code. Informational; does not affect scoring.
- **Payment_Terms_Days** — Integer number of days. Missing scores as moderate risk (12 points). Values >60 score maximum (25 points).
- **Preferred_Payment_Type** — One of: ACH, Wire, Check, EFT. Wire = highest risk (20 pts); blank = 15 pts.
- **Address_Country** — Full country name as it appears in Workday. Used for sanctions list matching.

**Example row:**
```
SUP-001,Acme Office Supplies,Office Supplies,12-3456789,USD,30,ACH,United States
```

**Validation rules:**
- Missing columns trigger a warning but scoring continues with available data
- Blank cells are treated as missing (score deducted or moderate risk applied)
- Country matching is case-sensitive — use exact Workday country names

---

## 6. Output Description

The tool produces two output files:

**`<base_name>_risk_scores.csv`** — One row per supplier with:
- All input fields preserved
- `Score_Completeness`, `Score_PaymentTerms`, `Score_Geographic`, `Score_PaymentType` (each 0–25)
- `Total_Risk_Score` (0–100)
- `Risk_Level` (LOW / MEDIUM / HIGH / CRITICAL)
- `Top_Risk_Factor` — the dimension with the highest point contribution
- `AI_Narrative` — two-sentence Claude explanation (HIGH/CRITICAL only, if AI enabled)

**Interpreting Risk Levels:**
| Risk Level | Score Range | Action |
|---|---|---|
| LOW | 0–25 | Routine monitoring |
| MEDIUM | 26–50 | Annual review |
| HIGH | 51–75 | Enhanced due diligence required |
| CRITICAL | 76–100 | Immediate escalation; payment hold recommended |

**`<base_name>_high_risk_report.txt`** — Human-readable report for HIGH/CRITICAL suppliers only. Suitable for attachment to audit findings or escalation emails. Includes full score breakdown and AI narrative for each flagged supplier.

---

## 7. Integration with Workday

**Extracting Supplier Data from Workday:**

*Via RaaS (Report as a Service):*
1. In Workday, navigate to **Reports** > find or create a custom report on the **Supplier** business object
2. Include the columns matching the input format above
3. Enable RaaS output via: **Actions** > **Web Service** > **View URLs**
4. Use the JSON or CSV endpoint with Basic Auth or OAuth 2.0

*Via EIB (Enterprise Interface Builder):*
1. Create an outbound EIB using **Get Suppliers** web service operation
2. Configure the transformation to match the CSV column names
3. Schedule the EIB to run nightly and drop to a shared network path or SFTP

*Direct API call example (Python):*
```python
import requests

url = "https://wd2-services1.myworkday.com/ccx/service/yourcompany/Staffing/v42.0"
# Use Workday REST API or SOAP to fetch supplier data
# See Workday Developer Docs: https://community.workday.com/node/218
```

**Loading Risk Scores Back into Workday:**
- Use a custom Workday report with the risk CSV as input to populate custom fields on the Supplier object
- Or surface results in a Workday Prism Analytics dataset for dashboarding

---

## 8. Agent Readiness Assessment

*Written from the perspective of the Integrations Sub-agent*

**Production Readiness: ★★★★☆**

**What's Ready for Immediate Use:**
- All four risk scoring dimensions are fully implemented and tested with demo data
- The --demo flag provides a runnable proof-of-concept with no setup required
- Output files are immediately usable in Excel or Power BI
- Country risk lists cover the primary OFAC and EU sanctions countries
- Claude narrative generation is production-quality and handles API failures gracefully

**What Needs Customization Per Client:**
- **Country risk lists:** Every client has different geographic exposure and may have internal policies beyond OFAC. The `--country-risk` flag supports this but the lists must be sourced from the client's compliance team.
- **Scoring weights:** The 0–25 per dimension is a CoP default. Clients in regulated industries (banking, defense) may need to weight geographic or payment type risk more heavily.
- **Supplier_Category field:** Workday category reference values vary by tenant. The category field is currently used only for completeness scoring, but clients may want category-specific rules (e.g., all "Staffing" suppliers must have W-9 on file).
- **Column name mapping:** If the client's EIB or RaaS export uses different column names, add a mapping step before scoring.

**Known Limitations:**
- Does not pull data directly from Workday — requires a CSV export step
- Country matching is case-sensitive and requires exact Workday country names
- AI narrative generation requires a live Anthropic API connection — not suitable for air-gapped environments
- Scoring is univariate (each dimension scored independently) — correlated risk factors are not modeled

**Recommended Next Steps Before Client Deployment:**
1. Obtain a sample supplier export from the client's Workday sandbox
2. Validate that column names match the expected format (or add a name mapping config)
3. Run `--demo` first, then `--input <client_sample>` to verify scoring logic
4. Review country risk lists with client's compliance team
5. Set up a scheduled EIB export + nightly script run (see Integration section)

---

## 9. Deployment Checklist

- [ ] Python 3.10+ installed on target machine
- [ ] `pip install pandas` completed
- [ ] `pip install anthropic` completed (if using AI narratives)
- [ ] `ANTHROPIC_API_KEY` set in environment (if using AI narratives)
- [ ] Supplier master CSV export from Workday tested and column names verified
- [ ] Country risk lists reviewed and customized for client's compliance policy
- [ ] Output directory created and write permissions confirmed
- [ ] `--demo` run successfully
- [ ] `--input <client_sample>` run and results reviewed with engagement team
- [ ] Output CSV validated in Excel / Power BI
- [ ] Scheduling mechanism configured (Task Scheduler / cron / Workday EIB schedule)
- [ ] Runbook documented with client-specific instructions
- [ ] Results shared with client's Procurement / Compliance lead

---

## 10. Practice Sharing Guidelines

**Sharing within the CoP:**
- This solution is stored in the CoP's shared AI Solutions Library at `assets/files/ai/solutions/`
- Reference this guide when presenting to client teams — it provides the business context needed for non-technical stakeholders
- Share `--demo` output (not client data) in CoP knowledge-sharing sessions

**Sharing with Clients:**
- Run `--demo` to produce sample output before client demos — never use actual client supplier data in demos
- The `_risk_scores.csv` output is appropriate for sharing with client Procurement or AP teams
- The `_high_risk_report.txt` may contain sensitive vendor information — treat as confidential
- If the client wants to retain and run this tool independently, provide the Python file and this guide; do NOT share the ANTHROPIC_API_KEY — they must obtain their own

**Extending the Solution:**
- To add new risk dimensions, add a new `score_*` function following the existing pattern and update `score_supplier()`
- To change the risk level thresholds, update the `determine_risk_level()` function
- Submit improvements back to the CoP Integrations Sub-agent lead for review before merging into the shared library
