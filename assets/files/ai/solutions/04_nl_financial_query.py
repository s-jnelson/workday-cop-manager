#!/usr/bin/env python3
"""
Workday Natural Language Financial Query Tool
===============================================
Type a natural language financial question → Claude maps it to a Workday RaaS
(Reports as a Service) query → returns simulated results from embedded sample data.

Usage:
    python 04_nl_financial_query.py           # Interactive REPL
    python 04_nl_financial_query.py --demo    # Run 5 example queries automatically
    python 04_nl_financial_query.py --list    # List all available reports
    python 04_nl_financial_query.py --help
"""

import argparse
import json
import os
import sys
import textwrap
from typing import Optional

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("WARNING: anthropic package not installed. Run: pip install anthropic")

# ---------------------------------------------------------------------------
# RaaS Report Catalog with sample data
# ---------------------------------------------------------------------------

RAAS_CATALOG = {
    "vendor_spend_by_period": {
        "description": "Top vendors ranked by total spend for a given date range. Shows invoice count and total amount per supplier.",
        "url_template": "https://{tenant}.workday.com/ccx/service/customreport2/{tenant}/ISU_Reporting/Vendor_Spend_By_Period?Company={company}&From_Date={from_date}&To_Date={to_date}&Limit={limit}&format=json",
        "parameters": {
            "company": "Workday Company reference (e.g., Acme_Corp)",
            "from_date": "Start date YYYY-MM-DD",
            "to_date": "End date YYYY-MM-DD",
            "limit": "Number of top vendors to return (default: 10)",
        },
        "sample_data": [
            {"rank": 1, "vendor": "TechCorp Solutions", "spend": 2_850_000, "invoice_count": 48, "avg_invoice": 59_375},
            {"rank": 2, "vendor": "Global Facilities Inc", "spend": 1_920_000, "invoice_count": 24, "avg_invoice": 80_000},
            {"rank": 3, "vendor": "DataStream Analytics", "spend": 1_245_000, "invoice_count": 12, "avg_invoice": 103_750},
            {"rank": 4, "vendor": "Office Essentials Ltd", "spend": 875_000, "invoice_count": 156, "avg_invoice": 5_609},
            {"rank": 5, "vendor": "CloudFirst Infrastructure", "spend": 760_000, "invoice_count": 36, "avg_invoice": 21_111},
            {"rank": 6, "vendor": "HR Advisory Partners", "spend": 620_000, "invoice_count": 8, "avg_invoice": 77_500},
            {"rank": 7, "vendor": "PrintMaster Corp", "spend": 445_000, "invoice_count": 89, "avg_invoice": 4_999},
            {"rank": 8, "vendor": "SecureNet Services", "spend": 380_000, "invoice_count": 12, "avg_invoice": 31_667},
            {"rank": 9, "vendor": "Apex Catering Group", "spend": 295_000, "invoice_count": 52, "avg_invoice": 5_673},
            {"rank": 10, "vendor": "Legal & Compliance Co", "spend": 240_000, "invoice_count": 6, "avg_invoice": 40_000},
        ],
    },

    "ap_aging_summary": {
        "description": "Accounts Payable aging buckets showing outstanding invoices by age (current, 1-30, 31-60, 61-90, 90+ days past due).",
        "url_template": "https://{tenant}.workday.com/ccx/service/customreport2/{tenant}/ISU_Reporting/AP_Aging_Summary?Company={company}&As_Of_Date={as_of_date}&format=json",
        "parameters": {
            "company": "Workday Company reference",
            "as_of_date": "Aging as-of date YYYY-MM-DD",
        },
        "sample_data": [
            {"bucket": "Current (not yet due)", "amount": 4_250_000, "invoice_count": 87, "pct_of_total": 52.4},
            {"bucket": "1–30 Days Past Due", "amount": 1_850_000, "invoice_count": 34, "pct_of_total": 22.8},
            {"bucket": "31–60 Days Past Due", "amount": 980_000, "invoice_count": 19, "pct_of_total": 12.1},
            {"bucket": "61–90 Days Past Due", "amount": 560_000, "invoice_count": 11, "pct_of_total": 6.9},
            {"bucket": "Over 90 Days Past Due", "amount": 470_000, "invoice_count": 9, "pct_of_total": 5.8},
            {"bucket": "TOTAL", "amount": 8_110_000, "invoice_count": 160, "pct_of_total": 100.0},
        ],
    },

    "gl_trial_balance": {
        "description": "General Ledger trial balance showing debit and credit balances by account for a specified accounting period.",
        "url_template": "https://{tenant}.workday.com/ccx/service/customreport2/{tenant}/ISU_Reporting/GL_Trial_Balance?Company={company}&Period={period}&Ledger={ledger}&format=json",
        "parameters": {
            "company": "Workday Company reference",
            "period": "Accounting period (e.g., Q1_2024, Jan_2024)",
            "ledger": "Ledger type (e.g., Actuals, Budget)",
        },
        "sample_data": [
            {"account": "1000-Cash & Equivalents", "type": "Asset", "debit": 5_200_000, "credit": 0, "net": 5_200_000},
            {"account": "1200-Accounts Receivable", "type": "Asset", "debit": 8_750_000, "credit": 0, "net": 8_750_000},
            {"account": "1500-Prepaid Expenses", "type": "Asset", "debit": 425_000, "credit": 0, "net": 425_000},
            {"account": "2000-Accounts Payable", "type": "Liability", "debit": 0, "credit": 3_180_000, "net": -3_180_000},
            {"account": "2100-Accrued Liabilities", "type": "Liability", "debit": 0, "credit": 890_000, "net": -890_000},
            {"account": "3000-Retained Earnings", "type": "Equity", "debit": 0, "credit": 12_450_000, "net": -12_450_000},
            {"account": "4000-Revenue", "type": "Revenue", "debit": 0, "credit": 18_600_000, "net": -18_600_000},
            {"account": "5000-Cost of Goods Sold", "type": "Expense", "debit": 9_300_000, "credit": 0, "net": 9_300_000},
            {"account": "6100-Salaries & Benefits", "type": "Expense", "debit": 4_800_000, "credit": 0, "net": 4_800_000},
            {"account": "7100-Travel & Entertainment", "type": "Expense", "debit": 625_000, "credit": 0, "net": 625_000},
        ],
    },

    "budget_vs_actual": {
        "description": "Budget vs. actual spend comparison by cost center, showing variance and percent attainment for a given period.",
        "url_template": "https://{tenant}.workday.com/ccx/service/customreport2/{tenant}/ISU_Reporting/Budget_vs_Actual?Company={company}&Period={period}&Cost_Center_Hierarchy={cost_center_hierarchy}&format=json",
        "parameters": {
            "company": "Workday Company reference",
            "period": "Period or date range",
            "cost_center_hierarchy": "Cost center or hierarchy node",
        },
        "sample_data": [
            {"cost_center": "CC-Finance", "budget": 850_000, "actual": 802_400, "variance": 47_600, "pct_used": 94.4},
            {"cost_center": "CC-IT", "budget": 2_100_000, "actual": 2_340_000, "variance": -240_000, "pct_used": 111.4},
            {"cost_center": "CC-Marketing", "budget": 1_500_000, "actual": 1_285_000, "variance": 215_000, "pct_used": 85.7},
            {"cost_center": "CC-Operations", "budget": 3_200_000, "actual": 3_198_500, "variance": 1_500, "pct_used": 100.0},
            {"cost_center": "CC-HR", "budget": 620_000, "actual": 545_000, "variance": 75_000, "pct_used": 87.9},
            {"cost_center": "CC-Sales", "budget": 1_800_000, "actual": 1_920_000, "variance": -120_000, "pct_used": 106.7},
            {"cost_center": "CC-Legal", "budget": 450_000, "actual": 398_000, "variance": 52_000, "pct_used": 88.4},
            {"cost_center": "TOTAL", "budget": 10_520_000, "actual": 10_488_900, "variance": 31_100, "pct_used": 99.7},
        ],
    },

    "expense_by_category": {
        "description": "Employee expense spend broken down by expense category for a given date range, sorted by total spend.",
        "url_template": "https://{tenant}.workday.com/ccx/service/customreport2/{tenant}/ISU_Reporting/Expense_By_Category?Company={company}&From_Date={from_date}&To_Date={to_date}&format=json",
        "parameters": {
            "company": "Workday Company reference",
            "from_date": "Start date YYYY-MM-DD",
            "to_date": "End date YYYY-MM-DD",
        },
        "sample_data": [
            {"category": "Airfare", "amount": 485_000, "reports": 342, "avg_report": 1_418, "top_spender": "Sales Team"},
            {"category": "Hotels & Lodging", "amount": 398_000, "reports": 398, "avg_report": 1_000, "top_spender": "Consulting"},
            {"category": "Meals & Entertainment", "amount": 245_000, "reports": 1_204, "avg_report": 203, "top_spender": "Sales Team"},
            {"category": "Ground Transportation", "amount": 124_000, "reports": 892, "avg_report": 139, "top_spender": "Operations"},
            {"category": "Software & Subscriptions", "amount": 98_000, "reports": 145, "avg_report": 676, "top_spender": "IT"},
            {"category": "Training & Conferences", "amount": 87_000, "reports": 89, "avg_report": 978, "top_spender": "HR"},
            {"category": "Office Supplies", "amount": 34_000, "reports": 456, "avg_report": 75, "top_spender": "All Depts"},
            {"category": "Miscellaneous", "amount": 28_000, "reports": 234, "avg_report": 120, "top_spender": "Various"},
        ],
    },

    "ar_aging_summary": {
        "description": "Accounts Receivable aging showing outstanding customer balances by days outstanding.",
        "url_template": "https://{tenant}.workday.com/ccx/service/customreport2/{tenant}/ISU_Reporting/AR_Aging_Summary?Company={company}&As_Of_Date={as_of_date}&format=json",
        "parameters": {
            "company": "Workday Company reference",
            "as_of_date": "Aging as-of date YYYY-MM-DD",
        },
        "sample_data": [
            {"bucket": "Current (not yet due)", "amount": 8_450_000, "customers": 42, "pct_of_total": 61.2},
            {"bucket": "1–30 Days Past Due", "amount": 2_890_000, "customers": 18, "pct_of_total": 20.9},
            {"bucket": "31–60 Days Past Due", "amount": 1_120_000, "customers": 7, "pct_of_total": 8.1},
            {"bucket": "61–90 Days Past Due", "amount": 560_000, "customers": 4, "pct_of_total": 4.1},
            {"bucket": "Over 90 Days Past Due (Bad Debt Risk)", "amount": 800_000, "customers": 3, "pct_of_total": 5.8},
            {"bucket": "TOTAL", "amount": 13_820_000, "customers": 74, "pct_of_total": 100.0},
        ],
    },

    "fixed_asset_register": {
        "description": "Fixed asset register showing assets by class with acquisition cost, accumulated depreciation, and net book value.",
        "url_template": "https://{tenant}.workday.com/ccx/service/customreport2/{tenant}/ISU_Reporting/Fixed_Asset_Register?Company={company}&As_Of_Date={as_of_date}&format=json",
        "parameters": {
            "company": "Workday Company reference",
            "as_of_date": "Report as-of date YYYY-MM-DD",
        },
        "sample_data": [
            {"asset_class": "Buildings & Leasehold", "count": 8, "cost": 12_500_000, "accum_depr": 4_200_000, "nbv": 8_300_000},
            {"asset_class": "Computer Equipment", "count": 284, "cost": 3_850_000, "accum_depr": 2_100_000, "nbv": 1_750_000},
            {"asset_class": "Furniture & Fixtures", "count": 156, "cost": 1_200_000, "accum_depr": 620_000, "nbv": 580_000},
            {"asset_class": "Software Licenses", "count": 45, "cost": 2_400_000, "accum_depr": 1_800_000, "nbv": 600_000},
            {"asset_class": "Vehicles", "count": 12, "cost": 580_000, "accum_depr": 290_000, "nbv": 290_000},
            {"asset_class": "Lab & Test Equipment", "count": 28, "cost": 4_200_000, "accum_depr": 1_050_000, "nbv": 3_150_000},
            {"asset_class": "TOTAL", "count": 533, "cost": 24_730_000, "accum_depr": 10_060_000, "nbv": 14_670_000},
        ],
    },
}

