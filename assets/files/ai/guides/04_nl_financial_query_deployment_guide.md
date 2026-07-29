# Deployment Guide: Natural Language Financial Query Tool
**Solution:** `solutions/04_nl_financial_query.py`
**Responsible Sub-agent:** Reporting Sub-agent
**Last Updated:** 2026-07-08

---

## 1. Overview

The Natural Language Financial Query Tool demonstrates how conversational AI can lower the barrier to Workday financial reporting. Finance users often know the question they want to ask ("Who are our biggest vendors this quarter?") but don't know which Workday report answers it, what the report is called, or how to set its parameters. This tool bridges that gap.

A user types a question in plain English. Claude maps it to the most appropriate Workday RaaS (Reports as a Service) report from a catalog of seven financial reports, extracts any parameter values mentioned in the question, and returns simulated results from embedded sample data. The tool also shows the actual RaaS URL the user would call against their own Workday tenant to get live data.

**What it does:**
- Maintains a catalog of 7 common Workday Finance RaaS reports (vendor spend, AP aging, trial balance, budget vs. actual, expense by category, AR aging, fixed asset register)
- Uses Claude claude-sonnet-4-5 to parse the user's natural language question and return a structured JSON mapping: {report name, parameters, interpretation, confidence}
- Displays simulated results from embedded sample data as a formatted table
- Shows the parameterized RaaS URL for connecting to the user's actual Workday tenant
- Runs as an interactive REPL (ask multiple questions without restarting) or in `--demo` batch mode

**Value delivered:**
- Enables non-technical finance staff to self-serve reports without Workday training
- Demonstrates the pattern of "AI as a query translator" — applicable to any report catalog
- Bridges the gap between business questions and technical Workday report parameters
- Produces working RaaS URLs that clients can adapt immediately for real data

**Typical use cases:**
- Finance team member asks a question during a business review without a Workday expert present
- Training / demonstration of AI-augmented finance analytics capabilities
- Prototype for a full-scale NL-to-Workday reporting interface

---

## 2. Prerequisites

### Python Version
Python 3.8 or higher.

### Required Packages
```bash
pip install anthropic
```

The `anthropic` SDK is the only non-standard dependency. All other libraries (`json`, `os`, `sys`, `argparse`, `textwrap`) are standard library.

**Note:** Unlike Solution 02, this tool requires the `anthropic` package and a valid API key. The Claude mapping step is the core function; there is no fallback mode without it.

### API Key Setup — Required
```bash
# Linux / macOS
export ANTHROPIC_API_KEY="sk-ant-..."

# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Windows Command Prompt
set ANTHROPIC_API_KEY=sk-ant-...
```

Without the API key, the tool will exit with an error message.

### No Input File Required
This is a fully interactive tool. No CSV files or data preparation needed.

---

## 3. Quick Start

```bash
# 1. Install dependency
pip install anthropic

# 2. Set API key
export ANTHROPIC_API_KEY="sk-ant-your-key-here"

# 3. Run 5 demo queries
python 04_nl_financial_query.py --demo
```

Or start the interactive REPL:
```bash
python 04_nl_financial_query.py
```

Then type: `Who are our top vendors this quarter?`

---

## 4. Usage

### All CLI Flags

| Flag | Description | Example |
|------|-------------|---------|
| `--demo` | Run 5 pre-built example queries automatically | `--demo` |
| `--list` | Show all available reports in the catalog | `--list` |
| `--help` / `-h` | Show help text | `--help` |

No `--input` or `--output` flags — this is an interactive REPL tool.

### Usage Examples

```bash
# Interactive REPL — recommended for live demos and exploration
python 04_nl_financial_query.py

# Run all 5 demo queries non-interactively
python 04_nl_financial_query.py --demo

# List all available reports without starting the REPL
python 04_nl_financial_query.py --list
```

### In-REPL Commands

| Input | Action |
|-------|--------|
| Any natural language question | Claude maps it to a report and shows results |
| `list` | Displays the full report catalog |
| `quit`, `exit`, `q` | Exits the REPL |
| Ctrl+C | Also exits gracefully |

### Example Questions That Work Well

```
Who are our top 10 vendors by spend in Q1?
Show me AP aging as of March 31
Which cost centers are over budget this year?
What did we spend on travel and meals last quarter?
What's the net book value of our fixed assets?
Give me a trial balance for the first quarter
Show me AR aging
What are the biggest expense categories for the sales team?
```

