#!/usr/bin/env python3
"""
Solution 07: Expense Policy Reviewer
Workday Finance Tech CoP — AI Solutions Library

Reviews expense report lines against configurable policy rules. Flags violations
by severity (P1/P2/P3) and optionally uses Claude AI to provide approval
recommendations and manager draft notes.

Usage:
    python 07_expense_policy_reviewer.py --demo
    python 07_expense_policy_reviewer.py --input expenses.csv
    python 07_expense_policy_reviewer.py --input expenses.csv --no-ai
    python 07_expense_policy_reviewer.py --input expenses.csv --policy custom_policy.json

Requires: ANTHROPIC_API_KEY environment variable (unless --no-ai is used)
"""

import argparse
import io
import json
import os
import sys
from datetime import datetime, date
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Run: pip install pandas")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Default policy
# ---------------------------------------------------------------------------

DEFAULT_POLICY = {
    "meals_per_diem": 75,
    "hotel_per_diem": 250,
    "entertainment_limit": 150,
    "alcohol_prohibited": True,
    "personal_items_prohibited": True,
    "receipt_required_above": 25,
    "max_single_expense": 5000,
    "prohibited_categories": ["Personal Care", "Gym", "Entertainment - Personal"],
    "weekend_meal_requires_note": True,
}

ALCOHOL_KEYWORDS = ["alcohol", "bar", "wine", "beer", "liquor", "spirits", "cocktail", "pub", "tavern"]
PERSONAL_KEYWORDS = ["personal", "gym", "grooming", "haircut", "clothing", "spa", "massage"]

MEAL_CATEGORIES = ["Meals", "Meals & Entertainment", "Business Meals", "Lunch", "Dinner", "Breakfast"]
HOTEL_CATEGORIES = ["Hotel", "Lodging", "Accommodation"]
ENTERTAINMENT_CATEGORIES = ["Entertainment", "Client Entertainment", "Team Entertainment"]

# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

DEMO_CSV = """Expense_Report_ID,Employee_ID,Expense_Date,Category,Amount,Currency,Description,Receipt_Attached,Merchant,Cost_Center
ER-2024-001,EMP-101,2024-03-15,Meals,45.00,USD,Lunch with client - project kickoff,Y,The Capital Grille,CC-Finance
ER-2024-001,EMP-101,2024-03-15,Hotel,275.00,USD,Overnight stay for client meeting,Y,Marriott Downtown,CC-Finance
ER-2024-001,EMP-101,2024-03-16,Meals,95.00,USD,Team dinner after workshop,Y,Nobu Restaurant,CC-Finance
ER-2024-002,EMP-202,2024-03-16,Meals,85.00,USD,Saturday working lunch - quarterly close,Y,Panera Bread,CC-Accounting
ER-2024-002,EMP-202,2024-03-17,Entertainment,200.00,USD,Client entertainment - Sunday golf outing,N,Pebble Beach Golf,CC-Accounting
ER-2024-002,EMP-202,2024-03-18,Meals,30.00,USD,Bar tab after client dinner - wine and cocktails,N,The Plaza Bar,CC-Accounting
ER-2024-003,EMP-303,2024-03-19,Personal Care,65.00,USD,Haircut and grooming before client presentation,N,Executive Salon,CC-IT
ER-2024-003,EMP-303,2024-03-19,Meals,22.00,USD,Working lunch at desk,N,Subway,CC-IT
ER-2024-003,EMP-303,2024-03-20,Hotel,230.00,USD,Conference hotel accommodation,Y,Hilton Conference Center,CC-IT
ER-2024-004,EMP-404,2024-03-20,Meals,55.00,USD,Lunch with prospective client,Y,Maggianos,CC-Sales
ER-2024-004,EMP-404,2024-03-21,Meals,70.00,USD,Team lunch - monthly meeting,Y,Olive Garden,CC-Sales
ER-2024-004,EMP-404,2024-03-21,Equipment,6500.00,USD,Laptop purchase for project,N,Best Buy,CC-Sales
ER-2024-005,EMP-505,2024-03-22,Meals,48.00,USD,Client breakfast meeting - contract renewal,Y,Four Seasons Cafe,CC-Consulting
ER-2024-005,EMP-505,2024-03-22,Entertainment,120.00,USD,Team celebration dinner - project close,Y,Cheesecake Factory,CC-Consulting
ER-2024-005,EMP-505,2024-03-23,Gym,45.00,USD,Hotel gym day pass during travel,N,Marriott Fitness,CC-Consulting
"""

# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------

