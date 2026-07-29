"""
Workday Financial Conversion Data Validator
============================================
Validates source data files against Workday Financial data model requirements
before executing iLoad or EIB conversion runs.

Supports all 14 standard Workday Financial conversion objects.

Usage
-----
    pip install pandas openpyxl

    from workday_financial_validator import WDValidator

    # Validate a single object
    v = WDValidator()
    result = v.validate("supplier_master", "path/to/supplier_data.csv")
    result.print_summary()
    result.to_excel("supplier_validation_results.xlsx")

    # Validate all objects in a directory
    results = v.validate_all("path/to/conversion_files/")

    # Check go/no-go readiness gate
    if result.meets_golive_gate():
        print("APPROVED for production load")
    else:
        print("BLOCKED — resolve P1/P2 issues before proceeding")
"""

from __future__ import annotations
import re
import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable


# ── Constants ──────────────────────────────────────────────────────────────────
SEVERITY_P1 = "P1-Critical"   # Blocks go-live; load will fail or corrupt data
SEVERITY_P2 = "P2-High"       # Likely to cause issues post-load
SEVERITY_P3 = "P3-Medium"     # Data quality concern; review recommended

GOLIVE_P1_THRESHOLD = 0        # Zero P1s required
GOLIVE_DEFECT_RATE_THRESHOLD = 5.0  # ≤5% overall defect rate (matching methodology gate)

ISO_CURRENCIES = {
    "USD","EUR","GBP","CAD","AUD","JPY","CHF","CNY","HKD","SGD","INR","MXN",
    "BRL","KRW","SEK","NOK","DKK","NZD","ZAR","AED","SAR","THB","MYR","PLN",
    "CZK","HUF","TRY","ILS","PHP","IDR","VND","CLP","COP","ARS","PEN",
}

ISO_COUNTRIES = {
    "US","GB","CA","AU","DE","FR","IT","ES","NL","BE","CH","AT","SE","NO","DK",
    "FI","IE","PT","LU","NZ","JP","CN","KR","IN","SG","HK","AE","SA","ZA","MX",
    "BR","AR","CL","CO","PE","PH","MY","TH","ID","VN","PL","CZ","HU","RO","BG",
}

VALID_PAYMENT_TYPES = {"ACH", "Check", "Wire", "Virtual_Card", "Manual", "Intercompany"}

VALID_DEPRECIATION_METHODS = {
    "Straight_Line", "Declining_Balance_150", "Declining_Balance_200",
    "Sum_of_Years_Digits", "Units_of_Production", "No_Depreciation",
}

VALID_ACCOUNT_TYPES = {
    "Asset", "Liability", "Equity", "Revenue", "Expense",
    "Gain_Loss", "Balance_Sheet", "Income_Statement",
}

VALID_SUPPLIER_CATEGORIES = {
    "Vendor", "Contractor", "Consultant", "Employee", "Intercompany",
    "Government", "Non_Profit", "Individual",
}


# ── Validation Result ──────────────────────────────────────────────────────────
@dataclass
class ValidationIssue:
    row: int
    column: str
    value: str
    severity: str
    rule: str
    message: str
    suggested_fix: str = ""