### Example Questions That May Return Low Confidence

```
Is our cash flow positive this month?        (no cash flow statement report in catalog)
What's our EBITDA?                           (calculated metric, no direct report)
Compare vendor prices                        (no vendor price benchmarking report)
Show me headcount costs by manager           (HCM data, not Finance catalog)
```

Low confidence triggers a clarifying prompt and lists available reports for the user to choose from.

---

## 5. Input Data Format

This tool accepts **typed natural language questions** only — no files or CSVs.

### What Claude Extracts From a Question

Claude parses the question for:

1. **Report intent** — which of the 7 catalog reports best answers the question
2. **Date parameters** — phrases like "Q1", "last month", "as of March 31", "this quarter" are converted to date ranges or as-of dates
3. **Company context** — if mentioned (e.g., "for EMEA"), extracted as the `company` parameter
4. **Limit/scope** — "top 10", "top 5" extracted as the `limit` parameter for vendor spend

### Parameter Defaults
When parameters are not mentioned in the question, Claude uses sensible defaults:
- `company`: `Acme_Corp`
- `as_of_date`: `2024-03-31` (hardcoded in the prompt — update to current date as needed)
- `from_date` / `to_date`: Quarter-based inference (e.g., "Q1" → `2024-01-01` to `2024-03-31`)
- `limit`: `10` for vendor spend

### What "Simulated Results" Means
The results shown are from the embedded `sample_data` lists in the `RAAS_CATALOG` dictionary. They are illustrative values designed to look realistic but are **not** from a real Workday tenant. The tool clearly states this after every result display.

---

## 6. Output Description

### Report Mapping Output

```
Question: Who are our top 5 vendors by spend this quarter?
Mapping to Workday RaaS report...

=================================================================
MATCHED REPORT: vendor_spend_by_period
=================================================================
Confidence:     HIGH — Multiple clear signals: top vendors, spend, quarterly period
Interpretation: This will show the highest-spending vendors ranked by total invoice amount for the specified period.

Parameters:
  company: Acme_Corp
  from_date: 2024-01-01
  to_date: 2024-03-31
  limit: 5

Simulated RaaS URL (replace {tenant} with your Workday tenant):
  https://{tenant}.workday.com/ccx/service/customreport2/{tenant}/ISU_Reporting/Vendor_Spend_By_Period?...

SIMULATED RESULTS (from embedded sample data):
-----------------------------------------------------------------
  rank   vendor                   spend     invoice_count  avg_invoice
  ---------------------------------------------------------------------
  1      TechCorp Solutions       $2.9M     48             $59.4K
  2      Global Facilities Inc    $1.9M     24             $80.0K
  ...

NOTE: These are sample/illustrative values, not live Workday data.
      Connect to your Workday tenant using the URL above for real data.
```

### Confidence Levels

| Confidence | Meaning | User Action |
|------------|---------|-------------|
| HIGH | Clear report match; parameters extracted | Review and use the RaaS URL |
| MEDIUM | Likely match; some ambiguity in parameters | Verify parameters before calling RaaS |
| LOW | Uncertain match or no report fits well | Rephrase the question or choose from the catalog list |

### Available Reports and Their Sample Data

The catalog includes 7 reports with embedded sample data:

| Report | Sample Data Shape |
|--------|------------------|
| `vendor_spend_by_period` | 10 vendors with rank, spend, invoice count, avg invoice |
| `ap_aging_summary` | 5 aging buckets + total with amounts, counts, percentages |
| `gl_trial_balance` | 10 accounts with debit, credit, net balance |
| `budget_vs_actual` | 8 cost centers with budget, actual, variance, % used |
| `expense_by_category` | 8 expense categories with amounts, report counts, top spender |
| `ar_aging_summary` | 5 aging buckets + total with customer counts and amounts |
| `fixed_asset_register` | 6 asset classes + total with cost, accumulated depreciation, NBV |

---

## 7. Integration with Workday

### From Simulated to Live Data

The tool's primary integration deliverable is the **parameterized RaaS URL** it generates. Once a user identifies the right report and parameters through the conversational interface, the RaaS URL provides a direct path to real Workday data.

### Step-by-Step: Going Live with a Matched Report

