#!/usr/bin/env python3
"""
Workday GL Financial Anomaly Detector
======================================
Detects anomalies in General Ledger transaction data using statistical methods.
No Claude API required for core detection — optional AI narrative for HIGH items.

Detection methods:
  1. Z-score per account (flag |z| > threshold, default 3)
  2. IQR outlier per account (Q1-1.5*IQR / Q3+1.5*IQR)
  3. Weekend/holiday posting detection
  4. Round-number bias (4+ trailing zeros on amounts > $10k)
  5. Duplicate detection (same amount + account + date)
  6. New account activity (account not seen in prior 90 days)

Usage:
    python 02_financial_anomaly_detector.py --input gl_transactions.csv
    python 02_financial_anomaly_detector.py --demo
    python 02_financial_anomaly_detector.py --input gl.csv --threshold 2.5
    python 02_financial_anomaly_detector.py --input gl.csv --no-narrative
"""

import argparse
import csv
import os
import random
import sys
import warnings
from datetime import date, datetime, timedelta, timezone
from typing import Optional

try:
    import numpy as np
    import pandas as pd
    from scipy import stats as scipy_stats
    SCIPY_AVAILABLE = True
except ImportError:
    print("ERROR: Required packages missing. Run: pip install pandas numpy scipy")
    sys.exit(1)

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# ---------------------------------------------------------------------------
# US Federal Holidays (2024 — extend as needed)
# ---------------------------------------------------------------------------

US_HOLIDAYS_2024 = {
    date(2024, 1, 1),   # New Year's Day
    date(2024, 1, 15),  # MLK Day
    date(2024, 2, 19),  # Presidents' Day
    date(2024, 5, 27),  # Memorial Day
    date(2024, 6, 19),  # Juneteenth
    date(2024, 7, 4),   # Independence Day
    date(2024, 9, 2),   # Labor Day
    date(2024, 11, 11), # Veterans Day
    date(2024, 11, 28), # Thanksgiving
    date(2024, 12, 25), # Christmas
}

# ---------------------------------------------------------------------------
# Synthetic demo data generator
# ---------------------------------------------------------------------------

ACCOUNTS = ["6100-Salaries", "6200-Benefits", "7100-Travel", "7200-Meals",
            "8100-Software", "8200-Hardware", "9100-Consulting", "9200-Rent",
            "5100-COGS", "4000-Revenue"]
COST_CENTERS = ["CC-Finance", "CC-IT", "CC-Marketing", "CC-Operations", "CC-HR"]
USERS = ["jsmith", "amiller", "rjohnson", "tlee", "kpatel", "bwilson",
         "mbrown", "cgarcia", "dchen", "lwang"]


