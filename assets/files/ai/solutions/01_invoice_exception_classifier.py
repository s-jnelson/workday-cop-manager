#!/usr/bin/env python3
"""
Workday AP Invoice Exception Classifier
========================================
Classifies Workday Accounts Payable invoice exceptions using rule-based routing
and optional Claude AI-generated plain-English explanations for approvers.

Usage:
    python 01_invoice_exception_classifier.py --input invoices.csv --output results.csv
    python 01_invoice_exception_classifier.py --demo
    python 01_invoice_exception_classifier.py --input invoices.csv --no-ai
    python 01_invoice_exception_classifier.py --help
"""

import argparse
import csv
import io
import os
import sys
import warnings
from datetime import datetime, timezone
from typing import Optional

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration: Exception types and resolver routing matrix
# ---------------------------------------------------------------------------

EXCEPTION_TYPES = {
    "DUPLICATE": "Potential duplicate invoice detected — same supplier, amount, or invoice number already exists in the system.",
    "PRICE_VARIANCE": "Invoice unit price differs from the PO agreed price beyond the accepted tolerance.",
    "QUANTITY_MISMATCH": "Quantity invoiced does not match quantity received or quantity on the purchase order.",
    "MISSING_PO": "Invoice cannot be matched to a valid purchase order in Workday.",
    "MISSING_RECEIPT": "Goods receipt or service confirmation has not been recorded in the system.",
    "TAX_DISCREPANCY": "Tax amount on invoice does not align with jurisdiction rules or PO tax terms.",
    "CURRENCY_MISMATCH": "Invoice currency differs from PO or supplier agreement currency.",
    "EARLY_PAYMENT": "Invoice payment date falls before contractual payment terms allow.",
    "OVER_BUDGET": "Approving this invoice would exceed the cost center or project budget.",
    "UNAPPROVED_SUPPLIER": "Supplier is not on the approved vendor list or has a compliance hold.",
}

# resolver_role: who owns it by default
# escalate_above: USD amount threshold requiring director escalation
# sla_hours: hours by which exception must be resolved
RESOLVER_MATRIX = {
    "DUPLICATE": {
        "resolver_role": "AP Specialist",
        "escalate_above": 50_000,
        "sla_hours": 24,
    },
    "PRICE_VARIANCE": {
        "resolver_role": "Procurement Analyst",
        "escalate_above": 25_000,
        "sla_hours": 48,
    },
    "QUANTITY_MISMATCH": {
        "resolver_role": "Receiving/Warehouse Manager",
        "escalate_above": 10_000,
        "sla_hours": 48,
    },
    "MISSING_PO": {
        "resolver_role": "Budget Owner / Requestor",
        "escalate_above": 5_000,
        "sla_hours": 72,
    },
    "MISSING_RECEIPT": {
        "resolver_role": "Receiving/Warehouse Manager",
        "escalate_above": 10_000,
        "sla_hours": 48,
    },
    "TAX_DISCREPANCY": {
        "resolver_role": "Tax Analyst",
        "escalate_above": 1_000,
        "sla_hours": 72,
    },
    "CURRENCY_MISMATCH": {
        "resolver_role": "Treasury / AP Supervisor",
        "escalate_above": 0,  # always escalate
        "sla_hours": 24,
    },
    "EARLY_PAYMENT": {
        "resolver_role": "AP Manager",
        "escalate_above": 100_000,
        "sla_hours": 24,
    },
    "OVER_BUDGET": {
        "resolver_role": "Finance Business Partner",
        "escalate_above": 10_000,
        "sla_hours": 24,
    },
    "UNAPPROVED_SUPPLIER": {
        "resolver_role": "Procurement Compliance",
        "escalate_above": 0,  # always escalate
        "sla_hours": 12,
    },
}

# ---------------------------------------------------------------------------
# Demo data (5 sample invoice exceptions)
# ---------------------------------------------------------------------------

