"""
Workday Address & Banking Validator Agent
Accenture Finance Technology Practice

Specialist developer agent for building, extending, and debugging the
address/banking validation solution. Understands Workday formatting
requirements and can fetch external reference data (geocoding, IBAN
registries, central bank codes) to fill in missing or corrected values.

Usage:
    python agents/address_validator_agent.py [--demo] [--validate FILE] [--country CC]
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

# ── Resolve project root ───────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
VALIDATOR_DIR = PROJECT_ROOT / "assets" / "files" / "ai" / "solutions" / "08_address_banking_validator"
sys.path.insert(0, str(VALIDATOR_DIR))

try:
    import workday_validator as wv
    VALIDATOR_OK = True
except ImportError as e:
    VALIDATOR_OK = False
    VALIDATOR_ERR = str(e)

# ── Optional Claude API integration ───────────────────────────────────────────
try:
    import anthropic
    CLAUDE_OK = True
except ImportError:
    CLAUDE_OK = False

# ── Optional requests for web lookup ──────────────────────────────────────────
try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

AGENT_SYSTEM_PROMPT = """You are an expert Workday data migration specialist with deep knowledge of:

1. **Workday Address Field Mapping** — country-specific rules for which address fields
   are Required, Optional, or Not Allowed (Address Lines 1-9, City, City Subdivision,
   Region, Region Subdivision, Postal Code). You know the exact rules for 40+ countries.

2. **Workday Banking Field Requirements** — per-country rules for Routing/Sort Codes,
   Bank Name, Branch, Account Number, BIC/SWIFT, Roll Number (UK), IBAN (EU/UK).

3. **Data correction strategies** — when a postal code is malformed, you know the
   correct format for that country. When a region is missing for USA, you know to
   look up the state from the city name.

4. **External data sources** — you can reason about geocoding APIs (Google Maps,
   OpenStreetMap Nominatim), IBAN validation registries (ibanapi.com), SWIFT/BIC
   directories, and national postal code databases.

When asked to validate or correct data:
- Identify exactly which Workday rule is violated and cite the field name as Workday uses it
- Provide the corrected value when you can determine it with confidence
- Explain why the correction is needed
- Flag ambiguous cases for human review rather than guessing