def generate_demo_data(n_rows: int = 300) -> pd.DataFrame:
    """Generate a synthetic GL transaction dataset with seeded anomalies."""
    random.seed(42)
    np.random.seed(42)

    start_date = datetime(2024, 1, 1)
    rows = []

    for i in range(n_rows):
        account = random.choice(ACCOUNTS)
        tx_date = start_date + timedelta(days=random.randint(0, 364))
        amount = abs(np.random.lognormal(mean=7, sigma=1.5))
        debit_credit = random.choice(["Debit", "Credit"])

        rows.append({
            "Transaction_ID": f"TXN-{i+1:05d}",
            "Date": tx_date.strftime("%Y-%m-%d"),
            "Account": account,
            "Cost_Center": random.choice(COST_CENTERS),
            "Amount": round(amount, 2),
            "Debit_Credit": debit_credit,
            "Description": f"Journal entry {i+1} - {account}",
            "Posted_By": random.choice(USERS),
        })

    # Inject known anomalies
    # 1. Huge z-score spike on account 7100-Travel
    for j in range(3):
        rows.append({
            "Transaction_ID": f"TXN-ANOM-Z{j+1}",
            "Date": "2024-06-15",
            "Account": "7100-Travel",
            "Cost_Center": "CC-Marketing",
            "Amount": 250000.00 + j * 10000,
            "Debit_Credit": "Debit",
            "Description": "Travel expense - executive offsite",
            "Posted_By": "jsmith",
        })

    # 2. Weekend posting
    rows.append({
        "Transaction_ID": "TXN-ANOM-WK1",
        "Date": "2024-03-09",  # Saturday
        "Account": "9100-Consulting",
        "Cost_Center": "CC-Finance",
        "Amount": 15000.00,
        "Debit_Credit": "Debit",
        "Description": "Weekend consulting charge",
        "Posted_By": "bwilson",
    })

    # 3. Round number bias
    rows.append({
        "Transaction_ID": "TXN-ANOM-RND1",
        "Date": "2024-04-10",
        "Account": "9200-Rent",
        "Cost_Center": "CC-Operations",
        "Amount": 50000.00,
        "Debit_Credit": "Debit",
        "Description": "Monthly rent payment",
        "Posted_By": "amiller",
    })

    # 4. Duplicate
    dup_row = {
        "Transaction_ID": "TXN-ANOM-DUP2",
        "Date": "2024-05-20",
        "Account": "8100-Software",
        "Cost_Center": "CC-IT",
        "Amount": 4850.00,
        "Debit_Credit": "Debit",
        "Description": "Software license Q2",
        "Posted_By": "tlee",
    }
    rows.append({**dup_row, "Transaction_ID": "TXN-ANOM-DUP1"})
    rows.append(dup_row)

    # 5. New account (not seen in first 90 days)
    rows.append({
        "Transaction_ID": "TXN-ANOM-NEW1",
        "Date": "2024-11-15",
        "Account": "ACCT-9999-NEW",
        "Cost_Center": "CC-Finance",
        "Amount": 75000.00,
        "Debit_Credit": "Debit",
        "Description": "New cost allocation",
        "Posted_By": "kpatel",
    })

    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])
    df["Amount"] = df["Amount"].astype(float)
    return df


# ---------------------------------------------------------------------------
# Detection methods
# ---------------------------------------------------------------------------

def detect_zscore(df: pd.DataFrame, threshold: float) -> pd.Series:
    """Flag transactions where |z-score| exceeds threshold within each account."""
    flags = pd.Series([[] for _ in range(len(df))], index=df.index)
    z_scores = pd.Series(0.0, index=df.index)

    for account, group in df.groupby("Account"):
        if len(group) < 3:
            continue
        z = scipy_stats.zscore(group["Amount"], nan_policy="omit")
        z_series = pd.Series(z, index=group.index)
        triggered = z_series.abs() > threshold
        for idx in group.index[triggered]:
            flags.at[idx] = flags.at[idx] + [f"ZSCORE({z_series[idx]:.2f})"]
            z_scores.at[idx] = abs(z_series[idx])

    return flags, z_scores


def detect_iqr(df: pd.DataFrame) -> pd.Series:
    """Flag transactions outside Q1-1.5*IQR or Q3+1.5*IQR per account."""
    flags = pd.Series([[] for _ in range(len(df))], index=df.index)

    for account, group in df.groupby("Account"):
        if len(group) < 4:
            continue
        q1 = group["Amount"].quantile(0.25)
        q3 = group["Amount"].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        triggered = (group["Amount"] < lower) | (group["Amount"] > upper)
        for idx in group.index[triggered]:
            flags.at[idx] = flags.at[idx] + ["IQR_OUTLIER"]

    return flags


def detect_weekend_holiday(df: pd.DataFrame) -> pd.Series:
    """Flag transactions posted on weekends or US federal holidays."""
    flags = pd.Series([[] for _ in range(len(df))], index=df.index)

    for idx, row in df.iterrows():
        tx_date = row["Date"]
        if hasattr(tx_date, "date"):
            d = tx_date.date()
        else:
            d = tx_date

        if tx_date.weekday() >= 5:  # Saturday=5, Sunday=6
            flags.at[idx] = flags.at[idx] + ["WEEKEND_POSTING"]
        elif d in US_HOLIDAYS_2024:
            flags.at[idx] = flags.at[idx] + ["HOLIDAY_POSTING"]

    return flags


