#!/usr/bin/env python3
"""
Solution 06: Conversion Mapping Assistant
Workday Finance Tech CoP — AI Solutions Library

Analyzes a legacy ERP CSV extract and suggests Workday field mappings using Claude AI.
Supports six common Workday objects and produces a mapping table and full report.

Usage:
    python 06_conversion_mapping_assistant.py --demo
    python 06_conversion_mapping_assistant.py --source legacy_export.csv --target supplier_master
    python 06_conversion_mapping_assistant.py --source legacy_export.csv --target ledger_accounts --interactive

Requires: ANTHROPIC_API_KEY environment variable
"""

import argparse
import io
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Run: pip install pandas")
    sys.exit(1)

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic SDK is required. Run: pip install anthropic")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Workday object definitions
# ---------------------------------------------------------------------------

WORKDAY_OBJECTS = {
    "supplier_master": {
        "display_name": "Supplier Master",
        "required_fields": [
            {"field": "Supplier_ID", "description": "Unique supplier identifier", "type": "String(36)", "notes": "Alphanumeric, no spaces"},
            {"field": "Supplier_Name", "description": "Legal supplier name", "type": "String(255)", "notes": "Must match legal entity name"},
            {"field": "Supplier_Category", "description": "Workday supplier category reference", "type": "Reference", "notes": "Must match Workday ref data"},
            {"field": "Tax_ID", "description": "Tax identification number", "type": "String(20)", "notes": "EIN format: XX-XXXXXXX"},
            {"field": "Default_Currency", "description": "ISO 4217 currency code", "type": "String(3)", "notes": "E.g., USD, EUR, GBP"},
        ],
        "optional_fields": [
            {"field": "Payment_Terms_Days", "description": "Net payment terms in days", "type": "Integer", "notes": "E.g., 30, 45, 60"},
            {"field": "Preferred_Payment_Type", "description": "Payment method", "type": "Reference", "notes": "ACH, Wire, Check, EFT"},
            {"field": "Address_Country", "description": "ISO country code or name", "type": "String(50)", "notes": "E.g., United States"},
            {"field": "Address_Line_1", "description": "Street address", "type": "String(100)", "notes": ""},
            {"field": "City", "description": "City", "type": "String(50)", "notes": ""},
            {"field": "State", "description": "State or province", "type": "String(50)", "notes": ""},
            {"field": "Postal_Code", "description": "Zip or postal code", "type": "String(10)", "notes": ""},
        ],
    },
    "ledger_accounts": {
        "display_name": "Ledger Accounts (Chart of Accounts)",
        "required_fields": [
            {"field": "Account_ID", "description": "Unique account code", "type": "String(20)", "notes": "Alphanumeric"},
            {"field": "Account_Name", "description": "Account description", "type": "String(255)", "notes": ""},
            {"field": "Account_Type", "description": "Asset/Liability/Revenue/Expense/Equity", "type": "Reference", "notes": "Workday account type ref"},
            {"field": "Fund", "description": "Workday fund reference", "type": "Reference", "notes": ""},
        ],
        "optional_fields": [
            {"field": "Summary_Account", "description": "Parent rollup account", "type": "Reference", "notes": ""},
            {"field": "Account_Set", "description": "Account set grouping", "type": "Reference", "notes": ""},
            {"field": "Default_Cost_Center", "description": "Default CC assignment", "type": "Reference", "notes": ""},
            {"field": "Active", "description": "Account status", "type": "Boolean", "notes": "Y/N or True/False"},
        ],
    },
    "cost_centers": {
        "display_name": "Cost Centers",
        "required_fields": [
            {"field": "Cost_Center_ID", "description": "Unique cost center code", "type": "String(20)", "notes": ""},
            {"field": "Cost_Center_Name", "description": "Cost center name", "type": "String(255)", "notes": ""},
            {"field": "Organization_Subtype", "description": "Workday org subtype", "type": "Reference", "notes": "Must be Cost Center subtype"},
        ],
        "optional_fields": [
            {"field": "Manager", "description": "Cost center manager", "type": "Reference(Worker)", "notes": "Workday Worker ID"},
            {"field": "Hierarchy_Level", "description": "Level in org hierarchy", "type": "Integer", "notes": ""},
            {"field": "Parent_Cost_Center", "description": "Parent org reference", "type": "Reference", "notes": ""},
            {"field": "Effective_Date", "description": "Date cost center becomes active", "type": "Date(YYYY-MM-DD)", "notes": ""},
        ],
    },
    "customer_master": {
        "display_name": "Customer Master (AR)",
        "required_fields": [
            {"field": "Customer_ID", "description": "Unique customer identifier", "type": "String(36)", "notes": ""},
            {"field": "Customer_Name", "description": "Legal customer name", "type": "String(255)", "notes": ""},
            {"field": "Customer_Category", "description": "Workday customer category", "type": "Reference", "notes": ""},
            {"field": "Currency", "description": "Billing currency ISO code", "type": "String(3)", "notes": ""},
        ],
        "optional_fields": [
            {"field": "Tax_ID", "description": "Customer tax ID", "type": "String(20)", "notes": ""},
            {"field": "Payment_Terms", "description": "Payment terms reference", "type": "Reference", "notes": ""},
            {"field": "Credit_Limit", "description": "Credit limit amount", "type": "Decimal", "notes": ""},
            {"field": "Billing_Address", "description": "Billing street address", "type": "String(200)", "notes": ""},
            {"field": "Contact_Email", "description": "Primary contact email", "type": "String(100)", "notes": "Valid email format"},
        ],
    },
    "open_ap_invoices": {
        "display_name": "Open AP Invoices",
        "required_fields": [
            {"field": "Invoice_Number", "description": "Supplier invoice number", "type": "String(50)", "notes": "Must be unique per supplier"},
            {"field": "Supplier_ID", "description": "Reference to supplier", "type": "Reference(Supplier)", "notes": "Must exist in Workday"},
            {"field": "Invoice_Date", "description": "Invoice date", "type": "Date(YYYY-MM-DD)", "notes": ""},
            {"field": "Due_Date", "description": "Payment due date", "type": "Date(YYYY-MM-DD)", "notes": ""},
            {"field": "Invoice_Amount", "description": "Total invoice amount", "type": "Decimal", "notes": "Positive value"},
            {"field": "Currency", "description": "Invoice currency", "type": "String(3)", "notes": "ISO 4217"},
        ],
        "optional_fields": [
            {"field": "PO_Number", "description": "Purchase order reference", "type": "String(50)", "notes": ""},
            {"field": "Ledger_Account", "description": "Expense account code", "type": "Reference(Account)", "notes": ""},
            {"field": "Cost_Center", "description": "Charging cost center", "type": "Reference(CostCenter)", "notes": ""},
            {"field": "Description", "description": "Invoice line description", "type": "String(500)", "notes": ""},
            {"field": "Tax_Amount", "description": "Tax portion of invoice", "type": "Decimal", "notes": ""},
        ],
    },
    "fixed_assets": {
        "display_name": "Fixed Assets",
        "required_fields": [
            {"field": "Asset_ID", "description": "Unique asset identifier", "type": "String(20)", "notes": ""},
            {"field": "Asset_Description", "description": "Asset description", "type": "String(255)", "notes": ""},
            {"field": "Asset_Class", "description": "Workday asset class reference", "type": "Reference", "notes": ""},
            {"field": "Acquisition_Date", "description": "Date asset was acquired", "type": "Date(YYYY-MM-DD)", "notes": ""},
            {"field": "Original_Cost", "description": "Original purchase cost", "type": "Decimal", "notes": ""},
            {"field": "Currency", "description": "Cost currency", "type": "String(3)", "notes": ""},
        ],
        "optional_fields": [
            {"field": "Accumulated_Depreciation", "description": "Total depreciation to date", "type": "Decimal", "notes": ""},
            {"field": "Net_Book_Value", "description": "Original cost minus accum depreciation", "type": "Decimal", "notes": ""},
            {"field": "Useful_Life_Years", "description": "Expected useful life", "type": "Integer", "notes": ""},
            {"field": "Depreciation_Method", "description": "Straight-line, DDB, etc.", "type": "Reference", "notes": ""},
            {"field": "Location", "description": "Physical location of asset", "type": "String(100)", "notes": ""},
            {"field": "Supplier_ID", "description": "Supplier asset was purchased from", "type": "Reference(Supplier)", "notes": ""},
        ],
    },
}

# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

DEMO_CSV = """vendor_code,vendor_name,vendor_type,federal_tax_number,pay_currency,standard_pay_days,payment_method,country_code,street_addr,city_name,zip
V-10042,Acme Office Supply Co,GOODS,12-3456789,USD,30,ACH,US,123 Main St,Springfield,62701
V-10091,GlobalTech Solutions Inc,SERVICES,98-7654321,USD,60,WIRE,GB,10 Downing St,London,SW1A 2AA
V-10155,FastFreight LLC,LOGISTICS,,USD,,CHK,MX,Av. Reforma 1,Mexico City,06600
V-10201,Premier Consulting Group,PROFESSIONAL,55-1234567,EUR,45,EFT,DE,Hauptstrasse 5,Berlin,10115
V-10322,Regional Print Services,MARKETING,33-9876543,USD,15,ACH,US,456 Oak Ave,Austin,73301
"""

DEMO_TARGET = "supplier_master"

# ---------------------------------------------------------------------------
# PII column stripping
# ---------------------------------------------------------------------------

PII_PATTERNS = re.compile(r"ssn|tax_id|personal|dob|birth|social_sec|national_id", re.IGNORECASE)


def strip_pii_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Remove columns that look like PII based on name patterns."""
    pii_cols = [c for c in df.columns if PII_PATTERNS.search(c)]
    if pii_cols:
        df = df.drop(columns=pii_cols)
    return df, pii_cols


def sample_columns(df: pd.DataFrame, max_rows: int = 5) -> dict:
    """Return {col: [sample_values]} for up to max_rows rows."""
    sample = df.head(max_rows)
    return {col: [str(v) for v in sample[col].tolist()] for col in sample.columns}


# ---------------------------------------------------------------------------
# Claude mapping call
# ---------------------------------------------------------------------------

def call_claude_for_mappings(
    source_samples: dict,
    target_object: str,
    api_key: str,
) -> dict:
    """Ask Claude to suggest field mappings and return structured JSON."""
    client = anthropic.Anthropic(api_key=api_key)

    obj_def = WORKDAY_OBJECTS[target_object]
    required_fields = obj_def["required_fields"]
    optional_fields = obj_def["optional_fields"]

    source_desc = []
    for col, vals in source_samples.items():
        source_desc.append(f"  Column: {col!r} | Sample values: {vals}")
    source_text = "\n".join(source_desc)

    target_desc = []
    for f in required_fields:
        target_desc.append(f"  [REQUIRED] {f['field']} ({f['type']}): {f['description']}. Notes: {f['notes']}")
    for f in optional_fields:
        target_desc.append(f"  [OPTIONAL] {f['field']} ({f['type']}): {f['description']}. Notes: {f['notes']}")
    target_text = "\n".join(target_desc)

    prompt = f"""You are a Workday ERP implementation consultant specializing in data conversion.