When asked to extend the validator:
- Write clean, testable Python code
- Follow the patterns in workday_validator.py (rules dicts, normalize functions, detect_columns)
- Preserve the existing API surface so app.py continues to work
"""


class AddressValidatorAgent:
    """Developer agent that specializes in Workday address/banking validation."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = None
        if CLAUDE_OK and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        self.conversation_history: list[dict] = []

    # ── Core chat ──────────────────────────────────────────────────────────────

    def chat(self, user_message: str) -> str:
        if not self.client:
            return self._rule_based_response(user_message)

        self.conversation_history.append({"role": "user", "content": user_message})
        response = self.client.messages.create(
            model="claude-opus-4-8",
            max_tokens=4096,
            system=AGENT_SYSTEM_PROMPT,
            messages=self.conversation_history,
            tools=self._get_tools(),
        )

        assistant_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                assistant_text += block.text
            elif block.type == "tool_use":
                tool_result = self._execute_tool(block.name, block.input)
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content,
                })
                self.conversation_history.append({
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": block.id, "content": tool_result}],
                })
                followup = self.client.messages.create(
                    model="claude-opus-4-8",
                    max_tokens=4096,
                    system=AGENT_SYSTEM_PROMPT,
                    messages=self.conversation_history,
                )
                for fb in followup.content:
                    if hasattr(fb, "text"):
                        assistant_text += fb.text
                break

        self.conversation_history.append({"role": "assistant", "content": assistant_text})
        return assistant_text

    # ── Rule-based fallback (no API key) ──────────────────────────────────────

    def _rule_based_response(self, query: str) -> str:
        q = query.lower()

        if any(w in q for w in ["hello", "hi", "who are you", "what can you do"]):
            return (
                "I'm the Workday Address & Banking Validator Agent. I can:\n"
                "• Explain Workday field rules for any country\n"
                "• Look up postal code formats, IBAN formats, BIC/SWIFT patterns\n"
                "• Identify why a record fails Workday validation\n"
                "• Suggest corrections for malformed addresses or banking data\n"
                "• Help extend the validator with new country rules\n\n"
                "Set ANTHROPIC_API_KEY for Claude-powered intelligent assistance."
            )

        if "country" in q or "rule" in q or "rules for" in q:
            for country, rules in wv.ADDRESS_RULES.items():
                if country.lower() in q:
                    required = [k for k, v in rules.items() if v == "Required"]
                    optional = [k for k, v in rules.items() if v == "Optional"]
                    not_allowed = [k for k, v in rules.items() if v == "Not Allowed"]
                    lines = [f"Workday Address Rules — {country}:", "",
                             f"  Required:     {', '.join(required) or 'none'}",
                             f"  Optional:     {', '.join(optional) or 'none'}",
                             f"  Not Allowed:  {', '.join(not_allowed) or 'none'}"]
                    if country in wv.POSTAL_CODE_PATTERNS:
                        _, desc = wv.POSTAL_CODE_PATTERNS[country]
                        lines.append(f"  Postal format: {desc}")
                    return "\n".join(lines)

            for country, rules in wv.BANKING_RULES.items():
                if country.lower() in q:
                    required = [k for k, v in rules.items() if v == "Required"]
                    optional = [k for k, v in rules.items() if v == "Optional"]
                    na = [k for k, v in rules.items() if v == "N/A"]
                    return (
                        f"Workday Banking Rules — {country}:\n\n"
                        f"  Required: {', '.join(required) or 'none'}\n"
                        f"  Optional: {', '.join(optional) or 'none'}\n"
                        f"  N/A:      {', '.join(na) or 'none'}"
                    )

        if "iban" in q:
            return (
                "IBAN Format: 2-letter country code + 2 check digits + BBAN (up to 30 chars)\n"
                "Examples:\n"
                "  GB29 NWBK 6016 1331 9268 19  (UK, 22 chars)\n"
                "  DE89 3704 0044 0532 0130 00  (Germany, 22 chars)\n"
                "  FR76 3000 6000 0112 3456 7890 189  (France, 27 chars)\n\n"
                "Workday requires IBAN for: UK, Germany, France, Italy, Spain, Belgium,\n"
                "Switzerland, Sweden, Austria, Netherlands, Ireland, Portugal, Denmark, Finland"
            )

        if "bic" in q or "swift" in q:
            return (
                "BIC/SWIFT Format: 8 or 11 characters\n"
                "  AAAA BB CC [DDD]\n"
                "  AAAA = Institution code (4 letters)\n"
                "  BB   = Country code (2 letters, ISO 3166)\n"
                "  CC   = Location code (2 alphanumeric)\n"
                "  DDD  = Branch code (3 alphanumeric, optional — XXX = head office)\n\n"
                "Example: CHASUS33 = JPMorgan Chase, US\n"
                "         BARCGB22 = Barclays, UK\n"
                "         DEUTDEDB = Deutsche Bank, Germany"
            )

        if "postal" in q or "zip" in q:
            out = ["Postal Code Formats by Country:\n"]
            for country, (pattern, desc) in list(wv.POSTAL_CODE_PATTERNS.items())[:15]:
                out.append(f"  {country:30s}  {desc}")
            out.append(f"\n  ... and {len(wv.POSTAL_CODE_PATTERNS) - 15} more")
            return "\n".join(out)

        if "list" in q and ("country" in q or "countries" in q):
            addr_countries = sorted(wv.ADDRESS_RULES.keys())
            return (
                f"Address validation rules cover {len(addr_countries)} countries:\n"
                + "\n".join(f"  • {c}" for c in addr_countries)
            )

        return (
            "I can answer questions about Workday address/banking validation rules.\n"
            "Try asking:\n"
            "  • 'What are the address rules for Japan?'\n"
            "  • 'What banking fields are required for UK?'\n"
            "  • 'What is the correct IBAN format?'\n"
            "  • 'List all supported countries'\n"
            "  • 'What is the postal code format for Germany?'\n\n"
            "Set ANTHROPIC_API_KEY to enable Claude-powered intelligent assistance."
        )

    # ── Tool definitions (used when Claude API is available) ──────────────────

    def _get_tools(self) -> list[dict]:
        return [
            {
                "name": "get_address_rules",
                "description": "Get Workday address field rules for a specific country",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "country": {"type": "string", "description": "Country name or ISO 2-letter code"},
                    },
                    "required": ["country"],
                },
            },
            {
                "name": "get_banking_rules",
                "description": "Get Workday banking field rules for a specific country",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "country": {"type": "string", "description": "Country name or ISO 2-letter code"},
                    },
                    "required": ["country"],
                },
            },
            {
                "name": "lookup_postal_code",
                "description": "Look up postal code information via Nominatim geocoding",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"},
                        "country": {"type": "string"},
                    },
                    "required": ["city", "country"],
                },
            },
            {
                "name": "validate_iban",
                "description": "Validate an IBAN number using the ISO 7064 MOD-97-10 algorithm",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "iban": {"type": "string", "description": "The IBAN to validate"},
                    },
                    "required": ["iban"],
                },
            },
        ]

    def _execute_tool(self, name: str, inputs: dict) -> str:
        if name == "get_address_rules":
            country = wv.normalize_country(inputs["country"])
            rules = wv.ADDRESS_RULES.get(country, wv.ADDRESS_RULES_GENERIC)
            postal = wv.POSTAL_CODE_PATTERNS.get(country)
            result = {"country": country, "rules": rules}
            if postal:
                result["postal_format"] = postal[1]
            return json.dumps(result, indent=2)

        if name == "get_banking_rules":
            country = wv.normalize_banking_country(inputs["country"])
            rules = wv.BANKING_RULES.get(country, wv.BANKING_RULES_GENERIC)
            return json.dumps({"country": country, "rules": rules}, indent=2)

        if name == "lookup_postal_code":
            if not REQUESTS_OK:
                return json.dumps({"error": "requests library not installed"})
            try:
                resp = requests.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": f"{inputs['city']}, {inputs['country']}", "format": "json", "limit": 1},
                    headers={"User-Agent": "WorkdayValidatorAgent/1.0"},
                    timeout=10,
                )
                data = resp.json()
                if data:
                    return json.dumps({"result": data[0]})
                return json.dumps({"result": None, "message": "No geocoding result found"})
            except Exception as e:
                return json.dumps({"error": str(e)})

        if name == "validate_iban":
            iban = inputs["iban"].replace(" ", "").upper()
            valid, msg = _validate_iban_checksum(iban)
            return json.dumps({"iban": iban, "valid": valid, "message": msg})

        return json.dumps({"error": f"Unknown tool: {name}"})