# ---------------------------------------------------------------------------
# Demo queries
# ---------------------------------------------------------------------------

DEMO_QUERIES = [
    "Who are our top 5 vendors by spend this quarter?",
    "Show me how our AP aging looks as of today",
    "Which cost centers are over budget?",
    "What did we spend on travel and meals last month?",
    "What is the net book value of our fixed assets?",
]

# ---------------------------------------------------------------------------
# Claude: map question to report
# ---------------------------------------------------------------------------

def map_query_to_report(client: "anthropic.Anthropic", user_question: str) -> dict:
    """Ask Claude to identify the best matching report and extract parameters."""

    catalog_summary = "\n".join([
        f"- {name}: {info['description']} | params: {list(info['parameters'].keys())}"
        for name, info in RAAS_CATALOG.items()
    ])

    prompt = f"""You are a Workday Reporting expert. A finance user has asked a question.
Your job is to identify which Workday RaaS (Reports as a Service) report best answers their question,
and extract any parameter values they mentioned.

Available reports:
{catalog_summary}

User question: "{user_question}"

Respond with valid JSON only (no markdown, no explanation outside the JSON):
{{
  "report": "<report_name or null if no match>",
  "params": {{
    "<param_name>": "<value or null if not mentioned>"
  }},
  "interpretation": "<1 sentence: what this report will show for their question>",
  "confidence": "high|medium|low",
  "confidence_reason": "<brief reason for confidence level>"
}}

Use today's date 2024-03-31 as default for date parameters if not specified.
Use "Acme_Corp" as default company if not specified.
Set confidence to "low" if the question doesn't clearly match any report."""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        return {
            "report": None,
            "params": {},
            "interpretation": "Could not parse response",
            "confidence": "low",
            "confidence_reason": f"JSON parse error: {exc}",
        }
    except Exception as exc:
        return {
            "report": None,
            "params": {},
            "interpretation": "Claude API error",
            "confidence": "low",
            "confidence_reason": str(exc),
        }


