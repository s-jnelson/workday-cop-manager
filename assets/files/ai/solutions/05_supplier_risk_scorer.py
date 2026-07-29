#!/usr/bin/env python3
"""
Solution 05: Supplier Risk Scorer
Workday Finance Tech CoP — AI Solutions Library

Scores supplier risk from Workday supplier master CSV data using configurable
risk dimensions. Optionally generates Claude AI narratives for high-risk suppliers.

Usage:
    python 05_supplier_risk_scorer.py --input suppliers.csv
    python 05_supplier_risk_scorer.py --demo
    python 05_supplier_risk_scorer.py --input suppliers.csv --no-ai
    python 05_supplier_risk_scorer.py --input suppliers.csv --country-risk custom_risk.json
"""

import argparse
import csv
import io
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Run: pip install pandas")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Country risk lists
# ---------------------------------------------------------------------------

HIGH_RISK_COUNTRIES = {
    "Belarus", "Russia", "Iran", "North Korea", "Syria",
    "Cuba", "Venezuela", "Myanmar",
}

MEDIUM_RISK_COUNTRIES = {
    "Afghanistan", "Iraq", "Libya", "Somalia", "Sudan",
    "South Sudan", "Yemen", "Zimbabwe", "Haiti", "Nicaragua",
}

# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

DEMO_CSV = """Supplier_ID,Supplier_Name,Supplier_Category,Tax_ID,Default_Currency,Payment_Terms_Days,Preferred_Payment_Type,Address_Country
SUP-001,Acme Office Supplies,Office Supplies,12-3456789,USD,30,ACH,United States
SUP-002,Global Tech Partners,IT Services,98-7654321,USD,90,Wire,Russia
SUP-003,Fast Freight LLC,Logistics,,USD,,Check,Mexico
SUP-004,Premier Consulting,Professional Services,55-1234567,USD,45,EFT,United Kingdom
SUP-005,BestDeal Imports,Manufacturing,,USD,75,Wire,Iran
SUP-006,Local Print Shop,Marketing,33-9876543,USD,15,ACH,United States
SUP-007,Regional Staffing Co,Staffing,77-1112233,USD,60,Check,
SUP-008,Delta Energy Corp,Utilities,44-5566778,USD,20,,Venezuela
"""

# ---------------------------------------------------------------------------
# Risk scoring functions
# ---------------------------------------------------------------------------

def score_data_completeness(row: pd.Series) -> int:
    """Score 0-25: deduct for missing critical fields."""
    score = 25
    if pd.isna(row.get("Tax_ID")) or str(row.get("Tax_ID", "")).strip() == "":
        score -= 10
    if pd.isna(row.get("Payment_Terms_Days")) or str(row.get("Payment_Terms_Days", "")).strip() == "":
        score -= 8
    if pd.isna(row.get("Address_Country")) or str(row.get("Address_Country", "")).strip() == "":
        score -= 4
    if pd.isna(row.get("Supplier_Category")) or str(row.get("Supplier_Category", "")).strip() == "":
        score -= 3
    return max(score, 0)


def score_payment_terms(row: pd.Series) -> int:
    """Score 0-25: longer payment terms = higher risk."""
    raw = str(row.get("Payment_Terms_Days", "")).strip().upper()
    if raw in ("", "NAN", "NONE"):
        return 12  # unknown = moderate risk
    if raw.startswith("NET10") or raw == "NET10":
        return 0
    try:
        days = float(raw)
    except ValueError:
        return 12
    if days > 60:
        return 25
    elif days > 30:
        return 15
    elif days > 15:
        return 5
    else:
        return 0


def score_geographic_risk(row: pd.Series, high_risk: set, medium_risk: set) -> int:
    """Score 0-25: based on supplier country."""
    country = str(row.get("Address_Country", "")).strip()
    if country == "" or country.upper() in ("NAN", "NONE"):
        return 10  # unknown country = moderate risk
    if country in high_risk:
        return 25
    if country in medium_risk:
        return 12
    return 0


def score_payment_type(row: pd.Series) -> int:
    """Score 0-25: riskier payment types score higher."""
    ptype = str(row.get("Preferred_Payment_Type", "")).strip().upper()
    mapping = {
        "WIRE": 20,
        "CHECK": 8,
        "ACH": 3,
        "EFT": 5,
    }
    if ptype in ("", "NAN", "NONE", "NOT SPECIFIED"):
        return 15
    return mapping.get(ptype, 10)


