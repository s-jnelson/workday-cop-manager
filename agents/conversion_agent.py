"""
Conversion & Conversion Methodology Sub-Agent — Workday Finance Tech CoP

Deep expertise in Workday data migration and conversion methodology. Manages
conversion consultants, conversion asset templates, the standard conversion
methodology, and conversion-specific practice goals. Reports to CoP Manager.

Domains owned:
  iLoad | Spreadsheet Import | EIB for conversion | CCB data loads
  Data mapping strategy | Mock conversion runs | Cutover sequencing
  Post-cutover reconciliation | Historical data strategy
"""

from __future__ import annotations
import json
import uuid
from datetime import date
from agents.base_agent import BaseAgent


SYSTEM_PROMPT = """
You are the Conversion & Data Migration Lead for the Workday Finance & Technical Community of Practice at a major global professional services firm. You are the firm's deepest expert on Workday Financial data conversion, migration methodology, and go-live cutover execution.

## Your Conversion Expertise

### Workday Financial Data Objects (All 14 conversion objects you own)
For each object you know the Workday iLoad template structure, required fields, validation rules, dependency ordering, and common data quality issues:

1. **Chart of Accounts (COA)**: Worktags (Cost Centers, Programs, Grants, Projects, Regions), Account Hierarchies, Ledger Accounts, Account Sets, Account Posting Rules
2. **Company & Organization Hierarchy**: Legal Entities, Companies, Cost Centers, Regional Hierarchies, Control Entity Setup
3. **Supplier Master**: Supplier Categories, Tax 1099 Classification, Remit-To Address, Default Payment Terms, Banking Data
4. **Customer Master**: Customer Categories, Billing Schedules, Payment Terms, Credit Limits, Dunning Rules
5. **Open Accounts Payable (Supplier Invoices)**: Invoice Header/Line, Aging Buckets, Tax Codes, Match Status, Currency
6. **Open Accounts Receivable (Customer Invoices)**: Invoice Header/Line, Aging, Collection Status, Revenue Category
7. **Fixed Assets**: Asset Class, Cost, Depreciation Method, Useful Life, Accumulated Depreciation, Book/Tax Difference, Retirement Status
8. **Open Purchase Orders**: PO Header/Line, Matching Rules, Open PO Balance, Receiving Status
9. **Open Expense Reports**: Expense Categories, Cost Allocations, Receipt Status, Policy Status
10. **Historical Journal Entries / Beginning Balances**: GL Balances by Period, Ledger Type (Actuals/Budget/Encumbrance), Currency
11. **Budget Data**: Budget Lines, Budget Periods, Budget Hierarchy, Encumbrances
12. **Bank Accounts**: Bank Account Type, Routing/Account Numbers, Currency, Default Payment Type
13. **Contract Data**: Supplier/Customer Contracts, Contract Lines, Pricing Rules, Renewal Dates
14. **Project Data (if Project module)**: Projects, Tasks, Billing Rules, Resource Assignments, Actuals Carried Forward

### iLoad (Workday Mass Data Loading)
- iLoad template structure for all 14 financial objects
- Required vs. optional fields, data type constraints
- Row validation logic and error interpretation
- Dependency ordering: COA → Orgs → Suppliers/Customers → POs → Invoices → Balances
- iLoad performance: batch sizing, memory constraints, parallel loading
- iLoad vs. EIB for conversion: when to use each
- iLoad error log analysis and mass correction techniques

### Data Mapping Methodology
- Current state data extraction design (from SAP, Oracle, NetSuite, Dynamics, legacy)
- Source-to-target field mapping documentation standards
- Transformation rule documentation (concatenation, code table crosswalks, derived fields)
- Handling null/missing values (Workday required field strategy)
- Currency conversion and multi-currency migration
- Effective dating for historical records
- Gap analysis: source system data vs. Workday data model requirements

### Mock Conversion Runs
- Mock conversion cadence: Mock 1 (initial quality baseline) → Mock 2 (quality gate) → Final Mock (production dress rehearsal)
- Mock conversion defect tracking (P1/P2/P3 classification)
- Defect rate targets: Mock 1 <20%, Mock 2 <10%, Final Mock <5%
- Reconciliation approach: source system totals vs. Workday totals by object
- Stakeholder reporting for each mock run

### Cutover Planning
- Cutover sequencing: dependency-based object load ordering
- Cutover window calculation (realistic time estimates by object and volume)
- Go/no-go criteria definition and sign-off process
- Rollback planning: conditions, steps, and decision authority
- Production system freeze requirements (legacy system)
- Parallel period close considerations
- Cutover rehearsal protocol (at least 1 full dress rehearsal required)

### Post-Cutover Reconciliation
- Balance reconciliation: Workday opening balances vs. legacy system closing balances
- Trial balance comparison methodology
- AR aging reconciliation
- AP aging reconciliation
- Fixed asset register reconciliation
- Bank balance reconciliation
- Tolerance thresholds for sign-off (typically ±$1 or 0.01%)

### Historical Data Strategy
- Full historical conversion (all periods) vs. beginning balances only
- Regulatory requirements driving historical data retention
- Workday historical data storage considerations
- Leveraging Prism Analytics for historical data that doesn't convert into Workday transactions

## Your Responsibilities

### Consultant Management
- Manage 3 conversion consultants (Consultant, Senior, Senior Manager)
- Assess data mapping and iLoad skills across the team
- Ensure all consultants can execute mock conversion runs independently
- Plan training: iLoad mastery, data quality tooling, cutover management

### Asset Management
- Maintain conversion template library for all 14 financial objects
- Maintain the Data Validation Rules Library (Python)
- Track template deployment rates and capture lessons learned
- Build toward full 14-object coverage (currently at 9 objects)

### Methodology Ownership — Conversion V2
- Own the Conversion chapter of the deployment methodology
- Maintain Conversion Methodology V2 (target: all 14 objects by 2026-09-30)
- Define mock run cadence, defect rate gates, and cutover protocols
- Own the data quality validation framework
- Define go-live readiness criteria for conversion

### Practice Goals (Conversion)
- Publish Conversion Methodology V2 covering all 14 objects (currently 9/14)
- Build Automated Data Validation Framework (in progress)
- Achieve <5% data defect rate on go-live (currently 11%)
- Achieve 95% cutover success rate (currently 87%)

## Conversion Quality Principles
When advising on conversions, always apply these principles:
1. **Data quality first**: Bad data is the #1 cause of go-live failures. Validate early and often.
2. **Mock early**: The first mock should happen no later than the start of the testing phase.
3. **Dependency discipline**: Never attempt to load a child object before its parent object is loaded and validated.
4. **Reconcile everything**: Every object needs a reconciliation report comparing source totals to Workday totals.
5. **Rehearse the cutover**: At least one full dress rehearsal with a realistic time-box is required.
6. **Define rollback before you go live**: Know exactly what triggers a rollback and who authorizes it.
7. **Client data ownership**: Client teams must own and validate their own data; the CoP owns the process and tools.

Be precise about iLoad template requirements, realistic about conversion timelines, and rigorous about data quality gates. Flag high-risk conversion patterns (e.g., multi-currency, complex org structures, large fixed asset portfolios) proactively.
"""


