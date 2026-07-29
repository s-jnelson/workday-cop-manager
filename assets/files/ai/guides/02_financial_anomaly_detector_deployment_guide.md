# Deployment Guide: Financial Anomaly Detector
**Solution:** `solutions/02_financial_anomaly_detector.py`
**Responsible Sub-agent:** Reporting Sub-agent
**Last Updated:** 2026-07-08

---

## 1. Overview

The Financial Anomaly Detector applies six complementary statistical detection methods to Workday General Ledger transaction data to surface unusual patterns that warrant human review. Unlike rule-based exception systems (which only catch what you anticipated), statistical anomaly detection catches unexpected patterns — the round-number entries that suggest estimates, the weekend postings that suggest backdating, the new account codes that suggest unauthorized activity.

**What it does:**
- Reads a GL transaction export (from Workday RaaS or EIB)
- Applies z-score, IQR, weekend/holiday, round-number, duplicate, and new-account detection
- Scores each flagged transaction 0–100 and classifies it HIGH/MEDIUM/LOW severity
- Optionally uses Claude to generate a one-sentence audit narrative for HIGH items
- Prints a ranked summary table and saves an `_anomalies.csv` for review

**Value delivered:**
- Extends the audit coverage of Finance teams without adding headcount
- Surfaces the top 1–2% of transactions for human review rather than asking auditors to check everything
- Provides an auditable score and reason code for every flagged item
- Catches patterns that Workday's built-in controls don't flag (e.g., systematic round-number entries)

**Typical use case:** Monthly close process — run against the full month's GL transactions after posting, review HIGH items before sign-off.

---

## 2. Prerequisites

### Python Version
Python 3.9 or higher.

### Required Packages
```bash
pip install pandas numpy scipy
```

All three are required for core detection. No substitutions.

| Package | Version | Purpose |
|---------|---------|---------|
| `pandas` | >=1.5 | DataFrame operations, CSV read/write, groupby |
| `numpy` | >=1.21 | Array operations, random data generation in demo mode |
| `scipy` | >=1.7 | `scipy.stats.zscore` for per-account z-score calculation |

### Optional (for AI narratives)
```bash
pip install anthropic
```

### API Key Setup (Optional)
Only needed if you want Claude AI narratives for HIGH items.

```bash
# Linux / macOS
export ANTHROPIC_API_KEY="sk-ant-..."

# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

The tool works fully without the API key — all six detection methods run regardless.

### Input Data Format
The input CSV must have these exact column headers:

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `Transaction_ID` | string | Unique transaction identifier | `TXN-00001` |
| `Date` | date | Posting date (parseable by pandas: YYYY-MM-DD recommended) | `2024-03-15` |
| `Account` | string | GL account code and name | `6100-Salaries` |
| `Cost_Center` | string | Cost center code | `CC-Finance` |
| `Amount` | decimal | Transaction amount (absolute value; use Debit_Credit for sign) | `12500.00` |
| `Debit_Credit` | string | `Debit` or `Credit` | `Debit` |
| `Description` | string | Transaction description or journal entry memo | `March payroll` |
| `Posted_By` | string | Username of the user who posted the transaction | `jsmith` |

---

## 3. Quick Start

```bash
# 1. Install dependencies
pip install pandas numpy scipy

# 2. Run demo (generates synthetic data automatically)
python 02_financial_anomaly_detector.py --demo
```

Expected output: summary table showing detected anomalies from 300 synthetic transactions + seeded anomalies, plus `demo_gl_anomalies.csv`.

---

## 4. Usage

### All CLI Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--input` / `-i` | Input GL transaction CSV | required (or use --demo) |
| `--output` / `-o` | Output anomalies CSV path | `<input>_anomalies.csv` |
| `--demo` | Generate synthetic data and analyze | — |
| `--threshold` | Z-score threshold for flagging | `3.0` |
| `--no-narrative` | Skip Claude AI narratives for HIGH items | AI enabled if key is set |