def determine_risk_level(total_score: int) -> str:
    if total_score <= 25:
        return "LOW"
    elif total_score <= 50:
        return "MEDIUM"
    elif total_score <= 75:
        return "HIGH"
    else:
        return "CRITICAL"


def score_supplier(row: pd.Series, high_risk: set, medium_risk: set) -> dict:
    """Compute all risk dimensions for a single supplier row."""
    completeness = score_data_completeness(row)
    payment_terms = score_payment_terms(row)
    geographic = score_geographic_risk(row, high_risk, medium_risk)
    payment_type = score_payment_type(row)
    total = completeness + payment_terms + geographic + payment_type
    level = determine_risk_level(total)

    return {
        "Supplier_ID": row.get("Supplier_ID", ""),
        "Supplier_Name": row.get("Supplier_Name", ""),
        "Supplier_Category": row.get("Supplier_Category", ""),
        "Address_Country": row.get("Address_Country", ""),
        "Preferred_Payment_Type": row.get("Preferred_Payment_Type", ""),
        "Payment_Terms_Days": row.get("Payment_Terms_Days", ""),
        "Score_Completeness": completeness,
        "Score_PaymentTerms": payment_terms,
        "Score_Geographic": geographic,
        "Score_PaymentType": payment_type,
        "Total_Risk_Score": total,
        "Risk_Level": level,
        "Top_Risk_Factor": _top_risk_factor(completeness, payment_terms, geographic, payment_type),
        "AI_Narrative": "",
    }


def _top_risk_factor(completeness, payment_terms, geographic, payment_type) -> str:
    factors = {
        "Data Completeness": 25 - completeness,
        "Payment Terms": payment_terms,
        "Geographic": geographic,
        "Payment Type": payment_type,
    }
    return max(factors, key=factors.get)


# ---------------------------------------------------------------------------
# Claude narrative generation
# ---------------------------------------------------------------------------

def generate_narrative(supplier_row: dict, api_key: str) -> str:
    """Call Claude to generate a 2-sentence risk narrative for a high-risk supplier."""
    try:
        import anthropic
    except ImportError:
        return "anthropic SDK not installed — skipping narrative."

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are a supplier risk analyst. Write exactly 2 sentences explaining the top risk factors for this supplier.
Be specific, professional, and actionable.

Supplier: {supplier_row['Supplier_Name']} ({supplier_row['Supplier_ID']})
Category: {supplier_row['Supplier_Category']}
Country: {supplier_row['Address_Country']}
Payment Type: {supplier_row['Preferred_Payment_Type']}
Payment Terms Days: {supplier_row['Payment_Terms_Days']}
Risk Scores — Completeness: {supplier_row['Score_Completeness']}/25, Payment Terms: {supplier_row['Score_PaymentTerms']}/25, Geographic: {supplier_row['Score_Geographic']}/25, Payment Type: {supplier_row['Score_PaymentType']}/25
Total Score: {supplier_row['Total_Risk_Score']}/100 ({supplier_row['Risk_Level']})