# ---------------------------------------------------------------------------
# Results formatting
# ---------------------------------------------------------------------------

def format_currency(value) -> str:
    """Format a number as USD currency string."""
    try:
        v = float(value)
        if abs(v) >= 1_000_000:
            return f"${v/1_000_000:,.1f}M"
        elif abs(v) >= 1_000:
            return f"${v/1_000:,.0f}K"
        else:
            return f"${v:,.0f}"
    except (TypeError, ValueError):
        return str(value)


def print_results_table(report_name: str, sample_data: list[dict], params: dict) -> None:
    """Print simulated results as a formatted table."""
    if not sample_data:
        print("  [No sample data available for this report]")
        return

    headers = list(sample_data[0].keys())
    col_widths = {h: max(len(str(h)), max(len(str(row.get(h, ""))) for row in sample_data)) + 2
                  for h in headers}

    # Cap column width at 30
    col_widths = {h: min(w, 30) for h, w in col_widths.items()}

    # Header row
    header_line = "  " + "  ".join(str(h).ljust(col_widths[h]) for h in headers)
    print(header_line)
    print("  " + "-" * (sum(col_widths.values()) + len(headers) * 2))

    for row in sample_data:
        cells = []
        for h in headers:
            val = row.get(h, "")
            # Format currency fields
            if isinstance(val, (int, float)) and any(
                kw in h.lower() for kw in ["amount", "spend", "budget", "actual", "cost", "debit", "credit", "net", "nbv", "avg"]
            ):
                cell = format_currency(val)
            elif isinstance(val, float) and "pct" in h.lower():
                cell = f"{val:.1f}%"
            else:
                cell = str(val)
            cells.append(cell[:col_widths[h]].ljust(col_widths[h]))
        print("  " + "  ".join(cells))


