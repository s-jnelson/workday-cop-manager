"""
Demo launcher for the Workday Address & Banking Data Validator.
Called from the dashboard "Run Demo" button via api/server.py.
Prints status info instead of actually starting the server (which
requires a long-running process -- start app.py separately for the
live web UI on http://localhost:8090).
"""
import sys
import io
from pathlib import Path

# Force UTF-8 output so special chars work on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TOOL_DIR = Path(__file__).parent

print("=" * 60)
print("  Workday Address & Banking Data Validator")
print("  Accenture Finance Technology Practice")
print("=" * 60)
print()
print("OVERVIEW")
print("--------")
print("A client-facing web application that validates address and")
print("banking data against official Workday field-mapping rules")
print("for 40+ countries -- no Workday tenant or API key required.")
print()
print("CAPABILITIES")
print("------------")
print("  Address Validation:")
print("    [*] Checks 40+ country-specific required/optional/not-allowed rules")
print("    [*] Validates postal code format per country (regex patterns)")
print("    [*] Flags fields populated where Workday disallows them")
print("    [*] Corrects spacing, casing, and removes prohibited fields")
print()
print("  Banking Validation:")
print("    [*] Checks 35+ country-specific banking field requirements")
print("    [*] Validates IBAN format (2-letter country code + check digits)")
print("    [*] Validates BIC/SWIFT format (8 or 11 chars)")
print("    [*] Flags N/A fields that should be left blank")
print()
print("  Output:")
print("    [*] Color-coded Excel: green (valid), amber (warning), red (error)")
print("    [*] Validation Status, Issues, and Suggestions columns appended")
print("    [*] Workday-ready corrected field columns")
print("    [*] Summary sheet with totals")
print()
print("QUICK VALIDATION CHECK")
print("----------------------")

try:
    sys.path.insert(0, str(TOOL_DIR))
    import workday_validator as wv
    countries_addr = len(wv.ADDRESS_RULES)
    countries_bank = len(wv.BANKING_RULES)
    postal_patterns = len(wv.POSTAL_CODE_PATTERNS)
    aliases = len(wv.COUNTRY_ALIASES)
    print(f"  [OK] Validator engine loaded successfully")
    print(f"  [OK] Address rules:      {countries_addr} countries")
    print(f"  [OK] Banking rules:      {countries_bank} countries")
    print(f"  [OK] Postal patterns:    {postal_patterns} countries")
    print(f"  [OK] Country aliases:    {aliases} recognized codes/names")
except Exception as e:
    print(f"  [ERROR] Error loading validator engine: {e}")
    sys.exit(1)

print()
print("DEPENDENCIES")
print("------------")
deps = ["flask", "flask_cors", "openpyxl", "pandas"]
for dep in deps:
    try:
        __import__(dep)
        print(f"  [OK] {dep}")
    except ImportError:
        print(f"  [MISSING] {dep}  -- run: pip install {dep}")

print()
print("HOW TO LAUNCH THE WEB UI")
print("------------------------")
print("  python assets/files/ai/solutions/08_address_banking_validator/app.py")
print()
print("  Then open: http://localhost:8090")
print()
print("SUPPORTED FILE FORMATS")
print("----------------------")
print("  Input:  .xlsx, .xls, .csv")
print("  Output: .xlsx (color-coded with validation results)")
print()
print("COUNTRY COVERAGE (sample)")
print("-------------------------")
sample = ["United States of America", "United Kingdom", "Germany", "Japan",
          "Australia", "Canada", "India", "Singapore", "Brazil", "France",
          "Finland", "Hong Kong", "United Arab Emirates", "Mexico", "South Africa"]
for c in sample:
    in_addr = "[ADDR]" if c in wv.ADDRESS_RULES else "[ -- ]"
    canon = wv.normalize_banking_country(c)
    in_bank = "[BANK]" if canon in wv.BANKING_RULES else "[ -- ]"
    print(f"  {in_addr}  {in_bank}  --  {c}")
print(f"  ... and {countries_addr - len(sample)} more countries")
print()
print("=" * 60)
print("  Ready. Start the web server with the command above.")
print("=" * 60)