def detect_round_numbers(df: pd.DataFrame, min_amount: float = 10_000) -> pd.Series:
    """Flag large round-number transactions (4+ trailing zeros)."""
    flags = pd.Series([[] for _ in range(len(df))], index=df.index)

    for idx, row in df.iterrows():
        amount = row["Amount"]
        if amount >= min_amount:
            # Check if divisible by 10,000 (4 trailing zeros)
            if amount == int(amount) and int(amount) % 10_000 == 0:
                flags.at[idx] = flags.at[idx] + [f"ROUND_NUMBER({amount:,.0f})"]

    return flags


def detect_duplicates(df: pd.DataFrame) -> pd.Series:
    """Flag rows where Amount + Account + Date appears more than once."""
    flags = pd.Series([[] for _ in range(len(df))], index=df.index)

    key_cols = ["Amount", "Account", "Date"]
    dupe_mask = df.duplicated(subset=key_cols, keep=False)

    for idx in df.index[dupe_mask]:
        flags.at[idx] = flags.at[idx] + ["DUPLICATE_TXN"]

    return flags


def detect_new_accounts(df: pd.DataFrame, lookback_days: int = 90) -> pd.Series:
    """Flag accounts that have no transactions in the prior 90-day window."""
    flags = pd.Series([[] for _ in range(len(df))], index=df.index)

    df_sorted = df.sort_values("Date")

    for idx, row in df_sorted.iterrows():
        account = row["Account"]
        tx_date = row["Date"]
        window_start = tx_date - timedelta(days=lookback_days)

        prior_activity = df_sorted[
            (df_sorted["Account"] == account)
            & (df_sorted["Date"] >= window_start)
            & (df_sorted["Date"] < tx_date)
        ]

        if len(prior_activity) == 0:
            # Check if this account ever appeared before this transaction
            ever_before = df_sorted[
                (df_sorted["Account"] == account) & (df_sorted["Date"] < tx_date)
            ]
            if len(ever_before) == 0:
                flags.at[idx] = flags.at[idx] + ["NEW_ACCOUNT"]

    return flags


# ---------------------------------------------------------------------------
# Severity scoring
# ---------------------------------------------------------------------------

def compute_severity_and_score(all_flags: list, max_z: float) -> tuple[str, int]:
    """Compute Severity (HIGH/MEDIUM/LOW) and Anomaly_Score (0-100)."""
    flag_count = len(all_flags)
    has_high_z = max_z > 4.0

    if has_high_z or flag_count >= 3:
        severity = "HIGH"
        base_score = 75
    elif flag_count == 2 or (max_z >= 3.0 and not has_high_z):
        severity = "MEDIUM"
        base_score = 50
    else:
        severity = "LOW"
        base_score = 25

    # Bonus points for z-score magnitude and flag count
    score = min(100, base_score + int(max_z * 3) + flag_count * 5)
    return severity, score


# ---------------------------------------------------------------------------
# Optional Claude narrative for HIGH items
# ---------------------------------------------------------------------------

def generate_narrative(client: "anthropic.Anthropic", row: dict) -> str:
    """Generate a 1-sentence narrative for a HIGH severity anomaly."""
    prompt = f"""You are a financial auditor's assistant. Write exactly ONE sentence
explaining why this GL transaction is flagged as a HIGH-severity anomaly.
Be specific about the anomaly type but do not mention exact dollar amounts.
Use professional audit language.

Transaction details:
- Account: {row['Account']}
- Anomaly Flags: {row['Anomaly_Flags']}
- Severity: {row['Severity']}
- Anomaly Score: {row['Anomaly_Score']}
- Posted By: {row['Posted_By']}
- Date: {row['Date']}

Respond with exactly one sentence."""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=128,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as exc:
        return f"[Narrative unavailable: {exc}]"