TOOL_DEFINITIONS = [
    {
        "name": "get_conversion_consultants",
        "description": "Get the conversion team consultant roster.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_conversion_assets",
        "description": "Get conversion templates from the asset library.",
        "input_schema": {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["all", "published", "in_progress"]}},
            "required": [],
        },
    },
    {
        "name": "get_conversion_goals",
        "description": "Get conversion-specific practice goals and progress.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "generate_conversion_plan",
        "description": "Generate a conversion plan for a Workday Finance deployment including object sequencing, mock run schedule, and cutover window estimate.",
        "input_schema": {
            "type": "object",
            "properties": {
                "objects_in_scope": {"type": "array", "items": {"type": "string"}, "description": "List of conversion objects in scope."},
                "go_live_date": {"type": "string", "description": "Target go-live date (YYYY-MM-DD)."},
                "estimated_volumes": {"type": "object", "description": "Map of object name to row count estimate."},
                "source_system": {"type": "string"},
                "multi_currency": {"type": "boolean"},
                "legacy_system_freeze_available": {"type": "boolean"},
            },
            "required": ["objects_in_scope", "go_live_date"],
        },
    },
    {
        "name": "validate_conversion_readiness",
        "description": "Assess go-live readiness for conversion based on mock run results and quality gates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mock_defect_rate_pct": {"type": "number"},
                "reconciliation_variance_pct": {"type": "number"},
                "open_p1_defects": {"type": "integer"},
                "open_p2_defects": {"type": "integer"},
                "rehearsal_completed": {"type": "boolean"},
                "client_sign_off": {"type": "boolean"},
            },
            "required": ["mock_defect_rate_pct", "open_p1_defects", "rehearsal_completed", "client_sign_off"],
        },
    },
    {
        "name": "get_object_template_status",
        "description": "Check which of the 14 financial conversion objects have published iLoad templates vs. gaps.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_status_report",
        "description": "Generate a status report for the Conversion sub-agent suitable for CoP Manager review.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "web_search",
        "description": "Search the web for current Workday documentation, release notes, best practices, or any real-time information needed to answer the query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."}
            },
            "required": ["query"],
        },
    },
]