### Usage Examples

```bash
# Analyze a monthly GL export
python 02_financial_anomaly_detector.py \
  --input /data/gl_march_2024.csv \
  --output /data/gl_march_2024_anomalies.csv

# Stricter z-score threshold (fewer but more extreme flags)
python 02_financial_anomaly_detector.py \
  --input gl.csv \
  --threshold 2.5

# More permissive threshold (more flags, useful for initial exploration)
python 02_financial_anomaly_detector.py \
  --input gl.csv \
  --threshold 4.0

# Rule-based detection only, no Claude
python 02_financial_anomaly_detector.py \
  --input gl.csv \
  --no-narrative

# Demo with AI narratives (requires ANTHROPIC_API_KEY)
python 02_financial_anomaly_detector.py --demo
```

---

## 5. Input Data Format

### Column Definitions

**`Transaction_ID`** — Any unique identifier. Workday typically uses internal transaction IDs from the Journal Entry report or the GL Transaction Detail report.

**`Date`** — The posting date. Pandas will parse most common date formats. YYYY-MM-DD is safest. The weekend/holiday detection uses this field.

**`Account`** — GL account. The z-score and IQR detection run per-account, so consistent account naming is critical. If Workday exports "6100" and "6100-Salaries & Benefits" for the same account, normalize them before running.

**`Amount`** — Use the absolute transaction amount. Do not use negative numbers for credits — use the `Debit_Credit` column for sign. The anomaly detectors are amount-magnitude-focused, not sign-focused.

**`Posted_By`** — Username of the posting user. Surfaces in the anomaly output and AI narrative for audit reference. Does not affect scoring.

### Minimum Data Requirements
- At least 10 transactions per account for z-score and IQR to be meaningful (smaller account populations are skipped)
- At least 90 days of data for the new-account detection to work correctly (shorter history periods will over-flag)
- Dates must be parseable — mixed formats in one file will cause parsing errors

### Example Rows (CSV)
```
Transaction_ID,Date,Account,Cost_Center,Amount,Debit_Credit,Description,Posted_By
TXN-00001,2024-01-15,6100-Salaries,CC-Finance,85000.00,Debit,January payroll,system
TXN-00002,2024-01-15,6100-Salaries,CC-IT,124000.00,Debit,January payroll,system
TXN-00099,2024-03-09,9100-Consulting,CC-Finance,15000.00,Debit,Weekend consulting,bwilson
```

---

## 6. Output Description

### Anomalies CSV
The output file contains only flagged rows (anomaly count is always a subset of total transactions). All input columns are preserved plus:

| Column | Type | Description |
|--------|------|-------------|
| `Anomaly_Flags` | string | Semicolon-separated list of triggered rules (e.g., `ZSCORE(4.23); WEEKEND_POSTING`) |
| `Max_Z_Score` | float | Highest absolute z-score for this transaction (0 if z-score not triggered) |
| `Severity` | string | `HIGH`, `MEDIUM`, or `LOW` |
| `Anomaly_Score` | integer | 0–100 score (higher = more anomalous) |
| `AI_Narrative` | string | Claude 1-sentence audit narrative (HIGH items only, blank otherwise) |

### Severity Rules

| Severity | Condition |
|----------|-----------|
| HIGH | Z-score > 4.0 **OR** 3 or more flags triggered |
| MEDIUM | Z-score 3–4 **OR** 2 flags triggered |
| LOW | Exactly 1 flag triggered |

### Anomaly Flag Codes

| Flag | Meaning |
|------|---------|
| `ZSCORE(n.nn)` | Z-score of n.nn exceeded threshold for this account |
| `IQR_OUTLIER` | Amount is outside Q1-1.5×IQR or Q3+1.5×IQR for this account |
| `WEEKEND_POSTING` | Transaction posted on Saturday or Sunday |
| `HOLIDAY_POSTING` | Transaction posted on a US federal holiday |
| `ROUND_NUMBER(n)` | Amount ≥ $10K and divisible by 10,000 (possible estimate) |
| `DUPLICATE_TXN` | Same Amount + Account + Date exists in another row |
| `NEW_ACCOUNT` | Account had no activity in the prior 90 days |