# ---------------------------------------------------------------------------
# Core analysis pipeline
# ---------------------------------------------------------------------------

def run_analysis(df: pd.DataFrame, z_threshold: float,
                 use_narrative: bool, client: Optional["anthropic.Anthropic"]) -> pd.DataFrame:
    """Run all detection methods and return the anomalies DataFrame."""

    print(f"  Running z-score detection (threshold |z| > {z_threshold})...")
    zscore_flags, z_scores = detect_zscore(df, z_threshold)

    print("  Running IQR outlier detection...")
    iqr_flags = detect_iqr(df)

    print("  Running weekend/holiday posting detection...")
    weekend_flags = detect_weekend_holiday(df)

    print("  Running round-number bias detection...")
    round_flags = detect_round_numbers(df)

    print("  Running duplicate transaction detection...")
    dupe_flags = detect_duplicates(df)

    print("  Running new account activity detection...")
    new_acct_flags = detect_new_accounts(df)

    # Combine flags
    all_flags_series = pd.Series(index=df.index, dtype=object)
    for idx in df.index:
        combined = (
            zscore_flags.at[idx]
            + iqr_flags.at[idx]
            + weekend_flags.at[idx]
            + round_flags.at[idx]
            + dupe_flags.at[idx]
            + new_acct_flags.at[idx]
        )
        all_flags_series.at[idx] = combined

    # Filter to only anomalous rows
    anomaly_mask = all_flags_series.apply(len) > 0
    anomaly_df = df[anomaly_mask].copy()

    if anomaly_df.empty:
        return anomaly_df

    anomaly_df["Anomaly_Flags"] = all_flags_series[anomaly_mask].apply(lambda x: "; ".join(x))
    anomaly_df["Max_Z_Score"] = z_scores[anomaly_mask]

    severities = []
    scores = []
    for idx in anomaly_df.index:
        flags = all_flags_series.at[idx]
        max_z = z_scores.at[idx]
        sev, score = compute_severity_and_score(flags, max_z)
        severities.append(sev)
        scores.append(score)

    anomaly_df["Severity"] = severities
    anomaly_df["Anomaly_Score"] = scores

    # Optional Claude narratives for HIGH items
    if use_narrative and client is not None:
        high_mask = anomaly_df["Severity"] == "HIGH"
        high_count = high_mask.sum()
        if high_count > 0:
            print(f"  Generating Claude narratives for {high_count} HIGH-severity item(s)...")
        narratives = []
        for idx, row in anomaly_df.iterrows():
            if row["Severity"] == "HIGH":
                narrative = generate_narrative(client, row.to_dict())
            else:
                narrative = ""
            narratives.append(narrative)
        anomaly_df["AI_Narrative"] = narratives

    return anomaly_df


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def print_summary_table(anomaly_df: pd.DataFrame, total_rows: int) -> None:
    """Print a formatted summary to stdout."""
    print("\n" + "=" * 90)
    print("ANOMALY DETECTION SUMMARY")
    print("=" * 90)
    print(f"Total transactions analyzed: {total_rows}")
    print(f"Anomalies detected:          {len(anomaly_df)}")

    if anomaly_df.empty:
        print("No anomalies detected.")
        return

    severity_counts = anomaly_df["Severity"].value_counts()
    for sev in ["HIGH", "MEDIUM", "LOW"]:
        count = severity_counts.get(sev, 0)
        print(f"  {sev:<8}: {count}")

    print()
    print(f"{'TXN ID':<18} {'Date':<12} {'Account':<22} {'Amount':>12} {'Score':>6} {'Sev':<8} {'Flags'}")
    print("-" * 90)

    display_df = anomaly_df.sort_values("Anomaly_Score", ascending=False).head(20)
    for _, row in display_df.iterrows():
        date_str = str(row["Date"])[:10]
        amount_str = f"${row['Amount']:>12,.2f}"
        flags_abbrev = row["Anomaly_Flags"][:35] + "..." if len(row["Anomaly_Flags"]) > 35 else row["Anomaly_Flags"]
        print(
            f"{str(row['Transaction_ID']):<18} {date_str:<12} {str(row['Account']):<22} "
            f"{amount_str} {int(row['Anomaly_Score']):>5}  {str(row['Severity']):<8} {flags_abbrev}"
        )

    if len(anomaly_df) > 20:
        print(f"  ... and {len(anomaly_df) - 20} more (see output file)")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Workday GL Financial Anomaly Detector — statistical detection of unusual transactions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with synthetic demo data:
  python 02_financial_anomaly_detector.py --demo

  # Analyze a real GL export:
  python 02_financial_anomaly_detector.py --input gl_transactions.csv

  # Stricter z-score threshold:
  python 02_financial_anomaly_detector.py --input gl.csv --threshold 2.5

  # Skip Claude narratives:
  python 02_financial_anomaly_detector.py --input gl.csv --no-narrative