DEMO_ROWS = [
    {
        "Invoice_ID": "INV-2024-00441",
        "Supplier": "Acme Office Supplies LLC",
        "Amount": "12500.00",
        "Currency": "USD",
        "Invoice_Date": "2024-03-15",
        "PO_Reference": "PO-2024-0872",
        "Exception_Type": "PRICE_VARIANCE",
        "Exception_Detail": "Unit price $125.00 vs PO price $98.50. Variance 26.9%.",
    },
    {
        "Invoice_ID": "INV-2024-00098",
        "Supplier": "Global Tech Solutions",
        "Amount": "87500.00",
        "Currency": "USD",
        "Invoice_Date": "2024-03-18",
        "PO_Reference": "",
        "Exception_Type": "MISSING_PO",
        "Exception_Detail": "No purchase order found. Vendor claims verbal approval from IT Director.",
    },
    {
        "Invoice_ID": "INV-2024-00332",
        "Supplier": "FastShip Logistics",
        "Amount": "4250.75",
        "Currency": "USD",
        "Invoice_Date": "2024-03-20",
        "PO_Reference": "PO-2024-0654",
        "Exception_Type": "DUPLICATE",
        "Exception_Detail": "Matches INV-2024-00298 on same supplier, same amount, same PO within 7 days.",
    },
    {
        "Invoice_ID": "INV-2024-00509",
        "Supplier": "Sunrise Catering Co",
        "Amount": "3800.00",
        "Currency": "EUR",
        "Invoice_Date": "2024-03-22",
        "PO_Reference": "PO-2024-0901",
        "Exception_Type": "CURRENCY_MISMATCH",
        "Exception_Detail": "PO issued in USD but invoice submitted in EUR. FX rate not locked.",
    },
    {
        "Invoice_ID": "INV-2024-00717",
        "Supplier": "BuildRight Contractors",
        "Amount": "245000.00",
        "Currency": "USD",
        "Invoice_Date": "2024-03-25",
        "PO_Reference": "PO-2024-0450",
        "Exception_Type": "OVER_BUDGET",
        "Exception_Detail": "Remaining budget for CC-0045 is $180,000. Invoice exceeds by $65,000.",
    },
]

# ---------------------------------------------------------------------------
# PII scrubbing helpers
# ---------------------------------------------------------------------------

def bucket_amount(amount: float) -> str:
    """Return a broad bucket label rather than exact amount."""
    if amount < 1_000:
        return "under $1K"
    elif amount < 5_000:
        return "$1K–$5K"
    elif amount < 25_000:
        return "$5K–$25K"
    elif amount < 100_000:
        return "$25K–$100K"
    elif amount < 500_000:
        return "$100K–$500K"
    else:
        return "over $500K"


def scrub_row_for_prompt(row: dict) -> dict:
    """Return a prompt-safe version of the row with PII/exact amounts removed."""
    try:
        amount = float(row.get("Amount", 0))
    except ValueError:
        amount = 0.0

    return {
        "Invoice_ID": row.get("Invoice_ID", "UNKNOWN"),
        "Supplier_Ref": f"Supplier-{hash(row.get('Supplier', '')) % 9999:04d}",
        "Amount_Bucket": bucket_amount(amount),
        "Currency": row.get("Currency", "USD"),
        "Invoice_Date": row.get("Invoice_Date", ""),
        "PO_Reference": row.get("PO_Reference", "N/A") or "N/A",
        "Exception_Type": row.get("Exception_Type", "UNKNOWN"),
        "Exception_Detail": row.get("Exception_Detail", ""),
    }


# ---------------------------------------------------------------------------
# Rule-based classification
# ---------------------------------------------------------------------------