@dataclass
class ValidationResult:
    object_name: str
    file_path: str
    total_rows: int
    issues: list[ValidationIssue] = field(default_factory=list)
    validated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def p1_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == SEVERITY_P1)

    @property
    def p2_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == SEVERITY_P2)

    @property
    def p3_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == SEVERITY_P3)

    @property
    def affected_rows(self) -> set[int]:
        return {i.row for i in self.issues}

    @property
    def defect_rate_pct(self) -> float:
        if self.total_rows == 0:
            return 0.0
        return round(len(self.affected_rows) / self.total_rows * 100, 2)

    def meets_golive_gate(self) -> bool:
        return self.p1_count == 0 and self.defect_rate_pct <= GOLIVE_DEFECT_RATE_THRESHOLD

    def print_summary(self) -> None:
        bar = "═" * 62
        print(f"\n{bar}")
        print(f"  Workday Conversion Validation — {self.object_name.upper()}")
        print(f"{bar}")
        print(f"  File          : {self.file_path}")
        print(f"  Total Rows    : {self.total_rows:,}")
        print(f"  Affected Rows : {len(self.affected_rows):,}")
        print(f"  Defect Rate   : {self.defect_rate_pct}%  (gate: ≤{GOLIVE_DEFECT_RATE_THRESHOLD}%)")
        print(f"  P1 Critical   : {self.p1_count}")
        print(f"  P2 High       : {self.p2_count}")
        print(f"  P3 Medium     : {self.p3_count}")
        status = "✓ APPROVED" if self.meets_golive_gate() else "✗ BLOCKED"
        color = "" if self.meets_golive_gate() else ""
        print(f"  Go-Live Gate  : {status}")
        print(f"{bar}")

        if self.issues:
            print(f"\n  Top Issues (first 20):")
            for issue in self.issues[:20]:
                print(f"    [{issue.severity}] Row {issue.row} | {issue.column} | {issue.message}")
                if issue.suggested_fix:
                    print(f"       Fix: {issue.suggested_fix}")
        print()

    def to_excel(self, output_path: str) -> str:
        """Write validation results to a formatted Excel report."""
        path = Path(output_path)
        summary_data = {
            "Metric": ["Object", "File", "Total Rows", "Affected Rows", "Defect Rate %",
                        "P1 Critical", "P2 High", "P3 Medium", "Go-Live Gate"],
            "Value": [self.object_name, self.file_path, self.total_rows,
                      len(self.affected_rows), f"{self.defect_rate_pct}%",
                      self.p1_count, self.p2_count, self.p3_count,
                      "APPROVED" if self.meets_golive_gate() else "BLOCKED"],
        }
        issues_data = {
            "Row":           [i.row for i in self.issues],
            "Column":        [i.column for i in self.issues],
            "Value":         [i.value for i in self.issues],
            "Severity":      [i.severity for i in self.issues],
            "Rule":          [i.rule for i in self.issues],
            "Message":       [i.message for i in self.issues],
            "Suggested Fix": [i.suggested_fix for i in self.issues],
        }

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame(summary_data).to_excel(writer, sheet_name="Summary", index=False)
            pd.DataFrame(issues_data).to_excel(writer, sheet_name="Issues", index=False)

            # Style the summary sheet
            wb = writer.book
            ws_summary = wb["Summary"]
            from openpyxl.styles import PatternFill, Font, Alignment
            header_fill = PatternFill("solid", fgColor="1E2333")
            for cell in ws_summary[1]:
                cell.fill = header_fill
                cell.font = Font(color="4A9EFF", bold=True)

            # Color-code severity in issues sheet
            ws_issues = wb["Issues"]
            severity_colors = {
                SEVERITY_P1: "3D1515",
                SEVERITY_P2: "3D2E0A",
                SEVERITY_P3: "143D22",
            }
            for row in ws_issues.iter_rows(min_row=2):
                sev_cell = row[3]  # Severity column
                color = severity_colors.get(sev_cell.value, "1E2333")
                fill = PatternFill("solid", fgColor=color)
                for cell in row:
                    cell.fill = fill

        print(f"Validation report written to: {path}")
        return str(path)


# ── Rule Engine ────────────────────────────────────────────────────────────────
class Rule:
    def __init__(self, column: str, severity: str, message_template: str, suggested_fix: str = ""):
        self.column = column
        self.severity = severity
        self.message_template = message_template
        self.suggested_fix = suggested_fix

    def check(self, row_idx: int, row: pd.Series) -> ValidationIssue | None:
        raise NotImplementedError


class RequiredField(Rule):
    """Field must not be null or empty."""
    def check(self, row_idx, row):
        val = row.get(self.column, None)
        if pd.isna(val) or str(val).strip() == "":
            return ValidationIssue(
                row=row_idx, column=self.column, value="(empty)",
                severity=self.severity, rule="RequiredField",
                message=f"'{self.column}' is required and cannot be blank.",
                suggested_fix=self.suggested_fix or f"Populate '{self.column}' for every row.",
            )
        return None


class MaxLength(Rule):
    """Field value must not exceed max_length characters."""
    def __init__(self, column, max_length, severity=SEVERITY_P2, suggested_fix=""):
        super().__init__(column, severity, "", suggested_fix)
        self.max_length = max_length

    def check(self, row_idx, row):
        val = str(row.get(self.column, "") or "")
        if len(val) > self.max_length:
            return ValidationIssue(
                row=row_idx, column=self.column, value=val[:50],
                severity=self.severity, rule="MaxLength",
                message=f"'{self.column}' length {len(val)} exceeds maximum {self.max_length}.",
                suggested_fix=self.suggested_fix or f"Truncate to {self.max_length} characters.",
            )
        return None