Input CSV columns:
  Transaction_ID, Date, Account, Cost_Center, Amount,
  Debit_Credit, Description, Posted_By
        """,
    )
    parser.add_argument("--input", "-i", help="Path to input GL transaction CSV.")
    parser.add_argument("--output", "-o", help="Output CSV path. Defaults to <input>_anomalies.csv")
    parser.add_argument("--demo", action="store_true", help="Generate synthetic data and run analysis.")
    parser.add_argument(
        "--threshold", type=float, default=3.0,
        help="Z-score threshold for flagging (default: 3.0).",
    )
    parser.add_argument(
        "--no-narrative", action="store_true",
        help="Skip Claude AI narrative generation for HIGH items.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.demo and not args.input:
        print("ERROR: Provide --input <file.csv> or use --demo mode.")
        print("Run with --help for usage information.")
        sys.exit(1)

    # Set up optional AI client
    use_narrative = not args.no_narrative
    client = None

    if use_narrative:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            use_narrative = False
            print("Note: ANTHROPIC_API_KEY not set. Skipping AI narratives for HIGH items.")
        elif not ANTHROPIC_AVAILABLE:
            use_narrative = False
            print("Note: anthropic package not installed. Skipping AI narratives.")
        else:
            client = anthropic.Anthropic(api_key=api_key)
            print("Claude AI narratives enabled for HIGH severity items.")

    # Load data
    if args.demo:
        print("DEMO mode: generating synthetic GL dataset (300 transactions + seeded anomalies)...")
        df = generate_demo_data(300)
        output_path = args.output or "demo_gl_anomalies.csv"
    else:
        print(f"Reading: {args.input}")
        try:
            df = pd.read_csv(args.input, parse_dates=["Date"])
            df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
        except FileNotFoundError:
            print(f"ERROR: File not found: {args.input}")
            sys.exit(1)
        except Exception as exc:
            print(f"ERROR reading file: {exc}")
            sys.exit(1)

        output_path = args.output or args.input.replace(".csv", "_anomalies.csv")

    print(f"\nAnalyzing {len(df)} transactions across {df['Account'].nunique()} accounts...")
    print()

    anomaly_df = run_analysis(df, args.threshold, use_narrative, client)
    print_summary_table(anomaly_df, len(df))

    if not anomaly_df.empty:
        # Ensure Date is string-formatted for CSV output
        out_df = anomaly_df.copy()
        out_df["Date"] = out_df["Date"].astype(str).str[:10]
        out_df.to_csv(output_path, index=False)
        print(f"\nAnomalies saved to: {output_path}")
    else:
        print("\nNo anomalies detected — no output file written.")


if __name__ == "__main__":
    main()