def classify_rule_based(row: dict) -> dict:
    """Apply rule-based routing from RESOLVER_MATRIX."""
    exception_type = row.get("Exception_Type", "").strip().upper()

    try:
        amount = float(row.get("Amount", 0))
    except (ValueError, TypeError):
        amount = 0.0

    if exception_type not in RESOLVER_MATRIX:
        return {
            "Assigned_To": "AP Manager (Unclassified)",
            "Escalate_To_Director": False,
            "SLA_Hours": 48,
            "Classification_Confidence": "LOW",
        }

    matrix = RESOLVER_MATRIX[exception_type]
    escalate = amount > matrix["escalate_above"] if matrix["escalate_above"] > 0 else True

    return {
        "Assigned_To": matrix["resolver_role"],
        "Escalate_To_Director": escalate,
        "SLA_Hours": matrix["sla_hours"],
        "Classification_Confidence": "HIGH",
    }


# ---------------------------------------------------------------------------
# Claude AI explanation generator
# ---------------------------------------------------------------------------

def generate_ai_explanation(client: "anthropic.Anthropic", row: dict) -> str:
    """Call Claude to produce a 2-3 sentence plain-English explanation for approvers."""
    safe = scrub_row_for_prompt(row)
    exception_type = safe["Exception_Type"]
    exception_desc = EXCEPTION_TYPES.get(exception_type, "An exception has been flagged.")

    prompt = f"""You are an AP (Accounts Payable) assistant helping finance approvers understand invoice exceptions.

Invoice exception details (PII has been masked):
- Invoice: {safe['Invoice_ID']}
- Supplier Reference: {safe['Supplier_Ref']} (name masked for privacy)
- Amount Range: {safe['Amount_Bucket']}
- Currency: {safe['Currency']}
- Invoice Date: {safe['Invoice_Date']}
- PO Reference: {safe['PO_Reference']}
- Exception Type: {exception_type}
- Exception Category Description: {exception_desc}
- Specific Detail: {safe['Exception_Detail']}

Write 2-3 sentences in plain English for a non-technical finance approver explaining:
1. What the problem is and why it was flagged
2. What action the approver needs to take

Use clear, professional language. Do not use technical jargon. Do not mention specific dollar amounts or supplier names. Keep it concise."""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as exc:
        return f"[AI explanation unavailable: {exc}]"


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------

def process_rows(rows: list[dict], use_ai: bool, client: Optional["anthropic.Anthropic"]) -> list[dict]:
    """Process a list of invoice rows, returning enriched output rows."""
    results = []
    processed_at = datetime.now(timezone.utc).isoformat()

    for i, row in enumerate(rows, start=1):
        print(f"  Processing row {i}/{len(rows)}: {row.get('Invoice_ID', 'N/A')} "
              f"({row.get('Exception_Type', 'UNKNOWN')})", end="", flush=True)

        classification = classify_rule_based(row)

        if use_ai and client is not None:
            print(" [AI]", end="", flush=True)
            ai_explanation = generate_ai_explanation(client, row)
        else:
            exception_type = row.get("Exception_Type", "UNKNOWN").upper()
            ai_explanation = EXCEPTION_TYPES.get(
                exception_type,
                "This invoice has been flagged for manual review. Please contact your AP team for details."
            )

        print()  # newline after status

        output_row = {**row}
        output_row["Assigned_To"] = classification["Assigned_To"]
        output_row["Escalate_To_Director"] = classification["Escalate_To_Director"]
        output_row["SLA_Hours"] = classification["SLA_Hours"]
        output_row["Classification_Confidence"] = classification["Classification_Confidence"]
        output_row["AI_Explanation"] = ai_explanation
        output_row["Processed_At"] = processed_at

        results.append(output_row)

    return results