def _validate_iban_checksum(iban: str) -> tuple[bool, str]:
    """ISO 7064 MOD-97-10 IBAN checksum validation."""
    if len(iban) < 5:
        return False, "IBAN too short"
    rearranged = iban[4:] + iban[:4]
    numeric = ""
    for ch in rearranged:
        if ch.isdigit():
            numeric += ch
        elif ch.isalpha():
            numeric += str(ord(ch) - ord("A") + 10)
        else:
            return False, f"Invalid character: {ch}"
    if int(numeric) % 97 == 1:
        return True, "Valid IBAN (checksum passed)"
    return False, "Invalid IBAN (checksum failed — check digits incorrect)"


# ── Demo / CLI ─────────────────────────────────────────────────────────────────

def run_demo():
    print("\n" + "=" * 62)
    print("  Workday Address & Banking Validator Agent — Demo Mode")
    print("=" * 62 + "\n")

    if not VALIDATOR_OK:
        print(f"ERROR: Could not load workday_validator: {VALIDATOR_ERR}")
        print(f"Ensure {VALIDATOR_DIR} contains workday_validator.py")
        return

    agent = AddressValidatorAgent()
    demo_queries = [
        "What are the Workday address rules for Japan?",
        "What banking fields are required for the United Kingdom?",
        "Is IBAN required for Germany?",
        "What is the correct postal code format for Canada?",
        "What fields are NOT allowed in a Workday address for Hong Kong?",
    ]

    for query in demo_queries:
        print(f"Q: {query}")
        print(f"A: {agent.chat(query)}")
        print("-" * 50)

    print("\nAgent capabilities summary:")
    print(f"  • Address rules:   {len(wv.ADDRESS_RULES)} countries")
    print(f"  • Banking rules:   {len(wv.BANKING_RULES)} countries")
    print(f"  • Postal patterns: {len(wv.POSTAL_CODE_PATTERNS)} countries")
    print(f"  • Claude API:      {'Connected' if agent.client else 'Not configured (set ANTHROPIC_API_KEY)'}")
    print(f"  • Web lookup:      {'Available' if REQUESTS_OK else 'Install requests library'}")


def run_interactive():
    if not VALIDATOR_OK:
        print(f"ERROR: {VALIDATOR_ERR}")
        sys.exit(1)

    agent = AddressValidatorAgent()
    print("\nWorkday Address & Banking Validator Agent")
    print("Type 'exit' to quit.\n")
    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break
        if user_input.lower() in ("exit", "quit", "q"):
            break
        if not user_input:
            continue
        response = agent.chat(user_input)
        print(f"\nAgent: {response}\n")


def validate_file_cli(file_path: str, mode: str = "address"):
    if not VALIDATOR_OK:
        print(f"ERROR: {VALIDATOR_ERR}")
        sys.exit(1)
    print(f"Validating: {file_path}")
    if mode == "banking":
        result = wv.validate_banking_file(file_path)
    else:
        result = wv.validate_address_file(file_path)
    s = result["summary"]
    print(f"  Total: {s['total']}  Valid: {s['valid']}  Warnings: {s['warnings']}  Errors: {s['errors']}")
    print(f"  Output: {result['output_path']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Workday Address & Banking Validator Agent")
    parser.add_argument("--demo", action="store_true", help="Run demonstration")
    parser.add_argument("--interactive", action="store_true", help="Interactive Q&A mode")
    parser.add_argument("--validate", metavar="FILE", help="Validate a file")
    parser.add_argument("--mode", choices=["address", "banking"], default="address",
                        help="Validation mode for --validate (default: address)")
    args = parser.parse_args()

    if args.validate:
        validate_file_cli(args.validate, args.mode)
    elif args.interactive:
        run_interactive()
    else:
        run_demo()