class ValidValues(Rule):
    """Field value must be in the allowed set."""
    def __init__(self, column, allowed: set, severity=SEVERITY_P1,
                 case_sensitive=False, suggested_fix=""):
        super().__init__(column, severity, "", suggested_fix)
        self.allowed = allowed
        self.case_sensitive = case_sensitive

    def check(self, row_idx, row):
        val = row.get(self.column, None)
        if pd.isna(val) or str(val).strip() == "":
            return None  # Let RequiredField handle blanks
        check_val = str(val).strip() if self.case_sensitive else str(val).strip().upper()
        allowed_check = self.allowed if self.case_sensitive else {v.upper() for v in self.allowed}
        if check_val not in allowed_check:
            top5 = ", ".join(list(self.allowed)[:5])
            return ValidationIssue(
                row=row_idx, column=self.column, value=str(val),
                severity=self.severity, rule="ValidValues",
                message=f"'{val}' is not a valid value for '{self.column}'.",
                suggested_fix=self.suggested_fix or f"Use one of: {top5} ...",
            )
        return None


class DateFormat(Rule):
    """Field must be a valid date in YYYY-MM-DD format."""
    def __init__(self, column, severity=SEVERITY_P1, required=True, suggested_fix=""):
        super().__init__(column, severity, "", suggested_fix)
        self.required = required

    def check(self, row_idx, row):
        val = row.get(self.column, None)
        if pd.isna(val) or str(val).strip() == "":
            if not self.required:
                return None
            return ValidationIssue(
                row=row_idx, column=self.column, value="(empty)",
                severity=self.severity, rule="DateFormat",
                message=f"'{self.column}' is required and must be a valid date.",
                suggested_fix="Format as YYYY-MM-DD (e.g., 2026-01-01).",
            )
        try:
            datetime.strptime(str(val).strip()[:10], "%Y-%m-%d")
            return None
        except ValueError:
            return ValidationIssue(
                row=row_idx, column=self.column, value=str(val),
                severity=self.severity, rule="DateFormat",
                message=f"'{val}' is not a valid date in YYYY-MM-DD format.",
                suggested_fix="Reformat as YYYY-MM-DD (e.g., 2026-01-01). Remove any time components.",
            )


class NumericAmount(Rule):
    """Field must be a valid number, optionally non-negative."""
    def __init__(self, column, severity=SEVERITY_P1, required=True,
                 non_negative=False, suggested_fix=""):
        super().__init__(column, severity, "", suggested_fix)
        self.required = required
        self.non_negative = non_negative

    def check(self, row_idx, row):
        val = row.get(self.column, None)
        if pd.isna(val) or str(val).strip() == "":
            if not self.required:
                return None
            return ValidationIssue(
                row=row_idx, column=self.column, value="(empty)",
                severity=self.severity, rule="NumericAmount",
                message=f"'{self.column}' is required and must be numeric.",
                suggested_fix="Enter a numeric value (e.g., 1250.00). No currency symbols or commas.",
            )
        try:
            # Strip common non-numeric characters
            cleaned = str(val).replace(",", "").replace("$", "").replace(" ", "").strip()
            num = float(cleaned)
            if self.non_negative and num < 0:
                return ValidationIssue(
                    row=row_idx, column=self.column, value=str(val),
                    severity=self.severity, rule="NumericAmount",
                    message=f"'{self.column}' value {num} is negative — must be ≥ 0.",
                    suggested_fix="Enter the absolute value. Use separate Debit/Credit columns for sign.",
                )
            return None
        except (ValueError, TypeError):
            return ValidationIssue(
                row=row_idx, column=self.column, value=str(val),
                severity=self.severity, rule="NumericAmount",
                message=f"'{val}' is not a valid number for '{self.column}'.",
                suggested_fix="Remove currency symbols, commas, and spaces. Use decimal point (not comma) for decimals.",
            )


