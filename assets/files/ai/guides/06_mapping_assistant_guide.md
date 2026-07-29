# Solution 06: Conversion Mapping Assistant — Deployment Guide

**File:** `solutions/06_conversion_mapping_assistant.py`
**Responsible Agent:** Conversion Sub-agent
**Version:** 1.0 | **Date:** 2026-07-08

---

## 1. Overview

The Conversion Mapping Assistant analyzes a legacy ERP CSV export and uses Claude AI to suggest field-level mappings to a target Workday object. It understands six common Workday objects (supplier master, ledger accounts, cost centers, customer master, open AP invoices, fixed assets) and produces a structured mapping table, data quality issue log, and a Markdown report suitable for conversion workplan documentation.

**Use Case:** During a Workday implementation, the data conversion workstream must map hundreds of legacy fields to Workday's data model. This tool accelerates the initial mapping pass from days to minutes, producing a first-draft mapping that the conversion team can review and refine rather than building from scratch.

**Value Delivered:**
- Eliminates the blank-page problem in conversion mapping workshops
- Surfaces data quality issues (format mismatches, missing required fields) before the first load attempt
- Produces deliverable-quality Markdown reports that can be pasted directly into a conversion workplan or shared in Teams
- Supports interactive overrides so the conversion analyst stays in control
- Protects client PII by stripping sensitive columns before sending to Claude

---

## 2. Prerequisites

**Python Version:** 3.10 or higher

**Required Packages:**
```bash
pip install pandas anthropic
```

**Optional Packages (for formatted table output):**
```bash
pip install tabulate
```

**API Key Setup (required — this tool has no rule-based fallback):**
```bash
# Windows
set ANTHROPIC_API_KEY=sk-ant-api03-...

# macOS / Linux
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

This tool requires Claude AI. It will exit with an error if `ANTHROPIC_API_KEY` is not set. There is no rule-based fallback — the intelligence of the mapping suggestion is the core value.

**Input Data Format:**
- Any CSV file exported from a legacy ERP system (SAP, Oracle, NetSuite, PeopleSoft, Sage, etc.)
- No specific column names are required — Claude analyzes whatever column names and sample values are present
- The tool strips columns matching PII patterns (ssn, tax_id, personal, dob, birth) before sending to Claude

---

## 3. Quick Start

```bash
# 1. Set API key
export ANTHROPIC_API_KEY=sk-ant-...

# 2. Run with demo data (no input file needed)
python 06_conversion_mapping_assistant.py --demo

# 3. Run against a real legacy extract
python 06_conversion_mapping_assistant.py \
  --source legacy_vendor_export.csv \
  --target supplier_master
```

---

## 4. Usage — All CLI Flags

| Flag | Description | Example |
|---|---|---|
| `--source FILE` | Path to legacy ERP CSV file | `--source sap_vendor.csv` |
| `--target OBJECT` | Workday target object name | `--target supplier_master` |
| `--demo` | Use embedded demo data (legacy vendor -> supplier_master) | `--demo` |
| `--interactive` | Allow user to override individual mappings after Claude's output | `--interactive` |
| `--output-dir DIR` | Directory for output files | `--output-dir ./output` |

**Supported target objects:**
| Object Key | Workday Object |
|---|---|
| `supplier_master` | Supplier Master |
| `ledger_accounts` | Chart of Accounts / Ledger Accounts |
| `cost_centers` | Cost Centers |
| `customer_master` | Customer Master (AR) |
| `open_ap_invoices` | Open AP Invoices |
| `fixed_assets` | Fixed Assets |

**Full example:**
```bash
python 06_conversion_mapping_assistant.py \
  --source oracle_gl_accounts.csv \
  --target ledger_accounts \
  --interactive \
  --output-dir ./conversion_output