def check_expense_row(row: pd.Series, policy: dict) -> list[dict]:
    """Check a single expense row against all policy rules. Returns list of violations."""
    violations = []

    amount = float(row.get("Amount", 0) or 0)
    category = str(row.get("Category", "")).strip()
    description = str(row.get("Description", "")).strip().lower()
    receipt = str(row.get("Receipt_Attached", "")).strip().upper()
    receipt_attached = receipt in ("Y", "YES", "TRUE", "1")
    currency = str(row.get("Currency", "USD")).strip()

    # Parse expense date
    expense_date = None
    try:
        date_str = str(row.get("Expense_Date", ""))
        expense_date = pd.to_datetime(date_str).date()
    except Exception:
        pass

    # Rule: prohibited categories
    if category in policy.get("prohibited_categories", []):
        violations.append({
            "rule": "prohibited_category",
            "severity": "P1",
            "detail": f"Category '{category}' is prohibited per policy.",
            "suggested_action": "Remove expense or reclassify to an approved category.",
        })

    # Rule: personal items prohibited
    if policy.get("personal_items_prohibited") and any(kw in description for kw in PERSONAL_KEYWORDS):
        violations.append({
            "rule": "personal_items_prohibited",
            "severity": "P1",
            "detail": f"Description contains personal/non-business terms: '{row.get('Description', '')}'",
            "suggested_action": "Remove expense — personal items are not reimbursable.",
        })

    # Rule: alcohol prohibited
    if policy.get("alcohol_prohibited") and any(kw in description for kw in ALCOHOL_KEYWORDS):
        violations.append({
            "rule": "alcohol_prohibited",
            "severity": "P2",
            "detail": f"Description suggests alcohol purchase: '{row.get('Description', '')}'",
            "suggested_action": "Separate alcohol charges from meal receipts. Alcohol is not reimbursable.",
        })

    # Rule: max single expense
    max_exp = policy.get("max_single_expense", 5000)
    if amount > max_exp:
        violations.append({
            "rule": "max_single_expense",
            "severity": "P1",
            "detail": f"Expense amount {currency} {amount:.2f} exceeds maximum single expense limit of {max_exp:.2f}.",
            "suggested_action": "Requires VP-level approval and supporting documentation.",
        })

    # Rule: receipt required
    receipt_threshold = policy.get("receipt_required_above", 25)
    if amount > receipt_threshold and not receipt_attached:
        if amount > 500:
            sev = "P1"
            action = "Receipt is mandatory for expenses over $500. Do not reimburse without receipt."
        else:
            sev = "P2"
            action = f"Receipt required for expenses over ${receipt_threshold}. Request receipt from employee."
        violations.append({
            "rule": "receipt_required",
            "severity": sev,
            "detail": f"No receipt attached for {currency} {amount:.2f} expense (threshold: ${receipt_threshold}).",
            "suggested_action": action,
        })

    # Rule: meals per diem
    is_meal = any(cat.lower() in category.lower() for cat in MEAL_CATEGORIES)
    if is_meal:
        meals_limit = policy.get("meals_per_diem", 75)
        if amount > meals_limit:
            violations.append({
                "rule": "meals_per_diem",
                "severity": "P2",
                "detail": f"Meal expense {currency} {amount:.2f} exceeds daily per diem of {meals_limit:.2f}.",
                "suggested_action": f"Reimburse up to ${meals_limit:.2f}. Employee responsible for overage.",
            })

        # Rule: weekend meal requires business justification
        if policy.get("weekend_meal_requires_note") and expense_date:
            if expense_date.weekday() in (5, 6):  # Saturday=5, Sunday=6
                # Check if description contains any business justification keywords
                biz_keywords = ["client", "meeting", "project", "close", "conference", "workshop", "quarterly"]
                has_justification = any(kw in description for kw in biz_keywords)
                if not has_justification:
                    violations.append({
                        "rule": "weekend_meal_requires_note",
                        "severity": "P3",
                        "detail": f"Meal expense on {expense_date.strftime('%A')} lacks business justification in description.",
                        "suggested_action": "Employee must add business purpose note for weekend meal reimbursement.",
                    })

    # Rule: hotel per diem
    is_hotel = any(cat.lower() in category.lower() for cat in HOTEL_CATEGORIES)
    if is_hotel:
        hotel_limit = policy.get("hotel_per_diem", 250)
        if amount > hotel_limit:
            violations.append({
                "rule": "hotel_per_diem",
                "severity": "P2",
                "detail": f"Hotel expense {currency} {amount:.2f} exceeds per diem of {hotel_limit:.2f}.",
                "suggested_action": f"Reimburse up to ${hotel_limit:.2f}. Document business need for higher-cost property.",
            })

    # Rule: entertainment limit
    is_entertainment = any(cat.lower() in category.lower() for cat in ENTERTAINMENT_CATEGORIES)
    if is_entertainment:
        ent_limit = policy.get("entertainment_limit", 150)
        if amount > ent_limit:
            violations.append({
                "rule": "entertainment_limit",
                "severity": "P3",
                "detail": f"Entertainment expense {currency} {amount:.2f} exceeds per-event limit of {ent_limit:.2f}.",
                "suggested_action": f"Requires manager pre-approval for entertainment over ${ent_limit:.2f}.",
            })

    return violations