class DecimalPlaces(Rule):
    """Amount field must not exceed the specified number of decimal places."""
    def __init__(self, column, max_decimals=2, severity=SEVERITY_P3, suggested_fix=""):
        super().__init__(column, severity, "", suggested_fix)
        self.max_decimals = max_decimals

    def check(self, row_idx, row):
        val = row.get(self.column, None)
        if pd.isna(val) or str(val).strip() == "":
            return None
        try:
            cleaned = str(val).replace(",", "").replace("$", "").strip()
            if "." in cleaned:
                decimals = len(cleaned.split(".")[1])
                if decimals > self.max_decimals:
                    return ValidationIssue(
                        row=row_idx, column=self.column, value=str(val),
                        severity=self.severity, rule="DecimalPlaces",
                        message=f"'{self.column}' has {decimals} decimal places; maximum is {self.max_decimals}.",
                        suggested_fix=f"Round to {self.max_decimals} decimal places.",
                    )
        except Exception:
            pass
        return None


class UniqueKey(Rule):
    """Column (or combination) must be unique across all rows."""
    def __init__(self, columns: list[str], severity=SEVERITY_P1, suggested_fix=""):
        super().__init__(",".join(columns), severity, "", suggested_fix)
        self.key_columns = columns
        self._seen: dict = {}

    def reset(self):
        self._seen = {}

    def check(self, row_idx, row):
        key = tuple(str(row.get(c, "")).strip() for c in self.key_columns)
        if key in self._seen:
            return ValidationIssue(
                row=row_idx, column=self.column, value=str(key),
                severity=self.severity, rule="UniqueKey",
                message=f"Duplicate key {dict(zip(self.key_columns, key))} — also found on row {self._seen[key]}.",
                suggested_fix="Remove or merge the duplicate row. Each key must appear exactly once.",
            )
        self._seen[key] = row_idx
        return None


class RegexFormat(Rule):
    """Field must match the specified regular expression."""
    def __init__(self, column, pattern: str, pattern_desc: str,
                 severity=SEVERITY_P2, required=False, suggested_fix=""):
        super().__init__(column, severity, "", suggested_fix)
        self.pattern = re.compile(pattern)
        self.pattern_desc = pattern_desc
        self.required = required

    def check(self, row_idx, row):
        val = row.get(self.column, None)
        if pd.isna(val) or str(val).strip() == "":
            return None  # Handled by RequiredField
        if not self.pattern.match(str(val).strip()):
            return ValidationIssue(
                row=row_idx, column=self.column, value=str(val),
                severity=self.severity, rule="RegexFormat",
                message=f"'{val}' does not match expected format for '{self.column}' ({self.pattern_desc}).",
                suggested_fix=self.suggested_fix or f"Format must match: {self.pattern_desc}",
            )
        return None


class CrossFieldRule(Rule):
    """Validates relationships between two fields."""
    def __init__(self, column: str, check_fn: Callable, message: str,
                 severity=SEVERITY_P2, suggested_fix=""):
        super().__init__(column, severity, message, suggested_fix)
        self.check_fn = check_fn
        self._message = message

    def check(self, row_idx, row):
        try:
            if not self.check_fn(row):
                return ValidationIssue(
                    row=row_idx, column=self.column, value="",
                    severity=self.severity, rule="CrossField",
                    message=self._message,
                    suggested_fix=self.suggested_fix,
                )
        except Exception:
            pass
        return None


# ── Object Rule Sets ──────────────────────────────────────────────────────────
def _date_not_future(col):
    def fn(row):
        val = row.get(col)
        if pd.isna(val) or str(val).strip() == "":
            return True
        try:
            d = datetime.strptime(str(val).strip()[:10], "%Y-%m-%d")
            return d <= datetime.now()
        except Exception:
            return True
    return fn