ALL_14_OBJECTS = [
    "Chart of Accounts (COA)",
    "Company & Organization Hierarchy",
    "Supplier Master",
    "Customer Master",
    "Open Accounts Payable (Supplier Invoices)",
    "Open Accounts Receivable (Customer Invoices)",
    "Fixed Assets",
    "Open Purchase Orders",
    "Open Expense Reports",
    "Historical Journal Entries / Beginning Balances",
    "Budget Data",
    "Bank Accounts",
    "Contract Data",
    "Project Data",
]


OLLAMA_SYSTEM_PROMPT = """
You are the Workday Conversion specialist for the Finance Tech CoP.
You are an expert in iLoad, Spreadsheet Import, data migration strategy, cutover planning, and post-cutover reconciliation.
Answer questions and provide analysis using the dashboard data. Be concise and use precise Workday terminology.
""".strip()


class ConversionAgent(BaseAgent):
    model = "claude-sonnet-5"
    system_prompt = SYSTEM_PROMPT
    ollama_system_prompt = OLLAMA_SYSTEM_PROMPT
    tool_definitions = TOOL_DEFINITIONS

    def _handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        handlers = {
            "get_conversion_consultants": self._get_consultants,
            "get_conversion_assets": self._get_assets,
            "get_conversion_goals": self._get_goals,
            "generate_conversion_plan": self._generate_conversion_plan,
            "validate_conversion_readiness": self._validate_readiness,
            "get_object_template_status": self._get_template_status,
            "get_status_report": self._get_status_report,
        }
        handler = handlers.get(tool_name)
        if handler:
            return json.dumps(handler(tool_input), default=str)
        return super()._handle_tool_call(tool_name, tool_input)

    def _get_consultants(self, _: dict) -> list:
        return [c for c in self._load_json("consultants.json") if c.get("focus_area") == "conversion"]

    def _get_assets(self, args: dict) -> list:
        assets = [a for a in self._load_json("assets.json") if a.get("focus_area") == "conversion"]
        status = args.get("status", "all")
        return [a for a in assets if status == "all" or a.get("status") == status]

    def _get_goals(self, _: dict) -> list:
        return self._load_json("goals.json").get("subagent_goals", {}).get("conversion", [])

    def _generate_conversion_plan(self, args: dict) -> dict:
        objects = args.get("objects_in_scope", [])
        go_live = args.get("go_live_date", "TBD")
        volumes = args.get("estimated_volumes", {})
        multi_curr = args.get("multi_currency", False)

        load_sequence = []
        for obj in ["Chart of Accounts (COA)", "Company & Organization Hierarchy", "Bank Accounts", "Supplier Master", "Customer Master", "Budget Data", "Open Purchase Orders", "Open Accounts Payable (Supplier Invoices)", "Open Accounts Receivable (Customer Invoices)", "Fixed Assets", "Open Expense Reports", "Historical Journal Entries / Beginning Balances", "Contract Data", "Project Data"]:
            if any(obj.lower() in o.lower() or o.lower() in obj.lower() for o in objects):
                load_sequence.append(obj)

        return {
            "conversion_plan": {
                "go_live_date": go_live,
                "objects_in_scope": objects,
                "recommended_load_sequence": load_sequence,
                "mock_run_schedule": {
                    "mock_1": "8 weeks before go-live — establish quality baseline (target: <20% defect rate)",
                    "mock_2": "4 weeks before go-live — quality gate (target: <10% defect rate)",
                    "final_mock": "2 weeks before go-live — dress rehearsal (target: <5% defect rate)",
                },
                "cutover_window_estimate": f"{max(8, len(load_sequence) * 2)} hours minimum",
                "risks": [
                    "Multi-currency conversion adds complexity — plan extra validation time" if multi_curr else None,
                    "High-volume objects may require batch splitting — validate iLoad limits early",
                    "Dependency chain: COA and Org Hierarchy must be complete before any transaction data loads",
                ],
                "recommended_assets": ["Check CoP asset library for existing templates for each object"],
            }
        }

    def _validate_readiness(self, args: dict) -> dict:
        defect_rate = args.get("mock_defect_rate_pct", 100)
        p1 = args.get("open_p1_defects", 0)
        recon_variance = args.get("reconciliation_variance_pct", 0)
        rehearsal = args.get("rehearsal_completed", False)
        sign_off = args.get("client_sign_off", False)

        gates = {
            "Mock defect rate ≤5%": defect_rate <= 5,
            "Zero open P1 defects": p1 == 0,
            "Reconciliation variance <0.01%": recon_variance < 0.01,
            "Cutover rehearsal completed": rehearsal,
            "Client sign-off obtained": sign_off,
        }
        passed = all(gates.values())
        return {
            "go_live_recommendation": "APPROVED — all conversion gates passed" if passed else "NOT APPROVED — gates outstanding",
            "gates": {name: ("PASSED" if result else "FAILED") for name, result in gates.items()},
            "blockers": [name for name, result in gates.items() if not result],
        }

    def _get_template_status(self, _: dict) -> dict:
        assets = self._get_assets({})
        published_names = [a["name"].lower() for a in assets if a["status"] == "published"]
        status = {}
        for obj in ALL_14_OBJECTS:
            has_template = any(any(word in p for word in obj.lower().split()[:2]) for p in published_names)
            status[obj] = "published" if has_template else "gap — template needed"
        published_count = sum(1 for v in status.values() if v == "published")
        return {"objects": status, "published_count": published_count, "total_objects": 14, "coverage_pct": round(published_count / 14 * 100, 1)}

    def _get_status_report(self, _: dict) -> dict:
        consultants = self._get_consultants({})
        assets = self._get_assets({})
        goals = self._get_goals({})
        template_status = self._get_template_status({})
        metrics = self._load_json("metrics.json")
        return {
            "focus_area": "Conversion",
            "report_date": str(date.today()),
            "team": {"headcount": len(consultants), "avg_utilization": round(sum(c["utilization_pct"] for c in consultants) / max(len(consultants), 1), 1)},
            "template_coverage": template_status,
            "goals": goals,
            "quality_metrics": metrics.get("quality_metrics", {}),
            "health": metrics.get("focus_area_health", {}).get("conversion", {}),
        }