Write 2 sentences only. No bullet points, no headers."""

    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_country_risk(filepath: str) -> tuple[set, set]:
    """Load custom country risk lists from JSON file."""
    with open(filepath, "r") as f:
        data = json.load(f)
    high = set(data.get("high_risk", []))
    medium = set(data.get("medium_risk", []))
    return high, medium


def print_summary(results: list[dict]) -> None:
    from collections import Counter
    counts = Counter(r["Risk_Level"] for r in results)
    print("\n" + "=" * 60)
    print("SUPPLIER RISK SCORING SUMMARY")
    print("=" * 60)
    print(f"  Total Suppliers Scored : {len(results)}")
    print(f"  CRITICAL               : {counts.get('CRITICAL', 0)}")
    print(f"  HIGH                   : {counts.get('HIGH', 0)}")
    print(f"  MEDIUM                 : {counts.get('MEDIUM', 0)}")
    print(f"  LOW                    : {counts.get('LOW', 0)}")
    print("=" * 60)

    high_critical = [r for r in results if r["Risk_Level"] in ("HIGH", "CRITICAL")]
    if high_critical:
        print("\nHIGH / CRITICAL SUPPLIERS:")
        print(f"  {'Supplier':<35} {'Score':>6}  {'Level':<10}  Top Risk Factor")
        print("  " + "-" * 70)
        for r in sorted(high_critical, key=lambda x: -x["Total_Risk_Score"]):
            name = str(r["Supplier_Name"])[:33]
            print(f"  {name:<35} {r['Total_Risk_Score']:>5}/100  {r['Risk_Level']:<10}  {r['Top_Risk_Factor']}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Workday CoP — Supplier Risk Scorer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", "-i", help="Path to supplier master CSV file")
    parser.add_argument("--demo", action="store_true", help="Use embedded demo data")
    parser.add_argument("--no-ai", action="store_true", help="Skip Claude AI narrative generation")
    parser.add_argument("--country-risk", metavar="FILE", help="JSON file with custom country risk lists")
    parser.add_argument("--output-dir", default=".", help="Directory for output files (default: current directory)")
    args = parser.parse_args()

    if not args.demo and not args.input:
        parser.error("Provide --input <file.csv> or use --demo")

    # Load country risk lists
    if args.country_risk:
        print(f"Loading custom country risk from: {args.country_risk}")
        high_risk, medium_risk = load_country_risk(args.country_risk)
    else:
        high_risk, medium_risk = HIGH_RISK_COUNTRIES.copy(), MEDIUM_RISK_COUNTRIES.copy()

    # Load supplier data
    if args.demo:
        print("Using embedded demo data (8 sample suppliers)...")
        df = pd.read_csv(io.StringIO(DEMO_CSV))
        base_name = "demo_suppliers"
    else:
        print(f"Loading supplier data from: {args.input}")
        df = pd.read_csv(args.input)
        base_name = Path(args.input).stem

    print(f"Loaded {len(df)} supplier records.")

    # Validate required columns
    required_cols = ["Supplier_ID", "Supplier_Name", "Supplier_Category", "Tax_ID",
                     "Default_Currency", "Payment_Terms_Days", "Preferred_Payment_Type", "Address_Country"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"WARNING: Missing expected columns: {missing}")
        print("Scoring will proceed with available columns.")

    # Score all suppliers
    print("\nScoring suppliers...")
    results = []
    for _, row in df.iterrows():
        scored = score_supplier(row, high_risk, medium_risk)
        results.append(scored)

    # Generate AI narratives for HIGH/CRITICAL
    use_ai = not args.no_ai
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if use_ai and not api_key:
        print("NOTE: ANTHROPIC_API_KEY not set — skipping AI narratives. Use --no-ai to suppress this message.")
        use_ai = False

    if use_ai:
        high_critical = [r for r in results if r["Risk_Level"] in ("HIGH", "CRITICAL")]
        if high_critical:
            print(f"\nGenerating Claude narratives for {len(high_critical)} HIGH/CRITICAL suppliers...")
            for r in high_critical:
                try:
                    r["AI_Narrative"] = generate_narrative(r, api_key)
                    print(f"  [OK] {r['Supplier_Name']}")
                except Exception as e:
                    r["AI_Narrative"] = f"Narrative generation failed: {e}"
                    print(f"  [ERR] {r['Supplier_Name']}: {e}")

    # Print summary
    print_summary(results)

    # Save outputs
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Risk scores CSV
    scores_path = output_dir / f"{base_name}_risk_scores.csv"
    pd.DataFrame(results).to_csv(scores_path, index=False)
    print(f"Risk scores saved to: {scores_path}")

    # High risk report text
    high_critical_results = [r for r in results if r["Risk_Level"] in ("HIGH", "CRITICAL")]
    report_path = output_dir / f"{base_name}_high_risk_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("WORKDAY SUPPLIER RISK — HIGH/CRITICAL REPORT\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\n\n")

        if not high_critical_results:
            f.write("No HIGH or CRITICAL risk suppliers identified.\n")
        else:
            for r in sorted(high_critical_results, key=lambda x: -x["Total_Risk_Score"]):
                f.write(f"Supplier: {r['Supplier_Name']} ({r['Supplier_ID']})\n")
                f.write(f"Risk Level: {r['Risk_Level']}  |  Total Score: {r['Total_Risk_Score']}/100\n")
                f.write(f"Scores — Completeness: {r['Score_Completeness']}/25  |  "
                        f"Payment Terms: {r['Score_PaymentTerms']}/25  |  "
                        f"Geographic: {r['Score_Geographic']}/25  |  "
                        f"Payment Type: {r['Score_PaymentType']}/25\n")
                f.write(f"Country: {r['Address_Country']}  |  Payment Type: {r['Preferred_Payment_Type']}\n")
                if r["AI_Narrative"]:
                    f.write(f"\nRisk Narrative:\n{r['AI_Narrative']}\n")
                f.write("\n" + "-" * 70 + "\n\n")

    print(f"High-risk report saved to: {report_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