**Step 1: Identify your Workday tenant name**
Your tenant name is the subdomain in your Workday URL:
`https://impl.workday.com/acme_corp/...` — tenant = `acme_corp`

**Step 2: Verify the RaaS report exists in your tenant**
The URL templates in the catalog reference ISU_Reporting as the report owner. You need to:
1. Open the RaaS URL in a browser (logged in as an admin or ISU)
2. If the report does not exist, create it in Workday using the report builder
3. Enable "Share with all users" or grant the ISU access

**Step 3: Replace the URL template variables**
```
# Template:
https://{tenant}.workday.com/ccx/service/customreport2/{tenant}/ISU_Reporting/Vendor_Spend_By_Period?...

# Populated:
https://acme_corp.workday.com/ccx/service/customreport2/acme_corp/ISU_Reporting/Vendor_Spend_By_Period?Company=Acme_Corp&From_Date=2024-01-01&To_Date=2024-03-31&Limit=10&format=json
```

**Step 4: Authenticate**
RaaS calls require Basic Auth with ISU credentials:
```bash
curl -u "ISU_username:password" \
  "https://acme_corp.workday.com/ccx/service/customreport2/acme_corp/ISU_Reporting/Vendor_Spend_By_Period?Company=Acme_Corp&format=json"
```

**Step 5: Replace sample data with live data**
To upgrade this tool from demo to production, replace the `sample_data` lookups with live RaaS API calls:

```python
import requests

def fetch_raas_data(report_name: str, params: dict, tenant: str, isu_user: str, isu_pass: str) -> list:
    """Fetch live data from Workday RaaS."""
    url = RAAS_CATALOG[report_name]["url_template"].format(tenant=tenant, **params) + "&format=json"
    response = requests.get(url, auth=(isu_user, isu_pass))
    response.raise_for_status()
    return response.json().get("Report_Entry", [])
```

### Workday Report Requirements
For each catalog entry to work against a real tenant, the following Workday reports must exist and be accessible:
- Reports must be marked as "Enable As Web Service" in the report definition
- The ISU used for authentication must have view access to all report prompts and data sources
- Prompt fields must use the same parameter names as the URL template (or the URL needs updating to match actual Workday prompt names)

---

## 8. Agent Readiness Assessment

*Written from the perspective of the Reporting Sub-agent responsible for this solution.*

**Production Readiness Rating: 3/5 — Strong demo; requires integration work for live deployment**

### What's Ready
- The conversational AI query translation is fully functional and consistently produces well-structured JSON mappings
- The report catalog covers the 7 most commonly requested Workday Finance reports
- Sample data is realistic enough for meaningful demos and stakeholder walkthroughs
- Confidence level system appropriately handles edge cases (low confidence triggers helpful fallback rather than a wrong answer)
- The REPL experience is polished and suitable for live client demos
- `--demo` mode runs 5 representative queries non-interactively — ideal for slide-deck or recording demos

### What Needs Customization Per Client

- **RaaS report names** — The `url_template` fields use `ISU_Reporting` as the report owner and generic report names. Every Workday tenant has different report names. Replace with the client's actual report names from their Workday environment.
- **Report catalog extension** — Clients will immediately ask "can I query [X report]?" when [X] is not in the catalog. Plan for 2–4 additional reports per client (common additions: headcount by cost center, open PO report, journal entry approval status).
- **Parameter prompt names** — Workday RaaS prompt parameters vary by report configuration. The URL templates need to be updated to match the actual prompt parameter names in each client's report definitions.
- **Sample data** — Replace with client-realistic numbers before any client-facing demo. Showing generic "Acme Corp" data in a client meeting is a credibility risk.
- **Date defaults** — The prompt hardcodes `2024-03-31` as the default as-of date. Update to use `datetime.now().date()` or a client-specific fiscal calendar.
- **Live data integration** — The biggest customization: replacing `sample_data` lookups with actual Workday RaaS API calls (see Integration section above). This is a 1–2 day development effort per deployment.