def list_catalog() -> None:
    """Print all available reports from the catalog."""
    print("\n" + "=" * 65)
    print("AVAILABLE WORKDAY RAAS REPORTS")
    print("=" * 65)
    for name, info in RAAS_CATALOG.items():
        print(f"\n{name}")
        print(f"  {info['description']}")
        print(f"  Parameters: {', '.join(info['parameters'].keys())}")
    print()


# ---------------------------------------------------------------------------
# Query processing
# ---------------------------------------------------------------------------

def process_query(client: "anthropic.Anthropic", question: str) -> None:
    """Map a question to a report and display results."""
    print(f"\nQuestion: {question}")
    print("Mapping to Workday RaaS report...")

    mapping = map_query_to_report(client, question)

    report_name = mapping.get("report")
    params = mapping.get("params", {})
    interpretation = mapping.get("interpretation", "")
    confidence = mapping.get("confidence", "low")
    confidence_reason = mapping.get("confidence_reason", "")

    if confidence == "low" or not report_name or report_name not in RAAS_CATALOG:
        print("\n" + "=" * 65)
        print("LOW CONFIDENCE — Could not confidently match your question.")
        print("=" * 65)
        print(f"\nYour question: {question}")
        if confidence_reason:
            print(f"Reason: {confidence_reason}")
        print("\nPlease try rephrasing, or choose from these reports:")
        for name, info in RAAS_CATALOG.items():
            print(f"  - {name}: {info['description'][:60]}...")
        return

    report_info = RAAS_CATALOG[report_name]

    print("\n" + "=" * 65)
    print(f"MATCHED REPORT: {report_name}")
    print("=" * 65)
    print(f"Confidence:     {confidence.upper()} — {confidence_reason}")
    print(f"Interpretation: {interpretation}")
    print()
    print("Parameters:")
    for param, value in params.items():
        if value:
            print(f"  {param}: {value}")
    print()
    print("Simulated RaaS URL (replace {{tenant}} with your Workday tenant):")
    url = report_info["url_template"]
    for param, value in params.items():
        if value:
            url = url.replace(f"{{{param}}}", str(value))
    print(f"  {url}")
    print()
    print("SIMULATED RESULTS (from embedded sample data):")
    print("-" * 65)
    print_results_table(report_name, report_info["sample_data"], params)
    print()
    print("NOTE: These are sample/illustrative values, not live Workday data.")
    print("      Connect to your Workday tenant using the URL above for real data.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Workday Natural Language Financial Query — ask finance questions, get RaaS report mappings.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive REPL (recommended):
  python 04_nl_financial_query.py

  # Run 5 demo queries automatically:
  python 04_nl_financial_query.py --demo

  # List all available reports:
  python 04_nl_financial_query.py --list

Example questions you can ask:
  "Who are our top 10 vendors by spend in Q1?"
  "Show me AP aging as of March 31"
  "Which cost centers are over budget this year?"
  "What did we spend on employee expenses last quarter?"
  "What's the net book value of our fixed assets?"
  "Show me accounts receivable aging"
  "Give me a trial balance for Q4"
        """,
    )
    parser.add_argument("--demo", action="store_true", help="Run 5 example queries automatically.")
    parser.add_argument("--list", action="store_true", help="List all available reports and exit.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.list:
        list_catalog()
        return

    # Check API key
    if not ANTHROPIC_AVAILABLE:
        print("ERROR: anthropic package not installed.")
        print("Run: pip install anthropic")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        print("Set it with: export ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print("=" * 65)
    print("Workday Natural Language Financial Query Tool")
    print("=" * 65)
    print("Ask any financial question in plain English.")
    print("Claude will map it to a Workday RaaS report and show sample results.")
    print("Type 'list' to see all reports. Type 'quit' or 'exit' to stop.")
    print()

    if args.demo:
        print("DEMO MODE: Running 5 example queries...\n")
        for i, question in enumerate(DEMO_QUERIES, 1):
            print(f"[{i}/5] {'-'*50}")
            process_query(client, question)
            print()
        print("Demo complete.")
        return

    # Interactive REPL loop
    while True:
        try:
            print("-" * 65)
            user_input = input("Your question: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        if user_input.lower() == "list":
            list_catalog()
            continue

        process_query(client, user_input)
        print()


if __name__ == "__main__":
    main()