def print_summary(results: list[dict]) -> None:
    """Print a human-readable summary table to stdout."""
    print("\n" + "=" * 80)
    print("PROCESSING SUMMARY")
    print("=" * 80)
    print(f"{'Invoice ID':<20} {'Exception Type':<22} {'Assigned To':<30} {'Escalate':<10} {'SLA':>5}")
    print("-" * 80)
    for r in results:
        escalate = "YES" if r["Escalate_To_Director"] else "no"
        print(
            f"{r.get('Invoice_ID', ''):<20} "
            f"{r.get('Exception_Type', ''):<22} "
            f"{r.get('Assigned_To', ''):<30} "
            f"{escalate:<10} "
            f"{r.get('SLA_Hours', ''):>4}h"
        )
    escalate_count = sum(1 for r in results if r["Escalate_To_Director"])
    print("-" * 80)
    print(f"Total: {len(results)} exceptions | {escalate_count} require director escalation")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Workday AP Invoice Exception Classifier — routes exceptions and generates approver explanations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with demo data (no input file needed):
  python 01_invoice_exception_classifier.py --demo

  # Classify a real CSV file using Claude AI:
  python 01_invoice_exception_classifier.py --input invoices.csv --output results.csv

  # Rule-based only (no Claude API call):
  python 01_invoice_exception_classifier.py --input invoices.csv --no-ai

  # Custom output path:
  python 01_invoice_exception_classifier.py --input invoices.csv --output /tmp/classified.csv

Input CSV columns:
  Invoice_ID, Supplier, Amount, Currency, Invoice_Date,
  PO_Reference, Exception_Type, Exception_Detail

Supported Exception_Type values:
  DUPLICATE, PRICE_VARIANCE, QUANTITY_MISMATCH, MISSING_PO, MISSING_RECEIPT,
  TAX_DISCREPANCY, CURRENCY_MISMATCH, EARLY_PAYMENT, OVER_BUDGET, UNAPPROVED_SUPPLIER
        """,
    )
    parser.add_argument(
        "--input", "-i",
        help="Path to input CSV file with invoice exceptions.",
    )
    parser.add_argument(
        "--output", "-o",
        help="Path for output CSV file. Defaults to <input>_classified.csv",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with 5 embedded sample rows (no input file needed).",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip Claude API calls; use rule-based explanations only.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.demo and not args.input:
        print("ERROR: Provide --input <file.csv> or use --demo mode.")
        print("Run with --help for usage information.")
        sys.exit(1)

    # Set up AI client
    use_ai = not args.no_ai
    client = None

    if use_ai:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            warnings.warn(
                "ANTHROPIC_API_KEY not set. Falling back to rule-based explanations. "
                "Set the environment variable to enable Claude AI explanations.",
                UserWarning,
                stacklevel=2,
            )
            use_ai = False
        elif not ANTHROPIC_AVAILABLE:
            warnings.warn(
                "anthropic package not installed. Run: pip install anthropic. "
                "Falling back to rule-based explanations.",
                UserWarning,
                stacklevel=2,
            )
            use_ai = False
        else:
            client = anthropic.Anthropic(api_key=api_key)

    # Load rows
    if args.demo:
        print("Running in DEMO mode with 5 embedded sample rows.")
        rows = DEMO_ROWS
        output_path = args.output or "demo_classified.csv"
    else:
        input_path = args.input
        print(f"Reading input: {input_path}")
        try:
            with open(input_path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
        except FileNotFoundError:
            print(f"ERROR: Input file not found: {input_path}")
            sys.exit(1)
        except Exception as exc:
            print(f"ERROR reading input file: {exc}")
            sys.exit(1)

        if not rows:
            print("No rows found in input file.")
            sys.exit(0)

        output_path = args.output or input_path.replace(".csv", "_classified.csv")

    mode_label = "Claude AI" if use_ai else "Rule-Based Only"
    print(f"Processing {len(rows)} invoice exception(s) using {mode_label} mode...")
    print()

    results = process_rows(rows, use_ai=use_ai, client=client)

    print_summary(results)

    # Write output CSV
    output_fields = [
        "Invoice_ID", "Supplier", "Amount", "Currency", "Invoice_Date",
        "PO_Reference", "Exception_Type", "Exception_Detail",
        "Assigned_To", "Escalate_To_Director", "SLA_Hours",
        "Classification_Confidence", "AI_Explanation", "Processed_At",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=output_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"\nOutput saved to: {output_path}")


if __name__ == "__main__":
    main()