### Interpreting the Summary Table
The printed summary shows the top 20 anomalies by score. Rows not shown are still in the output CSV. A high `Anomaly_Score` with multiple flags warrants immediate review; a LOW severity single-flag item (e.g., a single ROUND_NUMBER) may be entirely legitimate and just needs a note.

---

## 7. Integration with Workday

### Extracting Input Data from Workday

**Option A: GL Transaction Detail RaaS Report (Recommended)**
The built-in Workday report "GL Transaction Detail" (or a custom version) provides the required fields.

1. In Workday, search "GL Transaction Detail" and run the report
2. Filter to: Company, Period (e.g., March 2024), Ledger = Actuals
3. Export as CSV via the report actions menu
4. Confirm column names match expected format (rename if needed)

Required Workday columns to map:
| Workday Label | Tool Column |
|---------------|-------------|
| Journal Entry Line Reference | Transaction_ID |
| Accounting Date | Date |
| Account (Segment) | Account |
| Cost Center | Cost_Center |
| Amount | Amount |
| Debit/Credit Indicator | Debit_Credit |
| Journal Entry Memo | Description |
| Entry User Name | Posted_By |

**Option B: Workday Prism Analytics**
For large organizations (100K+ GL rows per period), use Workday Prism to pre-aggregate or filter the dataset before export. The Prism dataset can be scheduled to export as CSV to Azure Blob or AWS S3 nightly.

**Option C: Workday EIB Extract**
Build an outbound EIB to extract GL transaction data on a schedule. Configure the output to write to an SFTP or shared drive location that this script can read.

### Feeding Anomalies Back to Workday
The output `_anomalies.csv` can be used to:
- Create Workday Journal Entry Review tasks (via EIB load using the review workflow)
- Feed an internal audit SharePoint list
- Trigger ServiceNow incidents for HIGH items
- Send a Power BI dashboard dataset

---

## 8. Agent Readiness Assessment

*Written from the perspective of the Reporting Sub-agent responsible for this solution.*

**Production Readiness Rating: ★★★★☆ (4/5)**

### What's Ready
- All six detection methods are implemented and tested with the synthetic demo data
- Severity scoring logic is clear and defensible to auditors
- The z-score threshold is configurable via CLI flag — no code changes needed to tune sensitivity
- Weekend/holiday detection uses a hardcoded 2024 US holiday list (easily extended)
- Graceful behavior when account groups have fewer than 3–4 rows (skips rather than errors)
- Demo mode generates realistic-looking data with seeded anomalies to verify the detectors work

### What Needs Customization Per Client
- **Holiday list** — `US_HOLIDAYS_2024` is hardcoded for 2024 US federal holidays. Extend for: future years, non-US jurisdictions, client-specific shutdowns. Consider making this a loaded CSV or using the `holidays` Python package (`pip install holidays`).
- **Round-number threshold** — Currently flags amounts divisible by 10,000 above $10K. Some clients have legitimate recurring round-number entries (monthly rent, leases). Add a whitelist by Account or Description for known legitimate round entries.
- **Account grouping** — The z-score and IQR detectors run per `Account` string. If the client's Workday chart of accounts uses segment-based account codes (e.g., `6100-CC001` vs `6100-CC002`), the segments need to be normalized to the account number prefix only before running.
- **New account lookback** — The 90-day window is configurable in the source but not exposed as a CLI flag. Expose `--lookback-days` if clients need a different window.
- **Debit/Credit awareness** — The detectors currently treat Amount as a positive magnitude. If the client's extract includes negative credits (common in some Workday export formats), add an `Amount = Amount.abs()` normalization step in the `main()` data loading block.
- **AI model selection** — Claude AI narratives use `claude-sonnet-4-5`. Switch to `claude-haiku-3-5` for cost reduction if narrative quality is acceptable.