# ---------------------------------------------------------------------------
# Claude analysis
# ---------------------------------------------------------------------------

def analyze_report_with_claude(
    report_id: str,
    expense_rows: list[dict],
    violations: list[dict],
    api_key: str,
) -> dict:
    """Call Claude to review violations for a single expense report and provide recommendation."""
    try:
        import anthropic as anthropic_module
    except ImportError:
        return {"recommendation": "REVIEW", "rationale": "anthropic SDK not available.", "manager_note": ""}

    client = anthropic_module.Anthropic(api_key=api_key)

    expense_summary = []
    for row in expense_rows:
        expense_summary.append(
            f"  - {row.get('Expense_Date', '')}: {row.get('Category', '')} | "
            f"{row.get('Currency', 'USD')} {float(row.get('Amount', 0)):.2f} | "
            f"'{row.get('Description', '')}' | Receipt: {row.get('Receipt_Attached', 'N')}"
        )

    violations_summary = []
    for v in violations:
        violations_summary.append(f"  - [{v['severity']}] {v['rule']}: {v['detail']}")

    prompt = f"""You are a corporate expense policy compliance reviewer at a professional services firm.

Review the following expense report and its policy violations. Provide:
1. An honest assessment of whether violations are genuine or have an explanation
2. An overall recommendation: APPROVE, REJECT, or REVIEW (needs more info)
3. A brief, professional manager note (2-3 sentences) to communicate the decision

EXPENSE REPORT: {report_id}
EXPENSE LINES:
{chr(10).join(expense_summary)}

POLICY VIOLATIONS FLAGGED:
{chr(10).join(violations_summary)}

Return ONLY valid JSON — no markdown, no explanation outside the JSON:
{{
  "recommendation": "APPROVE|REJECT|REVIEW",
  "rationale": "1-2 sentences explaining your recommendation based on the violations",
  "manager_note": "Professional 2-3 sentence note the manager can send to the employee explaining the decision and any required actions.",
  "genuine_violations": ["list violation rule names that appear genuinely non-compliant"],
  "explainable_violations": ["list violation rule names that may have legitimate explanations"]
}}"""

    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    import re
    if "```" in raw:
        raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()

    return json.loads(raw)


# ---------------------------------------------------------------------------
# Output and summary
# ---------------------------------------------------------------------------