```

---

## 5. Input Data Format

**Source CSV:**
- Any CSV format exported from a legacy system — no template required
- The tool reads the first 5 rows as sample data to send to Claude
- Column headers are used as the primary signal for mapping suggestions
- Best results when column headers are descriptive (e.g., `vendor_name` is better than `col_3`)

**Columns automatically stripped before sending to Claude (PII protection):**
- Any column whose name contains: `ssn`, `tax_id`, `personal`, `dob`, `birth`, `social_sec`, `national_id`
- The tool reports stripped columns to the user

**Recommended pre-processing:**
- Remove obviously irrelevant columns (internal system timestamps, row IDs, flags)
- Ensure the file uses UTF-8 encoding
- Replace null values with empty strings if your export uses proprietary null representations

**Example source row (legacy vendor extract):**
```
vendor_code,vendor_name,vendor_type,federal_tax_number,pay_currency,standard_pay_days,payment_method,country_code
V-10042,Acme Office Supply Co,GOODS,12-3456789,USD,30,ACH,US
```

---

## 6. Output Description

**`<base_name>_mapping_output.csv`** — One row per mapping with:
- `Source_Column` — column from the legacy CSV
- `Target_Workday_Field` — recommended Workday field
- `Confidence` — HIGH / MEDIUM / LOW (Claude's assessment)
- `Transformation_Note` — any data transformation required (e.g., "Convert 2-char country code to full country name")
- `Data_Quality_Issue` — any data quality concern noted

**`<base_name>_mapping_report.md`** — Full Markdown report including:
- Field mapping table (suitable for pasting into a Confluence page or SharePoint)
- Unmapped source columns with notes
- Required Workday fields with no source mapping (action items)
- Executive summary paragraph

**Interpreting Confidence Levels:**
| Confidence | Meaning | Action |
|---|---|---|
| HIGH | Semantic match is clear | Accept with light review |
| MEDIUM | Likely match but needs validation | Validate with source system owner |
| LOW | Uncertain — Claude flagged for human review | Review and override manually |
| MANUAL | User-overridden in interactive mode | Already validated |

**Interactive Mode Overrides:**
When `--interactive` is used, after displaying Claude's suggestions the tool prompts for each mapping:
- Press **Enter** to accept the mapping as-is
- Type a **new field name** to override the target field
- Type **skip** to remove the mapping entirely

---

## 7. Integration with Workday

**Using Mapping Output in the Conversion Workplan:**
The `_mapping_report.md` is designed to be directly incorporated into the conversion design document. Copy the mapping table into Confluence or paste into a Word document.

**From Mapping to iLoad Template:**
1. Use the approved mappings to build an Excel iLoad template (one sheet per Workday object)
2. Write a Python or SQL transformation script using the `Transformation_Note` column as the spec
3. Populate the iLoad template from the legacy extract using the transformation script
4. Validate the populated template against the iLoad column definitions in Workday Community

**RaaS Validation:**
Before running the iLoad, validate reference field values (Supplier_Category, Account_Type, etc.) by calling the Workday RaaS for each reference object to get valid values:
```python
import requests
# GET https://<tenant>.workday.com/ccx/service/<tenant>/Revenue_Management/v1
# Use Get_Suppliers, Get_Customers, etc. to validate ref values
```

**EIB Load Process:**
1. Once the iLoad template is populated and validated, upload via Workday's EIB inbound integration
2. Use the **Load Supplier Data** or equivalent EIB for the target object
3. Review the EIB completion report for row-level errors

---

## 8. Agent Readiness Assessment

*Written from the perspective of the Conversion Sub-agent*

**Production Readiness: ★★★★☆**

**What's Ready for Immediate Use:**
- All six Workday objects are fully defined with required and optional fields, data types, and format notes
- PII stripping is automatic — safe to run on client data without manual pre-processing for common sensitive field names
- The Claude prompt is carefully engineered to return structured JSON every time
- Interactive mode gives the conversion analyst full control over the final mapping
- Output report is deliverable-quality Markdown

**What Needs Customization Per Client:**
- **Target object field lists:** The embedded field definitions cover standard Workday objects. If the client has custom fields (Workday Extend), those must be added to the `WORKDAY_OBJECTS` dict for each object
- **PII stripping patterns:** The default patterns cover common cases. Add client-specific sensitive column patterns before running on client data
- **Sampling strategy:** The tool uses the first 5 rows as samples. For large files with sparse data, increase the sample size or add a random sample option
- **Confidence thresholds:** LOW-confidence mappings should always be reviewed by the conversion analyst before including in the workplan

**Known Limitations:**
- Mapping quality depends on column name descriptiveness — poorly named legacy columns (e.g., `fld_027`) will produce low-confidence results
- Claude analyzes column names and sample values but does not have access to data dictionaries or source system documentation — provide those separately in a workshop
- The tool maps one source column to one target field — complex transformations involving multiple source columns (concatenation, lookups) are flagged in the transformation note but not automated
- Does not validate that mapped values exist in Workday reference data (use RaaS for that)

**Recommended Next Steps Before Client Deployment:**
1. Obtain a sample legacy extract (even 10 rows) from the source system
2. Run `--demo` to show the team what the output looks like before using client data
3. Review the `WORKDAY_OBJECTS` dict and add any client-specific custom fields
4. Add client-specific PII column patterns to `PII_PATTERNS` regex
5. Run the tool and review LOW-confidence mappings with the source system SME
6. Use `--interactive` in the mapping workshop to refine with the client's data team present

---

## 9. Deployment Checklist

- [ ] Python 3.10+ installed
- [ ] `pip install pandas anthropic tabulate` completed
- [ ] `ANTHROPIC_API_KEY` set and tested (`python -c "import anthropic; print('OK')"`)
- [ ] `--demo` run successfully
- [ ] Legacy source CSV obtained and reviewed for PII before running
- [ ] Target Workday object identified and confirmed with client
- [ ] Custom fields added to `WORKDAY_OBJECTS` if client has Workday Extend customizations
- [ ] Tool run against client sample extract
- [ ] LOW-confidence mappings reviewed with source system owner
- [ ] `_mapping_report.md` reviewed and incorporated into conversion workplan
- [ ] iLoad template built from approved mappings
- [ ] Transformation scripts written and tested against sample data

---

## 10. Practice Sharing Guidelines

**Sharing within the CoP:**
- Demonstrate using `--demo` only — never share client source data in CoP sessions
- The `_mapping_report.md` output is an excellent artifact to show at the CoP's bi-weekly knowledge share — it demonstrates immediate, tangible value to Conversion workstream leads
- Share lessons learned about which legacy systems have the cleanest column naming (and which don't)

**Sharing with Clients:**
- Position this as a "head start" tool, not a replacement for conversion workshops — the human review step is essential
- The `_mapping_output.csv` is the handoff artifact to the client's data team for iLoad template development
- Ensure the client understands that MEDIUM/LOW confidence mappings require human validation before use
- Provide the client with the Workday Community links to the iLoad templates for each object so they can cross-reference

**Contributing Improvements:**
- If you add a new Workday object definition to `WORKDAY_OBJECTS`, submit it to the Conversion Sub-agent lead
- If you find the Claude prompt produces poor results for a specific legacy system type, document the issue with a sample and submit to the CoP AI Solutions working group