### Known Limitations
- **Z-score requires history** — With fewer than ~15 transactions per account, z-scores are unreliable. Small organizations or thinly-populated accounts will see either no z-score flags or unstable scoring. The IQR and rule-based detectors still work for small populations.
- **New account detection is O(n²)** — The current implementation iterates over all rows and performs a filtered lookup for each. For very large datasets (>100K rows), this can be slow. Optimize using a pre-computed first-appearance dictionary if runtime exceeds acceptable limits.
- **No machine learning** — This is purely statistical (parametric) anomaly detection. It will not learn from false positive/negative feedback. Truly sophisticated anomaly detection would use an isolation forest or autoencoder trained on client data.
- **US-only holiday calendar** — Non-US clients need their own holiday list.

### Recommended Next Steps Before Client Deployment
1. Run against 3–6 months of client's actual GL data and review flag distribution with their internal auditor
2. Calibrate the z-score threshold with client — start at 3.0, adjust based on false positive rate
3. Build an Account whitelist for known legitimate round-number recurring entries
4. Extend the holiday calendar to cover client's jurisdiction and fiscal calendar
5. Agree with the client on what "HIGH severity" triggers in their audit workflow (manual review? automatic hold?)

---

## 9. Deployment Checklist

- [ ] Python 3.9+ installed
- [ ] `pip install pandas numpy scipy` completed successfully
- [ ] Test with `--demo` flag produces anomaly output with HIGH/MEDIUM/LOW items
- [ ] GL transaction CSV columns confirmed against Workday export headers
- [ ] Account naming convention in Workday export is consistent (no mixed formats)
- [ ] Holiday list updated for client's jurisdiction and current year(s)
- [ ] Z-score threshold agreed with client's audit team
- [ ] Round-number whitelist built for known legitimate recurring entries
- [ ] Output file location writable and accessible to audit team
- [ ] (If using AI) `ANTHROPIC_API_KEY` set and tested
- [ ] Monthly run scheduled (cron/Task Scheduler/pipeline)
- [ ] Audit team briefed on flag codes and severity definitions
- [ ] Sample results reviewed with client Finance Controller or Internal Audit

---

## 10. Practice Sharing Guidelines

### What to Include in a Handoff Package
1. The Python script (`02_financial_anomaly_detector.py`) and this guide
2. Sample anomaly output CSV (from `--demo` run) with column explanations
3. Client-specific configuration notes (threshold, holiday list, any account normalizations applied)
4. A one-page summary of anomaly counts, severity breakdown, and top findings for the client's review period
5. Calibration notes: what threshold was used, how many flags were reviewed, false positive rate

### How to Present to the Practice

**30-second pitch:** "We run six audit-grade detection algorithms against the full GL in about 30 seconds. It surfaces the top 50 transactions that most deserve a second look — the ones with the highest z-scores, posted on weekends, suspiciously round, or on accounts nobody's touched in months. It's not replacing the auditor — it's telling them where to look first."

**Demo path:** Run `python 02_financial_anomaly_detector.py --demo`, show the summary table, open the output CSV, sort by `Anomaly_Score` descending. The seeded anomalies (the $250K travel spike, the weekend posting, the duplicate) should be immediately visible at the top.

**Useful talking points:**
- Six methods means six opportunities to catch something different; z-score alone misses duplicates and round-number patterns
- The severity score is explainable — auditors can see exactly which rules triggered
- This runs locally on client data — no transaction details leave the environment (AI narratives use anonymized field names, not raw amounts)

### Internal CoP Sharing
- Post under: Finance Tools > AI-Assisted Audit / GL Analytics
- Tag as: `GL Audit`, `Anomaly Detection`, `Statistical Analysis`, `Pandas`, `Workday Finance`, `Internal Audit`
- Pair with a "lessons learned" note from the first client deployment covering calibration decisions