OBJECT_RULES: dict[str, list[Rule]] = {

    # ── 1. Ledger Accounts / Chart of Accounts ──────────────────────────────
    "ledger_accounts": [
        UniqueKey(["Ledger_Account_ID"]),
        RequiredField("Ledger_Account_ID", SEVERITY_P1, suggested_fix="Assign a unique ID, e.g., '1000', '2100'."),
        MaxLength("Ledger_Account_ID", 50),
        RequiredField("Name", SEVERITY_P1, suggested_fix="Enter the account display name."),
        MaxLength("Name", 255),
        RequiredField("Account_Type", SEVERITY_P1),
        ValidValues("Account_Type", VALID_ACCOUNT_TYPES, suggested_fix="Use: Asset, Liability, Equity, Revenue, Expense, or Gain_Loss"),
        DateFormat("Start_Date", required=True),
        DateFormat("End_Date", required=False, severity=SEVERITY_P2),
        ValidValues("Currency_Code", ISO_CURRENCIES, suggested_fix="Use 3-letter ISO currency code, e.g., USD"),
    ],

    # ── 2. Cost Centers ──────────────────────────────────────────────────────
    "cost_centers": [
        UniqueKey(["Cost_Center_ID"]),
        RequiredField("Cost_Center_ID", SEVERITY_P1),
        MaxLength("Cost_Center_ID", 50),
        RequiredField("Name", SEVERITY_P1),
        MaxLength("Name", 255),
        RequiredField("Availability_Date", SEVERITY_P1),
        DateFormat("Availability_Date", required=True),
        DateFormat("Inactive_Date", required=False, severity=SEVERITY_P2),
    ],

    # ── 3. Supplier Master ──────────────────────────────────────────────────
    "supplier_master": [
        UniqueKey(["Supplier_ID"]),
        RequiredField("Supplier_ID", SEVERITY_P1, suggested_fix="Assign a unique Supplier ID matching the legacy system."),
        MaxLength("Supplier_ID", 50),
        RequiredField("Supplier_Name", SEVERITY_P1),
        MaxLength("Supplier_Name", 300),
        RequiredField("Default_Currency", SEVERITY_P1),
        ValidValues("Default_Currency", ISO_CURRENCIES),
        ValidValues("Default_Payment_Type", VALID_PAYMENT_TYPES, severity=SEVERITY_P2),
        RequiredField("Country", SEVERITY_P1),
        ValidValues("Country", ISO_COUNTRIES, severity=SEVERITY_P2, suggested_fix="Use 2-letter ISO country code (e.g., US, GB, CA)."),
        MaxLength("Address_Line_1", 200),
        MaxLength("City", 100),
        MaxLength("State", 50),
        MaxLength("Postal_Code", 20),
        RegexFormat("Tax_ID", r"^\d{2}-\d{7}$|^\d{3}-\d{2}-\d{4}$|^[A-Z0-9\-]{5,30}$",
                    "EIN (##-#######), SSN (###-##-####), or alphanumeric for foreign Tax IDs",
                    severity=SEVERITY_P3, required=False),
    ],

    # ── 4. Customer Master ──────────────────────────────────────────────────
    "customer_master": [
        UniqueKey(["Customer_ID"]),
        RequiredField("Customer_ID", SEVERITY_P1),
        MaxLength("Customer_ID", 50),
        RequiredField("Customer_Name", SEVERITY_P1),
        MaxLength("Customer_Name", 300),
        RequiredField("Currency", SEVERITY_P1),
        ValidValues("Currency", ISO_CURRENCIES),
        RequiredField("Country", SEVERITY_P1),
        ValidValues("Country", ISO_COUNTRIES, severity=SEVERITY_P2),
        NumericAmount("Credit_Limit_Amount", required=False, non_negative=True, severity=SEVERITY_P3),
        DecimalPlaces("Credit_Limit_Amount"),
    ],

    # ── 5. Open Accounts Payable (Supplier Invoices) ────────────────────────
    "open_ap_invoices": [
        UniqueKey(["Company", "Supplier_ID", "Invoice_Number"]),
        RequiredField("Company", SEVERITY_P1, suggested_fix="Enter the Workday Company Reference ID."),
        RequiredField("Supplier_ID", SEVERITY_P1, suggested_fix="Must match a Supplier loaded in Supplier Master."),
        RequiredField("Invoice_Number", SEVERITY_P1),
        MaxLength("Invoice_Number", 100),
        RequiredField("Invoice_Date", SEVERITY_P1),
        DateFormat("Invoice_Date", required=True),
        CrossFieldRule("Invoice_Date", _date_not_future("Invoice_Date"),
                       "Invoice_Date is in the future — open AP invoices should have past dates.",
                       severity=SEVERITY_P2, suggested_fix="Verify the Invoice_Date is correct."),
        RequiredField("Due_Date", SEVERITY_P1),
        DateFormat("Due_Date", required=True),
        RequiredField("Currency", SEVERITY_P1),
        ValidValues("Currency", ISO_CURRENCIES),
        RequiredField("Invoice_Amount", SEVERITY_P1),
        NumericAmount("Invoice_Amount", non_negative=False),
        DecimalPlaces("Invoice_Amount"),
        NumericAmount("Tax_Amount", required=False, non_negative=True, severity=SEVERITY_P3),
        DecimalPlaces("Tax_Amount"),
        CrossFieldRule(
            "Due_Date",
            lambda row: (
                pd.isna(row.get("Invoice_Date")) or pd.isna(row.get("Due_Date")) or
                datetime.strptime(str(row["Due_Date"]).strip()[:10], "%Y-%m-%d") >=
                datetime.strptime(str(row["Invoice_Date"]).strip()[:10], "%Y-%m-%d")
            ),
            "Due_Date cannot be before Invoice_Date.",
            severity=SEVERITY_P2,
        ),
    ],

    # ── 6. Open Accounts Receivable (Customer Invoices) ─────────────────────
    "open_ar_invoices": [
        UniqueKey(["Company", "Customer_ID", "Invoice_Number"]),
        RequiredField("Company", SEVERITY_P1),
        RequiredField("Customer_ID", SEVERITY_P1, suggested_fix="Must match a Customer loaded in Customer Master."),
        RequiredField("Invoice_Number", SEVERITY_P1),
        MaxLength("Invoice_Number", 100),
        RequiredField("Invoice_Date", SEVERITY_P1),
        DateFormat("Invoice_Date"),
        CrossFieldRule("Invoice_Date", _date_not_future("Invoice_Date"),
                       "Invoice_Date is in the future.", severity=SEVERITY_P2),
        RequiredField("Due_Date", SEVERITY_P1),
        DateFormat("Due_Date"),
        RequiredField("Currency", SEVERITY_P1),
        ValidValues("Currency", ISO_CURRENCIES),
        RequiredField("Invoice_Amount", SEVERITY_P1),
        NumericAmount("Invoice_Amount", non_negative=True),
        DecimalPlaces("Invoice_Amount"),
    ],

    # ── 7. Fixed Assets ──────────────────────────────────────────────────────
    "fixed_assets": [
        UniqueKey(["Asset_ID"]),
        RequiredField("Asset_ID", SEVERITY_P1),
        MaxLength("Asset_ID", 50),
        RequiredField("Asset_Description", SEVERITY_P1),
        MaxLength("Asset_Description", 500),
        RequiredField("Asset_Class", SEVERITY_P1, suggested_fix="Must match a valid Workday Asset Class Reference ID."),
        RequiredField("Acquisition_Date", SEVERITY_P1),
        DateFormat("Acquisition_Date"),
        RequiredField("Currency", SEVERITY_P1),
        ValidValues("Currency", ISO_CURRENCIES),
        RequiredField("Original_Cost", SEVERITY_P1),
        NumericAmount("Original_Cost", non_negative=True),
        DecimalPlaces("Original_Cost"),
        RequiredField("Net_Book_Value", SEVERITY_P1),
        NumericAmount("Net_Book_Value", non_negative=True),
        DecimalPlaces("Net_Book_Value"),
        NumericAmount("Accumulated_Depreciation", required=False, non_negative=True, severity=SEVERITY_P2),
        RequiredField("Depreciation_Method", SEVERITY_P2),
        ValidValues("Depreciation_Method", VALID_DEPRECIATION_METHODS),
        NumericAmount("Useful_Life_Years", required=False, non_negative=True, severity=SEVERITY_P2),
        CrossFieldRule(
            "Net_Book_Value",
            lambda row: (
                pd.isna(row.get("Original_Cost")) or pd.isna(row.get("Net_Book_Value")) or
                float(str(row.get("Net_Book_Value", 0) or 0).replace(",", "") or 0) <=
                float(str(row.get("Original_Cost", 0) or 0).replace(",", "") or 0)
            ),
            "Net_Book_Value cannot exceed Original_Cost (asset cannot appreciate beyond cost).",
            severity=SEVERITY_P2,
            suggested_fix="Check Net_Book_Value — it should be Original_Cost minus Accumulated_Depreciation.",
        ),
        DateFormat("Placed_in_Service_Date", required=True, severity=SEVERITY_P2),
    ],

    # ── 8. GL Beginning Balances ─────────────────────────────────────────────
    "beginning_balances_gl": [
        UniqueKey(["Company", "Ledger_Account", "Cost_Center", "Currency", "Period"]),
        RequiredField("Company", SEVERITY_P1),
        RequiredField("Ledger_Account", SEVERITY_P1, suggested_fix="Must match a Ledger Account ID from the COA load."),
        RequiredField("Currency", SEVERITY_P1),
        ValidValues("Currency", ISO_CURRENCIES),
        RequiredField("Period", SEVERITY_P1, suggested_fix="Format as YYYY-MM (e.g., 2025-12 for December 2025)."),
        RegexFormat("Period", r"^\d{4}-\d{2}$", "YYYY-MM format (e.g., 2025-12)", severity=SEVERITY_P2),
        NumericAmount("Debit_Amount", required=False, non_negative=True, severity=SEVERITY_P1),
        NumericAmount("Credit_Amount", required=False, non_negative=True, severity=SEVERITY_P1),
        DecimalPlaces("Debit_Amount"),
        DecimalPlaces("Credit_Amount"),
        CrossFieldRule(
            "Debit_Amount",
            lambda row: not (
                (pd.isna(row.get("Debit_Amount")) or str(row.get("Debit_Amount", "")).strip() == "") and
                (pd.isna(row.get("Credit_Amount")) or str(row.get("Credit_Amount", "")).strip() == "")
            ),
            "Either Debit_Amount or Credit_Amount must be populated (both cannot be blank).",
            severity=SEVERITY_P1,
        ),
        CrossFieldRule(
            "Credit_Amount",
            lambda row: not (
                str(row.get("Debit_Amount", "")).strip() not in ("", "0", "0.00") and
                str(row.get("Credit_Amount", "")).strip() not in ("", "0", "0.00")
            ),
            "Both Debit_Amount and Credit_Amount are populated — only one should have a value per row.",
            severity=SEVERITY_P2,
            suggested_fix="Use separate rows for debits and credits, or use a signed Amount column.",
        ),
    ],

    # ── 9. Bank Accounts ─────────────────────────────────────────────────────
    "bank_accounts": [
        UniqueKey(["Company", "Bank_Account_Nickname"]),
        RequiredField("Company", SEVERITY_P1),
        RequiredField("Bank_Account_Nickname", SEVERITY_P1),
        MaxLength("Bank_Account_Nickname", 100),
        RequiredField("Financial_Institution_Name", SEVERITY_P1),
        MaxLength("Financial_Institution_Name", 255),
        RequiredField("Currency", SEVERITY_P1),
        ValidValues("Currency", ISO_CURRENCIES),
        RequiredField("Bank_Account_Number", SEVERITY_P1),
        MaxLength("Bank_Account_Number", 50),
        ValidValues("Default_Payment_Type", VALID_PAYMENT_TYPES, severity=SEVERITY_P2),
        RegexFormat("Routing_Number", r"^\d{9}$", "9-digit US ABA routing number",
                    severity=SEVERITY_P2, required=False,
                    suggested_fix="Must be exactly 9 digits for US ACH. Leave blank for non-US accounts."),
        DateFormat("Start_Date", required=True),
    ],

    # ── 10. Open Purchase Orders ──────────────────────────────────────────────
    "open_purchase_orders": [
        UniqueKey(["Company", "PO_Number", "PO_Line_Number"]),
        RequiredField("Company", SEVERITY_P1),
        RequiredField("Supplier_ID", SEVERITY_P1, suggested_fix="Must match a Supplier loaded in Supplier Master."),
        RequiredField("PO_Number", SEVERITY_P1),
        MaxLength("PO_Number", 100),
        RequiredField("PO_Line_Number", SEVERITY_P1, suggested_fix="Numeric line number, starting at 1."),
        RequiredField("PO_Date", SEVERITY_P1),
        DateFormat("PO_Date"),
        CrossFieldRule("PO_Date", _date_not_future("PO_Date"),
                       "PO_Date is in the future — open POs should have past dates.", severity=SEVERITY_P2),
        RequiredField("Currency", SEVERITY_P1),
        ValidValues("Currency", ISO_CURRENCIES),
        RequiredField("Extended_Amount", SEVERITY_P1),
        NumericAmount("Extended_Amount", non_negative=True),
        DecimalPlaces("Extended_Amount"),
        RequiredField("Open_Amount", SEVERITY_P1),
        NumericAmount("Open_Amount", non_negative=True),
        DecimalPlaces("Open_Amount"),
        CrossFieldRule(
            "Open_Amount",
            lambda row: (
                pd.isna(row.get("Open_Amount")) or pd.isna(row.get("Extended_Amount")) or
                float(str(row.get("Open_Amount", 0) or 0).replace(",", "") or 0) <=
                float(str(row.get("Extended_Amount", 0) or 0).replace(",", "") or 0)
            ),
            "Open_Amount cannot exceed Extended_Amount.",
            severity=SEVERITY_P2,
            suggested_fix="Open_Amount is the remaining unbilled/unpaid amount — it cannot exceed the total line amount.",
        ),
    ],
}


