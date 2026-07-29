#!/usr/bin/env python3
"""
Workday Integration Error Diagnostics Tool
===========================================
Analyzes Workday integration error logs using pattern matching and optional
Claude AI to produce root-cause diagnoses and numbered resolution steps.

Input modes:
  --file <path>   : Read error log from a file
  --stdin         : Read from stdin (pipe-friendly)
  Interactive     : Prompts user to paste error text (default if no flag)

Usage:
    python 03_integration_error_diagnostics.py --file error.log
    python 03_integration_error_diagnostics.py --stdin < error.log
    python 03_integration_error_diagnostics.py --no-ai --file error.log
    python 03_integration_error_diagnostics.py --save --file error.log
    python 03_integration_error_diagnostics.py
"""

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# ---------------------------------------------------------------------------
# Workday error pattern library
# ---------------------------------------------------------------------------
# Each key is a pattern name. Patterns are lists of regex strings (OR logic).
# Resolution steps are numbered strings for display.

ERROR_PATTERN_LIBRARY = {
    "XSLT_TRANSFORM": {
        "patterns": [r"XSLT", r"transform(?:ation)?", r"XSL"],
        "error_type": "XSLT Transformation Error",
        "common_cause": "The XSLT stylesheet has a syntax error, references an undefined variable, or the input XML does not match the expected schema.",
        "resolution_steps": [
            "Open the integration in Workday Studio and locate the XSLT transform step.",
            "Validate the XSLT file using an XML/XSLT validator (e.g., Saxon, Oxygen XML).",
            "Check that all referenced XPath expressions match the actual XML input structure.",
            "Confirm the input document encoding (UTF-8 is required; BOM can cause silent failures).",
            "Test the transform with a sample payload using the Studio test harness.",
            "Redeploy the integration after fixing and run a test launch.",
        ],
        "prevention": "Add schema validation before the transform step. Store XSLT in source control with version tags.",
        "escalation": "If the XSLT logic is correct but the error persists, raise a Workday Support case with the integration WSDL and sample payload.",
        "est_resolution_hours": "2–4 hours",
    },
    "ISU_AUTH": {
        "patterns": [r"ISU", r"Integration System User", r"Functional Area.*permission", r"Security Group"],
        "error_type": "ISU Authentication / Permission Error",
        "common_cause": "The Integration System User (ISU) account lacks permissions for the target Workday functional area, or the ISU password has expired.",
        "resolution_steps": [
            "In Workday, navigate to: View Integration System User > [ISU Name].",
            "Check 'Security Group Memberships' — ensure the required domain security policies are included.",
            "Verify the ISU password has not expired (check 'Password Expiration' field).",
            "If a new domain was accessed, add the ISU to the appropriate Integration Security Group.",
            "Reset the ISU credentials in the integration's credential store if the password was rotated.",
            "Run 'Maintain Password Rules' to confirm the ISU is exempt from expiry if required.",
        ],
        "prevention": "Use a dedicated ISU per integration family. Document which security groups each ISU requires. Set calendar reminders for credential rotation.",
        "escalation": "If security group assignment does not resolve the issue, engage your Workday Security Administrator or open a support ticket with tenant name and ISU details.",
        "est_resolution_hours": "1–3 hours",
    },
    "XML_SCHEMA": {
        "patterns": [r"XSD", r"schema validation", r"xs:element", r"cvc-", r"not valid according"],
        "error_type": "XML Schema Validation Error",
        "common_cause": "The integration payload does not conform to the Workday Web Services (WWS) XSD schema — often due to missing required elements, incorrect data types, or namespace mismatches.",
        "resolution_steps": [
            "Capture the full XML payload from the integration log or Studio test run.",
            "Download the relevant WWS XSD from Workday Community (search 'Workday Web Services XSD').",
            "Validate the payload against the XSD using SoapUI or Oxygen XML.",
            "Fix missing required fields, correct data type formats (dates must be YYYY-MM-DD), and verify namespace declarations.",
            "Check if the Workday tenant is on a newer API version that introduced schema changes.",
            "Update the integration schema reference version if the tenant was upgraded.",
        ],
        "prevention": "Pin XSD versions in integration specs. Run schema validation in a pre-production sandbox after every Workday update.",
        "escalation": "If schema errors reference Workday internal elements (wsd: prefix), open a Workday Support case — this may indicate a platform bug.",
        "est_resolution_hours": "2–6 hours",
    },
    "SOAP_FAULT": {
        "patterns": [r"SOAP", r"soap:Fault", r"faultstring", r"faultcode", r"Envelope"],
        "error_type": "SOAP Fault",
        "common_cause": "The SOAP request is malformed, references an invalid operation, or the Workday WWS returned a business validation error.",
        "resolution_steps": [
            "Extract the full SOAP fault from the error log — look for <faultcode> and <faultstring> elements.",
            "Check <faultstring> for a Workday validation message (e.g., 'Duplicate ID', 'Inactive Worker').",
            "Validate the SOAP envelope structure against the WSDL using SoapUI.",
            "Confirm the SOAP action header matches the operation name.",
            "If the fault is a business rule violation, review the input data (worker status, effective dates, etc.).",
            "Test the corrected payload in SoapUI against a sandbox tenant before reprocessing.",
        ],
        "prevention": "Use SoapUI mock tests during development. Log full SOAP envelopes (with PII masked) for troubleshooting.",
        "escalation": "If the fault code contains 'INTERNAL_ERROR' or a stack trace, open a P2 support case with Workday including the full fault envelope.",
        "est_resolution_hours": "1–4 hours",
    },
    "CONNECTIVITY": {
        "patterns": [r"timeout", r"connection refused", r"ETIMEDOUT", r"connect timed out", r"UnknownHostException", r"No route to host"],
        "error_type": "Connectivity / Timeout Error",
        "common_cause": "Network connectivity between the integration host and Workday (or the external endpoint) is interrupted — could be firewall rules, DNS failure, or the target service is down.",
        "resolution_steps": [
            "Test connectivity to the endpoint from the integration host: `curl -v https://<host>` or `nslookup <host>`.",
            "Check if the Workday tenant is in a maintenance window (see Workday Status page: status.workday.com).",
            "Verify firewall rules allow outbound HTTPS (443) from the integration server to *.workday.com.",
            "If the external endpoint is the target, confirm it is accessible and check its health dashboard.",
            "Review timeout settings in the integration connector — increase if the payload is large.",
            "Check for VPN or proxy issues if traffic must traverse a corporate network.",
        ],
        "prevention": "Implement retry logic with exponential backoff in the integration. Set up monitoring alerts for endpoint availability.",
        "escalation": "If Workday is the unreachable endpoint and the status page shows no incident, open a P1 support case immediately.",
        "est_resolution_hours": "0.5–2 hours (if external); raise support case immediately if Workday-side",
    },
    "EIB_COLUMN": {
        "patterns": [r"EIB", r"Expected Columns", r"column count", r"column mismatch", r"header row"],
        "error_type": "EIB Column Mismatch Error",
        "common_cause": "The EIB (Enterprise Interface Builder) input file has a different number of columns or column names than the template expects — often caused by adding/removing columns in an Excel export.",
        "resolution_steps": [
            "Download the current EIB template from Workday: View EIB > [Integration Name] > Download Template.",
            "Compare the template column headers row-by-row against the input file.",
            "Re-map or re-order columns in the input file to match the template exactly (case-sensitive).",
            "Remove any extra columns not in the template (Excel often adds hidden columns).",
            "Ensure the file is saved as CSV UTF-8 (not ANSI or UTF-16) with no BOM.",
            "Re-upload through the EIB launch page and review the validation report.",
        ],
        "prevention": "Always generate the input file from the EIB template. Store the template in a shared location and refresh after Workday updates.",
        "escalation": "If the template itself seems corrupted, rebuild the EIB from scratch in a sandbox or contact your Workday HCM/Finance functional lead.",
        "est_resolution_hours": "1–2 hours",
    },
    "ILOAD_REFERENCE": {
        "patterns": [r"iLoad", r"Invalid Reference", r"WID", r"Reference ID.*not found", r"does not exist in Workday"],
        "error_type": "Invalid Workday Reference ID (iLoad)",
        "common_cause": "The integration is referencing a Workday object (Cost Center, Worker, Position, etc.) by an ID that does not exist or has been inactivated in the target tenant.",
        "resolution_steps": [
            "Identify the failing Reference ID from the error message.",
            "In Workday, search for the object using 'Find by Reference ID' or the relevant search report.",
            "Confirm whether the object is Active, Inactive, or never existed in this tenant.",
            "If migrating between tenants (e.g., sandbox to production), re-extract Reference IDs from the target tenant.",
            "Update the integration source data or mapping table with valid Reference IDs.",
            "Run the integration in test mode against a small batch before full reprocessing.",
        ],
        "prevention": "Maintain a cross-reference table of Workday Reference IDs per tenant. Validate reference IDs in a pre-run lookup before submitting the full load.",
        "escalation": "If objects were accidentally inactivated in production, engage your Workday Functional Admin to restore them or create equivalent replacements.",
        "est_resolution_hours": "2–8 hours (depends on data volume)",
    },
    "ENDPOINT_404": {
        "patterns": [r"404", r"not found", r"No resource found", r"Resource.*not found"],
        "error_type": "Endpoint Not Found (404)",
        "common_cause": "The API endpoint URL is incorrect, the Workday service version has changed, or the integration is pointed at a decommissioned endpoint.",
        "resolution_steps": [
            "Confirm the full endpoint URL from the integration configuration.",
            "Check Workday Community for any deprecation notices for this API version.",
            "Compare the URL against the current WSDL endpoint from Workday's tenant-specific URL.",
            "Update the endpoint URL in the integration connector to the current version.",
            "Test the corrected URL with a basic GET/POST in Postman or SoapUI.",
            "If using a partner integration, check if the partner has changed their callback URL.",
        ],
        "prevention": "Store API endpoint URLs as environment-specific configuration variables. Subscribe to Workday release notes for API deprecation notices.",
        "escalation": "If the Workday-side endpoint is 404 and the URL is correct, raise a support case — the service may have been relocated in a platform update.",
        "est_resolution_hours": "1–3 hours",
    },
    "AUTH_401": {
        "patterns": [r"401", r"unauthorized", r"Unauthorized", r"Authentication failed", r"Invalid credentials"],
        "error_type": "Authentication Error (401 Unauthorized)",
        "common_cause": "The credentials used by the integration (API key, OAuth token, ISU password, or certificate) are invalid, expired, or not authorized for this resource.",
        "resolution_steps": [
            "Check the integration credential store for the affected connection — verify username and password/token.",
            "If using OAuth 2.0, confirm the access token has not expired and the refresh token flow is working.",
            "For certificate-based auth, check the certificate expiry date and ensure it is still trusted by Workday.",
            "Regenerate the API key or ISU password and update the integration configuration.",
            "Test authentication separately using Postman with the same credentials.",
            "Confirm the user/ISU account is not locked due to failed login attempts.",
        ],
        "prevention": "Set calendar alerts 30 days before credential/certificate expiry. Use a secrets manager rather than hardcoding credentials.",
        "escalation": "If authentication fails immediately after a credential reset, engage the Workday Security Admin — the account may be flagged or have a concurrent session conflict.",
        "est_resolution_hours": "0.5–2 hours",
    },
    "WORKDAY_500": {
        "patterns": [r"500", r"internal server error", r"Internal Server Error", r"Unexpected error", r"NullPointerException"],
        "error_type": "Workday Internal Server Error (500)",
        "common_cause": "Workday encountered an unexpected error processing the request — could be a platform bug, a corrupt data condition, or resource exhaustion on the tenant.",
        "resolution_steps": [
            "Record the exact timestamp and full error stack trace from the integration log.",
            "Check status.workday.com for any ongoing incidents affecting your Workday product.",
            "Retry the operation with a smaller batch size to see if the error is data-specific.",
            "Attempt the same operation manually in the Workday UI to isolate if it's integration-only.",
            "Collect: tenant name, operation name, timestamp, transaction ID, and full error body.",
            "Open a Workday Support ticket (Priority 1 if production-blocking) with all collected details.",
        ],
        "prevention": "Implement error alerting so 500s are caught immediately. Log transaction IDs for every call to correlate with Workday support investigations.",
        "escalation": "Escalate to P1 if the 500 blocks a critical business process. Include your Customer Success Manager if the incident persists beyond 2 hours.",
        "est_resolution_hours": "2–24 hours (Workday investigation required)",
    },
    "RATE_LIMIT": {
        "patterns": [r"rate limit", r"429", r"Too Many Requests", r"throttl", r"quota exceeded"],
        "error_type": "API Rate Limiting (429 Too Many Requests)",
        "common_cause": "The integration is exceeding Workday's API call rate limits — common when running bulk operations, parallel threads, or scheduled jobs that overlap.",
        "resolution_steps": [
            "Check the integration's concurrency settings — reduce parallel threads if running multiple workers.",
            "Implement exponential backoff retry logic: wait 1s, 2s, 4s, 8s between retries.",
            "Stagger scheduled integration runs to avoid concurrent peaks (e.g., offset by 15 minutes).",
            "Review Workday API rate limit documentation for your specific service (Community > Developer).",
            "Move bulk data loads to off-peak hours (e.g., overnight batch windows).",
            "If rate limits are consistently hit at normal volumes, request a limit increase via Workday Support.",
        ],
        "prevention": "Build rate-limit-aware HTTP clients with automatic retry. Monitor API call volume per tenant per hour. Use Workday Prism/data lake for high-volume reads instead of API.",
        "escalation": "If rate limits cannot be avoided due to business requirements, open an architectural review with Workday to discuss approved bulk patterns.",
        "est_resolution_hours": "1–4 hours to implement backoff",
    },
    "PAYROLL_CONNECTOR": {
        "patterns": [r"PECI", r"PICOF", r"payroll connector", r"Payroll Interface", r"pay group", r"payroll extract"],
        "error_type": "Payroll Connector Error (PECI/PICOF)",
        "common_cause": "The PECI (Payroll Effective Change Interface) or PICOF (Payroll Input Connector Output File) has a data issue — often an unmapped pay component, an out-of-sync effective date, or a missing worker record on the payroll provider side.",
        "resolution_steps": [
            "Open the payroll run in Workday and view the connector output file for the affected period.",
            "Identify which worker(s) or pay components are in error from the connector log.",
            "Verify that all pay components referenced in the PECI file are mapped in the payroll provider's system.",
            "Check effective dates — PECI changes must align with the payroll period calendar.",
            "If a worker is missing on the provider side, trigger a full worker sync (PICOF full file) for that employee.",
            "Reprocess the payroll run after resolving data issues and confirm the connector completes clean.",
        ],
        "prevention": "Run payroll connector validation reports before each pay cycle. Maintain a mapping document between Workday pay components and payroll system codes.",
        "escalation": "Engage both your Workday Payroll Functional Lead and the payroll provider's integration team simultaneously — payroll errors often require coordinated investigation.",
        "est_resolution_hours": "4–16 hours (payroll cycles are time-critical; escalate immediately)",
    },
}

# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------

def match_patterns(error_text: str) -> tuple[Optional[str], dict, float]:
    """
    Scan error text against all patterns. Return (best_key, pattern_info, confidence_score).
    Confidence is based on number of pattern matches.
    """
    scores: dict[str, int] = {}

    for key, info in ERROR_PATTERN_LIBRARY.items():
        score = 0
        for pattern in info["patterns"]:
            if re.search(pattern, error_text, re.IGNORECASE):
                score += 1
        if score > 0:
            scores[key] = score

    if not scores:
        return None, {}, 0.0

    best_key = max(scores, key=lambda k: scores[k])
    best_score = scores[best_key]
    max_patterns = len(ERROR_PATTERN_LIBRARY[best_key]["patterns"])
    confidence = min(1.0, best_score / max(1, max_patterns))

    return best_key, ERROR_PATTERN_LIBRARY[best_key], confidence


# ---------------------------------------------------------------------------
# Claude AI diagnosis
# ---------------------------------------------------------------------------

def generate_ai_diagnosis(client: "anthropic.Anthropic", error_text: str,
                           matched_key: Optional[str], matched_info: dict) -> dict:
    """Call Claude for a structured diagnosis of the integration error."""

    pattern_context = ""
    if matched_key and matched_info:
        pattern_context = f"""
Pattern matching identified this as likely: {matched_info['error_type']}
Common cause from knowledge base: {matched_info['common_cause']}
"""

    prompt = f"""You are a Workday integration expert and technical support specialist.
Analyze this Workday integration error and provide a structured diagnosis.

ERROR LOG / TEXT:
---
{error_text[:3000]}
---
{pattern_context}

Provide your analysis in this exact format:

ROOT CAUSE:
[2-3 sentences explaining the specific root cause based on the error details]

RESOLUTION STEPS:
1. [First step]
2. [Second step]
3. [Third step]
4. [Additional steps as needed, max 6 total]

PREVENTION MEASURES:
- [Measure 1]
- [Measure 2]
- [Measure 3 if needed]

ESCALATION PATH:
[Who to contact and when if the above steps don't resolve the issue]

ESTIMATED RESOLUTION TIME:
[Time estimate with brief reasoning]

Be specific to the actual error text provided. Use Workday terminology correctly.
Do not recommend steps that require information not available in the error."""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        return {"ai_text": raw, "error": None}
    except Exception as exc:
        return {"ai_text": None, "error": str(exc)}


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_pattern_diagnosis(matched_key: str, matched_info: dict, confidence: float) -> str:
    """Format the rule-based pattern match output."""
    lines = [
        "=" * 70,
        "WORKDAY INTEGRATION ERROR DIAGNOSIS",
        "=" * 70,
        f"Error Type:   {matched_info['error_type']}",
        f"Pattern Key:  {matched_key}",
        f"Confidence:   {confidence:.0%}",
        "",
        "COMMON CAUSE:",
        f"  {matched_info['common_cause']}",
        "",
        "RESOLUTION STEPS:",
    ]
    for i, step in enumerate(matched_info["resolution_steps"], 1):
        lines.append(f"  {i}. {step}")

    lines += [
        "",
        "PREVENTION MEASURES:",
        f"  {matched_info['prevention']}",
        "",
        "ESCALATION PATH:",
        f"  {matched_info['escalation']}",
        "",
        "ESTIMATED RESOLUTION TIME:",
        f"  {matched_info['est_resolution_hours']}",
        "=" * 70,
    ]
    return "\n".join(lines)