A client is migrating from a legacy ERP system to Workday. You must analyze the source system CSV columns and suggest mappings to the target Workday object.

SOURCE SYSTEM COLUMNS (with sample values from first 5 rows):
{source_text}

TARGET WORKDAY OBJECT: {obj_def['display_name']}
TARGET FIELDS:
{target_text}

Return ONLY valid JSON matching this exact structure — no markdown, no explanation outside the JSON:
{{
  "mappings": [
    {{
      "source_col": "exact source column name",
      "target_field": "exact Workday field name",
      "confidence": "high|medium|low",
      "transformation_note": "describe any transformation needed (e.g., format conversion, lookup to ref data, concatenation). Write 'None' if direct map.",
      "data_quality_issue": "describe data quality concern if any. Write 'None' if clean."
    }}
  ],
  "unmapped_source_cols": ["list of source columns with no reasonable Workday mapping"],
  "required_fields_missing": ["list of required Workday fields with no source column mapping"],
  "summary": "2-3 sentence summary of mapping quality, main challenges, and recommended actions before loading."
}}

Rules:
- Only map source columns to target fields where there is a reasonable semantic match.
- A source column can map to at most one target field.
- A target field can only appear once in mappings.
- Be conservative: use 'low' confidence if the match is uncertain.
- Do not invent transformations — only suggest ones clearly needed based on the data types and sample values."""

    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Extract JSON if wrapped in code block
    if "```" in raw:
        raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()

    return json.loads(raw)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def print_mapping_table(mapping_result: dict, target_object: str) -> None:
    obj_name = WORKDAY_OBJECTS[target_object]["display_name"]
    print(f"\n{'=' * 70}")
    print(f"WORKDAY CONVERSION MAPPING — {obj_name}")
    print(f"{'=' * 70}")

    mappings = mapping_result.get("mappings", [])
    if mappings:
        # Try tabulate if available
        try:
            from tabulate import tabulate
            rows = [[m["source_col"], m["target_field"], m["confidence"].upper(),
                     m["transformation_note"][:40] + "..." if len(m.get("transformation_note", "")) > 40 else m.get("transformation_note", "")]
                    for m in mappings]
            print(tabulate(rows, headers=["Source Column", "Workday Field", "Confidence", "Transformation"], tablefmt="grid"))
        except ImportError:
            # Manual formatting
            print(f"\n  {'Source Column':<25} {'Workday Field':<30} {'Conf':<8} Transformation")
            print("  " + "-" * 85)
            for m in mappings:
                note = (m.get("transformation_note") or "None")[:30]
                print(f"  {m['source_col']:<25} {m['target_field']:<30} {m['confidence'].upper():<8} {note}")

    unmapped = mapping_result.get("unmapped_source_cols", [])
    if unmapped:
        print(f"\n  UNMAPPED SOURCE COLUMNS ({len(unmapped)}): {', '.join(unmapped)}")

    missing_req = mapping_result.get("required_fields_missing", [])
    if missing_req:
        print(f"\n  MISSING REQUIRED WORKDAY FIELDS ({len(missing_req)}): {', '.join(missing_req)}")

    issues = [m for m in mappings if m.get("data_quality_issue") and m["data_quality_issue"].lower() != "none"]
    if issues:
        print(f"\n  DATA QUALITY ISSUES:")
        for m in issues:
            print(f"    [{m['source_col']} -> {m['target_field']}]: {m['data_quality_issue']}")

    summary = mapping_result.get("summary", "")
    if summary:
        print(f"\n  SUMMARY:\n  {summary}")
    print()


def interactive_overrides(mapping_result: dict) -> dict:
    """Allow user to manually override individual mappings."""
    mappings = mapping_result.get("mappings", [])
    print("\n--- INTERACTIVE MAPPING OVERRIDE ---")
    print("For each mapping, press Enter to accept or type a new target field name to override.")
    print("Type 'skip' to remove the mapping entirely.\n")

    new_mappings = []
    for m in mappings:
        print(f"  {m['source_col']} -> {m['target_field']} [{m['confidence']}]")
        user_input = input("  Accept (Enter) / Override field name / 'skip': ").strip()
        if user_input.lower() == "skip":
            print("  Removed.")
        elif user_input == "":
            new_mappings.append(m)
        else:
            m = dict(m)
            m["target_field"] = user_input
            m["confidence"] = "manual"
            m["transformation_note"] = "Manually overridden by user"
            new_mappings.append(m)
            print(f"  Overridden to: {user_input}")

    mapping_result = dict(mapping_result)
    mapping_result["mappings"] = new_mappings
    return mapping_result


def save_outputs(mapping_result: dict, target_object: str, base_name: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    obj_name = WORKDAY_OBJECTS[target_object]["display_name"]

    # Mapping CSV
    csv_path = output_dir / f"{base_name}_mapping_output.csv"
    rows = []
    for m in mapping_result.get("mappings", []):
        rows.append({
            "Source_Column": m.get("source_col", ""),
            "Target_Workday_Field": m.get("target_field", ""),
            "Confidence": m.get("confidence", ""),
            "Transformation_Note": m.get("transformation_note", ""),
            "Data_Quality_Issue": m.get("data_quality_issue", ""),
        })
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    print(f"Mapping CSV saved to: {csv_path}")

    # Markdown report
    md_path = output_dir / f"{base_name}_mapping_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Workday Conversion Mapping Report\n\n")
        f.write(f"**Target Object:** {obj_name}  \n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n\n")

        f.write("## Field Mapping Table\n\n")
        f.write("| Source Column | Workday Field | Confidence | Transformation Note | Data Quality Issue |\n")
        f.write("|---|---|---|---|---|\n")
        for m in mapping_result.get("mappings", []):
            f.write(f"| {m.get('source_col','')} | {m.get('target_field','')} | {m.get('confidence','').upper()} | "
                    f"{m.get('transformation_note','')} | {m.get('data_quality_issue','')} |\n")

        unmapped = mapping_result.get("unmapped_source_cols", [])
        f.write(f"\n## Unmapped Source Columns\n\n")
        if unmapped:
            for col in unmapped:
                f.write(f"- `{col}`\n")
        else:
            f.write("_All source columns were mapped._\n")

        missing_req = mapping_result.get("required_fields_missing", [])
        f.write(f"\n## Required Workday Fields With No Source Mapping\n\n")
        if missing_req:
            for field in missing_req:
                f.write(f"- `{field}` — **Action required:** Provide default value or source from another system\n")
        else:
            f.write("_All required fields have source mappings._\n")

        f.write(f"\n## Summary\n\n{mapping_result.get('summary', '')}\n")

    print(f"Mapping report saved to: {md_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Workday CoP — Conversion Mapping Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--source", "-s", help="Legacy ERP CSV file to analyze")
    parser.add_argument("--target", "-t", choices=list(WORKDAY_OBJECTS.keys()),
                        help=f"Workday target object: {', '.join(WORKDAY_OBJECTS.keys())}")
    parser.add_argument("--demo", action="store_true", help="Use embedded demo data (supplier_master target)")
    parser.add_argument("--interactive", action="store_true", help="Allow user to override individual mappings")
    parser.add_argument("--output-dir", default=".", help="Directory for output files")
    args = parser.parse_args()

    # Check API key — this tool requires Claude
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.")
        print("This tool requires Claude AI — there is no rule-based fallback.")
        print("Set your API key: export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    if not args.demo and (not args.source or not args.target):
        parser.error("Provide --source <file.csv> --target <object>, or use --demo")

    # Load data
    if args.demo:
        print("Using embedded demo data (legacy vendor extract -> supplier_master)...")
        df = pd.read_csv(io.StringIO(DEMO_CSV))
        target_object = DEMO_TARGET
        base_name = "demo_legacy_vendor"
    else:
        print(f"Loading source CSV: {args.source}")
        df = pd.read_csv(args.source)
        target_object = args.target
        base_name = Path(args.source).stem

    print(f"Loaded {len(df)} rows, {len(df.columns)} columns.")
    print(f"Target Workday object: {WORKDAY_OBJECTS[target_object]['display_name']}")

    # Strip PII columns
    df, stripped_pii = strip_pii_columns(df)
    if stripped_pii:
        print(f"NOTE: Stripped potential PII columns before sending to Claude: {stripped_pii}")

    # Sample data
    source_samples = sample_columns(df, max_rows=5)

    # Call Claude
    print("\nCalling Claude to analyze mappings...")
    mapping_result = call_claude_for_mappings(source_samples, target_object, api_key)

    # Print table
    print_mapping_table(mapping_result, target_object)

    # Interactive overrides
    if args.interactive:
        mapping_result = interactive_overrides(mapping_result)
        print("\nFinal mapping after overrides:")
        print_mapping_table(mapping_result, target_object)

    # Save outputs
    output_dir = Path(args.output_dir)
    save_outputs(mapping_result, target_object, base_name, output_dir)
    print("\nDone.")


if __name__ == "__main__":
    main()