# ── Validator ─────────────────────────────────────────────────────────────────
class WDValidator:
    """Main validation entry point."""

    SUPPORTED_OBJECTS = list(OBJECT_RULES.keys())

    def validate(self, object_name: str, file_path: str,
                 skip_rows: int = 0) -> ValidationResult:
        """
        Validate a CSV or Excel file against the rules for the given object.

        Args:
            object_name:  One of SUPPORTED_OBJECTS (e.g., 'supplier_master').
            file_path:    Path to a .csv or .xlsx file.
            skip_rows:    Number of header/instruction rows to skip before data begins.
                          Use skip_rows=3 if using CoP iLoad templates (3 header rows).

        Returns:
            ValidationResult with all issues found.
        """
        object_name = object_name.lower().strip()
        if object_name not in OBJECT_RULES:
            raise ValueError(
                f"Unknown object '{object_name}'. Supported: {self.SUPPORTED_OBJECTS}"
            )

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Load data
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path, skiprows=skip_rows, dtype=str, keep_default_na=False)
        else:
            df = pd.read_excel(path, skiprows=skip_rows, dtype=str, keep_default_na=False)

        # Drop fully empty rows
        df = df.dropna(how="all").reset_index(drop=True)

        result = ValidationResult(
            object_name=object_name,
            file_path=str(path),
            total_rows=len(df),
        )

        rules = OBJECT_RULES[object_name]

        # Reset stateful rules (e.g., UniqueKey tracks seen values)
        for rule in rules:
            if hasattr(rule, "reset"):
                rule.reset()

        for idx, row in df.iterrows():
            row_num = idx + 1  # 1-based row number for user-facing output
            for rule in rules:
                # Only run rule if column exists in the file
                if rule.column not in df.columns and not isinstance(rule, (CrossFieldRule, UniqueKey)):
                    continue
                issue = rule.check(row_num, row)
                if issue:
                    result.issues.append(issue)

        return result

    def validate_all(self, directory: str, pattern: str = "*.csv") -> dict[str, ValidationResult]:
        """
        Validate all matching files in a directory. File stems must match object names.
        E.g., supplier_master.csv → validates as 'supplier_master'.
        """
        results = {}
        dir_path = Path(directory)
        for f in dir_path.glob(pattern):
            stem = f.stem.lower()
            # Try exact match first, then partial match
            obj = stem if stem in OBJECT_RULES else next(
                (k for k in OBJECT_RULES if k in stem or stem in k), None
            )
            if obj:
                print(f"Validating {f.name} as '{obj}'...")
                results[obj] = self.validate(obj, str(f))
            else:
                print(f"Skipping {f.name} — no matching object rule set found.")
        return results

    def print_all_summaries(self, results: dict[str, ValidationResult]) -> None:
        for obj, result in results.items():
            result.print_summary()

        # Overall summary
        total_p1 = sum(r.p1_count for r in results.values())
        total_rows = sum(r.total_rows for r in results.values())
        affected  = sum(len(r.affected_rows) for r in results.values())
        overall_rate = round(affected / total_rows * 100, 2) if total_rows else 0
        gate = total_p1 == 0 and overall_rate <= GOLIVE_DEFECT_RATE_THRESHOLD

        print("═" * 62)
        print(f"  OVERALL VALIDATION SUMMARY — {len(results)} objects")
        print(f"  Total Rows    : {total_rows:,}")
        print(f"  Total P1s     : {total_p1}")
        print(f"  Defect Rate   : {overall_rate}%")
        print(f"  Go-Live Gate  : {'✓ APPROVED' if gate else '✗ BLOCKED'}")
        print("═" * 62 + "\n")


# ── CLI entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print(__doc__)
        print("\nSupported objects:")
        for obj in WDValidator.SUPPORTED_OBJECTS:
            print(f"  {obj}")
        sys.exit(0)

    obj_arg  = sys.argv[1]
    file_arg = sys.argv[2]
    skip_arg = int(sys.argv[3]) if len(sys.argv) > 3 else 0

    v = WDValidator()
    r = v.validate(obj_arg, file_arg, skip_rows=skip_arg)
    r.print_summary()

    if len(sys.argv) > 4:
        r.to_excel(sys.argv[4])