def format_ai_diagnosis(ai_result: dict, matched_info: dict) -> str:
    """Format the Claude AI diagnosis output."""
    lines = [
        "=" * 70,
        "WORKDAY INTEGRATION ERROR DIAGNOSIS (AI-Enhanced)",
        "=" * 70,
    ]

    if matched_info:
        lines += [
            f"Detected Pattern: {matched_info['error_type']}",
            "",
        ]

    if ai_result.get("error"):
        lines += [
            "NOTE: Claude AI unavailable — showing pattern-based diagnosis.",
            f"Error: {ai_result['error']}",
        ]
    else:
        lines.append(ai_result["ai_text"])

    lines.append("=" * 70)
    return "\n".join(lines)


def save_diagnosis(diagnosis_text: str, error_text: str) -> str:
    """Save diagnosis to a markdown file."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"diagnosis_{timestamp}.md"

    content = f"""# Workday Integration Error Diagnosis
Generated: {datetime.now(timezone.utc).isoformat()}

## Error Input
```
{error_text[:2000]}{"...(truncated)" if len(error_text) > 2000 else ""}
```

## Diagnosis
```
{diagnosis_text}
```
"""
    with open(filename, "w", encoding="utf-8") as fh:
        fh.write(content)
    return filename


# ---------------------------------------------------------------------------
# Input reading
# ---------------------------------------------------------------------------

def read_interactive() -> str:
    """Prompt user to paste error text interactively."""
    print("Paste your Workday integration error log below.")
    print("Press ENTER on a blank line when done.")
    print("-" * 50)
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "" and lines:
            # Check if last line was also blank (double blank = done)
            break
        lines.append(line)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Workday Integration Error Diagnostics — pattern matching + Claude AI root cause analysis.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Read error from file:
  python 03_integration_error_diagnostics.py --file integration.log

  # Pipe from stdin:
  cat error.log | python 03_integration_error_diagnostics.py --stdin

  # Pattern matching only (no Claude API):
  python 03_integration_error_diagnostics.py --no-ai --file error.log

  # Save diagnosis to markdown:
  python 03_integration_error_diagnostics.py --file error.log --save

  # Interactive paste mode (default if no flags):
  python 03_integration_error_diagnostics.py

Supported Error Pattern Types:
  XSLT_TRANSFORM, ISU_AUTH, XML_SCHEMA, SOAP_FAULT, CONNECTIVITY,
  EIB_COLUMN, ILOAD_REFERENCE, ENDPOINT_404, AUTH_401,
  WORKDAY_500, RATE_LIMIT, PAYROLL_CONNECTOR
        """,
    )
    parser.add_argument("--file", "-f", help="Path to error log file.")
    parser.add_argument("--stdin", "-s", action="store_true", help="Read error text from stdin.")
    parser.add_argument("--no-ai", action="store_true", help="Pattern matching only — skip Claude API.")
    parser.add_argument("--save", action="store_true", help="Save diagnosis to a markdown file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Read error text
    if args.file:
        try:
            error_text = Path(args.file).read_text(encoding="utf-8", errors="replace")
            print(f"Read {len(error_text)} characters from: {args.file}")
        except FileNotFoundError:
            print(f"ERROR: File not found: {args.file}")
            sys.exit(1)
    elif args.stdin:
        error_text = sys.stdin.read()
        print(f"Read {len(error_text)} characters from stdin.")
    else:
        error_text = read_interactive()

    if not error_text.strip():
        print("ERROR: No error text provided.")
        sys.exit(1)

    # Pattern matching
    print("\nScanning error patterns...")
    matched_key, matched_info, confidence = match_patterns(error_text)

    if not matched_key:
        print("WARNING: No known Workday error patterns matched.")
        print("Known patterns:", ", ".join(ERROR_PATTERN_LIBRARY.keys()))
        matched_info = {}

    # Determine AI usage
    use_ai = not args.no_ai
    client = None

    if use_ai:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("Note: ANTHROPIC_API_KEY not set — using pattern-based diagnosis only.")
            use_ai = False
        elif not ANTHROPIC_AVAILABLE:
            print("Note: anthropic package not installed — using pattern-based diagnosis only.")
            use_ai = False
        else:
            client = anthropic.Anthropic(api_key=api_key)

    # Generate diagnosis
    print()
    if use_ai:
        print("Generating AI-enhanced diagnosis with Claude...")
        ai_result = generate_ai_diagnosis(client, error_text, matched_key, matched_info)
        diagnosis_text = format_ai_diagnosis(ai_result, matched_info)
    elif matched_key:
        diagnosis_text = format_pattern_diagnosis(matched_key, matched_info, confidence)
    else:
        diagnosis_text = "\n".join([
            "=" * 70,
            "NO MATCHING PATTERN FOUND",
            "=" * 70,
            "This error does not match any known Workday integration error patterns.",
            "",
            "Recommended actions:",
            "  1. Search Workday Community (community.workday.com) for the error message.",
            "  2. Check the Workday release notes for recent API/integration changes.",
            "  3. Open a Workday Support ticket with the full error log.",
            "  4. Set ANTHROPIC_API_KEY and remove --no-ai flag for AI-assisted diagnosis.",
            "=" * 70,
        ])

    print(diagnosis_text)

    if args.save:
        saved_path = save_diagnosis(diagnosis_text, error_text)
        print(f"\nDiagnosis saved to: {saved_path}")


if __name__ == "__main__":
    main()