def print_summary(report_summaries: list[dict], all_violations: list[dict]) -> None:
    from collections import Counter
    sev_counts = Counter(v["severity"] for v in all_violations)
    rec_counts = Counter(r.get("recommendation", "REVIEW") for r in report_summaries)

    print("\n" + "=" * 65)
    print("EXPENSE POLICY REVIEW SUMMARY")
    print("=" * 65)
    print(f"  Expense Reports Reviewed : {len(report_summaries)}")
    print(f"  Total Violations Found   : {len(all_violations)}")
    print(f"    P1 (Critical)          : {sev_counts.get('P1', 0)}")
    print(f"    P2 (Warning)           : {sev_counts.get('P2', 0)}")
    print(f"    P3 (Advisory)          : {sev_counts.get('P3', 0)}")
    print(f"  Recommendations:")
    print(f"    APPROVE                : {rec_counts.get('APPROVE', 0)}")
    print(f"    REVIEW                 : {rec_counts.get('REVIEW', 0)}")
    print(f"    REJECT                 : {rec_counts.get('REJECT', 0)}")
    print("=" * 65)

    for r in report_summaries:
        rec = r.get("recommendation", "N/A")
        rec_symbol = {"APPROVE": "[OK]", "REJECT": "[!!]", "REVIEW": "[??]", "N/A": "[ ]"}.get(rec, "[ ]")
        print(f"  {rec_symbol} {r['Expense_Report_ID']}: {rec} — P1:{r['P1_Count']} P2:{r['P2_Count']} P3:{r['P3_Count']}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Workday CoP — Expense Policy Reviewer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", "-i", help="Expense report CSV file")
    parser.add_argument("--demo", action="store_true", help="Use embedded demo data (15 sample rows)")
    parser.add_argument("--no-ai", action="store_true", help="Rule engine only — skip Claude analysis")
    parser.add_argument("--policy", metavar="FILE", help="JSON file with policy overrides")
    parser.add_argument("--output-dir", default=".", help="Directory for output files")
    args = parser.parse_args()

    if not args.demo and not args.input:
        parser.error("Provide --input <file.csv> or use --demo")

    # Load policy
    policy = dict(DEFAULT_POLICY)
    if args.policy:
        print(f"Loading custom policy from: {args.policy}")
        with open(args.policy, "r") as f:
            overrides = json.load(f)
        policy.update(overrides)
        print(f"  Applied {len(overrides)} policy overrides.")

    # Load data
    if args.demo:
        print("Using embedded demo data (15 sample expense rows)...")
        df = pd.read_csv(io.StringIO(DEMO_CSV))
        base_name = "demo_expenses"
    else:
        print(f"Loading expense data from: {args.input}")
        df = pd.read_csv(args.input)
        base_name = Path(args.input).stem

    print(f"Loaded {len(df)} expense rows across {df['Expense_Report_ID'].nunique()} reports.")

    # Check API key
    use_ai = not args.no_ai
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if use_ai and not api_key:
        print("NOTE: ANTHROPIC_API_KEY not set — skipping AI analysis. Use --no-ai to suppress this message.")
        use_ai = False

    # Run rule engine on all rows
    print("\nRunning policy rule engine...")
    all_violations = []
    violation_rows = []

    for idx, row in df.iterrows():
        violations = check_expense_row(row, policy)
        for v in violations:
            violation_rows.append({
                "Expense_Report_ID": row.get("Expense_Report_ID", ""),
                "Employee_ID": row.get("Employee_ID", ""),
                "Expense_Date": row.get("Expense_Date", ""),
                "Category": row.get("Category", ""),
                "Amount": row.get("Amount", ""),
                "Currency": row.get("Currency", ""),
                "Description": row.get("Description", ""),
                "Violation_Rule": v["rule"],
                "Severity": v["severity"],
                "Violation_Detail": v["detail"],
                "Suggested_Action": v["suggested_action"],
            })
        all_violations.extend(violations)

    print(f"Found {len(all_violations)} total violations.")

    # Group by report and generate AI analysis
    report_summaries = []
    grouped = df.groupby("Expense_Report_ID")

    for report_id, report_df in grouped:
        report_rows = report_df.to_dict(orient="records")
        report_violations = [
            v for vrow in violation_rows
            if vrow["Expense_Report_ID"] == report_id
            for v in [{"severity": vrow["Severity"], "rule": vrow["Violation_Rule"], "detail": vrow["Violation_Detail"]}]
        ]

        p1 = sum(1 for v in report_violations if v["severity"] == "P1")
        p2 = sum(1 for v in report_violations if v["severity"] == "P2")
        p3 = sum(1 for v in report_violations if v["severity"] == "P3")

        summary_row = {
            "Expense_Report_ID": report_id,
            "Employee_ID": report_df["Employee_ID"].iloc[0] if "Employee_ID" in report_df.columns else "",
            "Total_Amount": round(report_df["Amount"].astype(float).sum(), 2),
            "Expense_Line_Count": len(report_df),
            "P1_Count": p1,
            "P2_Count": p2,
            "P3_Count": p3,
            "Total_Violations": p1 + p2 + p3,
            "recommendation": "APPROVE" if (p1 + p2) == 0 else ("REJECT" if p1 > 0 else "REVIEW"),
            "rationale": "",
            "manager_note": "",
        }

        if use_ai and (p1 + p2) > 0:
            print(f"  Analyzing {report_id} with Claude ({p1} P1, {p2} P2 violations)...")
            try:
                ai_result = analyze_report_with_claude(report_id, report_rows, report_violations, api_key)
                summary_row["recommendation"] = ai_result.get("recommendation", summary_row["recommendation"])
                summary_row["rationale"] = ai_result.get("rationale", "")
                summary_row["manager_note"] = ai_result.get("manager_note", "")
            except Exception as e:
                print(f"  [ERR] Claude analysis failed for {report_id}: {e}")

        report_summaries.append(summary_row)

    # Print summary
    print_summary(report_summaries, all_violations)

    # Save outputs
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    violations_path = output_dir / f"{base_name}_policy_violations.csv"
    pd.DataFrame(violation_rows).to_csv(violations_path, index=False)
    print(f"Policy violations saved to: {violations_path}")

    summary_path = output_dir / f"{base_name}_report_summary.csv"
    pd.DataFrame(report_summaries).to_csv(summary_path, index=False)
    print(f"Report summary saved to: {summary_path}")

    # Optional Excel output
    excel_path = output_dir / f"{base_name}_expense_review.xlsx"
    try:
        import openpyxl
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            pd.DataFrame(violation_rows).to_excel(writer, sheet_name="Violations", index=False)
            pd.DataFrame(report_summaries).to_excel(writer, sheet_name="Report Summary", index=False)
        print(f"Excel workbook saved to: {excel_path}")
    except ImportError:
        print("NOTE: openpyxl not installed — Excel output skipped. Run: pip install openpyxl")

    print("\nDone.")


if __name__ == "__main__":
    main()