### Known Limitations
- **Sample data only** — Currently 100% simulated data. The tool cannot connect to a live Workday tenant without the integration work described above. This is a demo tool, not a production reporting system in its current state.
- **7-report catalog** — A real Workday Finance implementation has 50–200 reports. Questions outside the catalog always return low confidence. Expanding the catalog is straightforward (add entries to `RAAS_CATALOG`) but requires time investment.
- **No session memory** — The REPL does not remember previous questions. "Show me the same thing for Q2" will not work — the user must re-ask the full question.
- **English only** — Claude performs well in English; multilingual question support would require prompt engineering changes.
- **No auth handling** — The tool does not manage Workday credentials. The RaaS URL is generated but the user must handle authentication themselves.
- **Claude dependency** — If the Anthropic API is unavailable, the tool cannot function at all (no fallback like Solutions 1 and 2). Add a fallback keyword matcher for production use.

### Recommended Next Steps Before Client Deployment
1. Replace sample data with client-realistic numbers (use actual Workday report outputs)
2. Identify the 5 most common reporting questions the client's finance team asks and verify the catalog covers them
3. Update RaaS URL templates with the client's actual report names and prompt parameter names
4. Implement live Workday RaaS calls using the `requests` library with ISU credentials
5. Add 3–5 client-specific reports to the catalog based on their most-used reports
6. Test with non-technical finance users and refine question phrasing guidance based on their natural language patterns

---

## 9. Deployment Checklist

- [ ] Python 3.8+ installed
- [ ] `pip install anthropic` completed
- [ ] `ANTHROPIC_API_KEY` set and tested
- [ ] `--demo` mode runs successfully and produces clean output
- [ ] `--list` output reviewed — all 7 reports understood by team
- [ ] Sample data replaced with client-realistic values (before any client demo)
- [ ] Report catalog verified: all 7 reports exist in client's Workday tenant
- [ ] RaaS URL templates updated with client's actual report names
- [ ] Date defaults updated to use current date (not hardcoded 2024-03-31)
- [ ] Low-confidence behavior tested with out-of-scope questions
- [ ] Finance team users trained on what questions work well and what does not
- [ ] (For production) Live Workday RaaS API integration implemented
- [ ] (For production) ISU credentials configured for RaaS access
- [ ] (For production) Additional client-specific reports added to catalog

---

## 10. Practice Sharing Guidelines

### What to Include in a Handoff Package
1. The Python script (`04_nl_financial_query.py`) and this guide
2. A recording or GIF of the interactive REPL in action (15–30 seconds showing a question → result)
3. The `--demo` output as a text file showing all 5 example queries and their results
4. Client-specific additions: updated sample data, added reports, updated RaaS URLs
5. A note on what was customized and what would be needed to go fully live

### How to Present to the Practice

**30-second pitch:** "Type any financial question in plain English. The AI figures out which Workday report answers it, fills in the parameters, and shows you the results — plus the exact API URL to pull live data from their Workday tenant. The finance team stops needing to know Workday report names or how to set prompts. They just ask."

**Demo path:** Run `python 04_nl_financial_query.py --demo` and walk through the 5 examples. The most powerful moment is when a loosely worded question like "which cost centers are blowing their budget?" correctly maps to `budget_vs_actual` with the right parameters and shows a formatted variance table.

**For skeptics ("this is just sample data"):** Agree immediately — this is a demo of the translation layer, not a reporting system. The value is the AI's ability to map natural language to structured report parameters. The live data connection is a 1–2 day integration. The demo shows what the user experience would look like.

**Useful talking points:**
- This pattern (NL query → structured report parameters → data) works with any report catalog, not just Workday Finance
- The same approach can be applied to HCM, Payroll, or any Workday module with RaaS endpoints
- The confidence scoring prevents the AI from hallucinating a report that does not exist — low confidence = explicit acknowledgment of uncertainty

### Internal CoP Sharing
- Post under: Finance Tools > AI-Assisted Reporting / Conversational Finance
- Tag as: `NL Query`, `RaaS`, `Conversational AI`, `Workday Finance`, `Claude API`, `Reporting`, `Self-Service Analytics`
- Include a "what questions work" cheat sheet for demos — this will help other consultants use it without trial and error
- Flag the "sample data only" limitation clearly so no one accidentally demos this to a client expecting live data

### Roadmap Suggestion for Practice Leadership
This tool is a strong foundation for a more ambitious capability: a full NL-to-Workday reporting assistant where:
- The catalog is dynamically loaded from the client's Workday tenant (via the Report metadata API)
- Live RaaS data is fetched and displayed in real time
- Results can be exported to Excel or embedded in a Teams tab

Estimated build-out: 2–3 weeks of additional development on top of this foundation.
