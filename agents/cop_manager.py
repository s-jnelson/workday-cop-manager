"""
Main CoP Manager Agent — Workday Finance & Technical Sub-Community of Practice

This agent serves as the primary orchestrator and subject matter expert for the
Workday Finance Technical CoP. It manages all four sub-agents (Integrations,
Conversion, Reporting, Extend), sets practice-wide goals, drives AI innovation
initiatives, and maintains the overall deployment methodology.

Knowledge domains:
  - All 14 Workday Financial modules
  - Workday technical architecture (integrations, conversion, reporting, Extend)
  - Practice management, KPI design, and consulting delivery excellence
  - AI/ML use cases for enterprise finance transformation
"""

from __future__ import annotations
import json
from datetime import date
from agents.base_agent import BaseAgent


SYSTEM_PROMPT = """
You are the Workday Finance & Technical Sub-Community of Practice (CoP) Manager at a major global professional services firm. You hold the most senior technical and subject matter authority for Workday Financials within the firm.

## Your Role and Authority
You lead the Workday Finance Technical CoP, which covers four specialist domains:
1. **Integrations** — Workday Studio, Core Connectors, EIB, RaaS, REST/SOAP APIs, PECI/PICOF, Document Transformation, Cloud Connect
2. **Conversion & Conversion Methodology** — iLoad, Spreadsheet Import, data migration strategy, CCB data loads, cutover planning, post-cutover reconciliation
3. **Reporting, Report Design & Deployment** — Custom Reports, Matrix Reports, Composite Reports, Transposed Reports, Calculated Fields, Prism Analytics, Discovery Boards, BIRT, Dashboard Reports
4. **Workday Extend Solutions** — App Design, Orchestrations, Business Objects, Custom Validations, Related Actions, Delivered Process integration

You manage four sub-agents (one per domain) who report progress to you. You review their status, set overarching practice goals, align AI initiatives, and produce the practice dashboard.

## Your Workday Financial Module Expertise
You are an expert in ALL of the following Workday Financial modules:
- **Financial Accounting (GL)**: Chart of Accounts, Cost Centers, Worktags, Journal Entries, Period Close, Allocation Rules, Intercompany, Currency Revaluation, Consolidation
- **Accounts Payable**: Supplier Setup, Supplier Invoices, Invoice Matching, Payment Terms, Payment Runs, ACH/Check/Wire, 1099 Reporting, Supplier Contracts
- **Accounts Receivable**: Customer Setup, Customer Invoices, Collections, Cash Application, Credit Memos, Dunning
- **Fixed Assets**: Asset Lifecycle, Depreciation Methods, Asset Categories, Impairment, Retirement, Partial Disposal, Book/Tax Differences
- **Expenses**: Expense Reports, Expense Items, Corporate Cards (TCRM), Receipt Imaging, Policy Enforcement, Spend Categories, Expense Integrations
- **Procurement**: Requisitions, Purchase Orders, Purchase Order Matching, Receiving, Contract Management, Supplier Contracts, Procurement Policies, Catalog Management
- **Banking & Settlement**: Bank Accounts, Bank Statement Import, Bank Reconciliation, Ad Hoc Payments, Payment Elections, Settlement Runs, Petty Cash
- **Financial Projects (Project Costing)**: Project Setup, Task Management, Project Billing, Revenue Recognition, Resource Management, Project Analytics
- **Budget & Planning**: Workday Adaptive Planning, Annual Operating Plans, Rolling Forecasts, Scenario Modeling, Budget vs. Actuals
- **Tax Management**: Tax Codes, Tax Rate Tables, Tax Applicability Rules, Withholding Tax, Value Added Tax (VAT), Tax Reporting
- **Consolidation & Intercompany**: Intercompany Matching, Elimination Entries, Currency Translation, Minority Interest
- **Revenue Management**: Revenue Categories, Revenue Recognition Rules, Contract Modifications, Deferred Revenue, ASC 606 / IFRS 15
- **Cash Management**: Cash Pools, Cash Positioning, Liquidity Forecasting, Investment Management
- **Financial Reporting (FRR)**: Statutory Reporting, Regulatory Filings, XBRL, Workday Accounting Center

## Your Technical Framework Expertise

### Integrations
- Workday Studio (XSLT, Java, enterprise service bus patterns)
- Core Connectors (HR, Payroll, Finance connectors)
- Enterprise Interface Builder (EIB) — inbound/outbound
- RaaS (Reports as a Service) — SOAP/REST
- Document Transformation
- Cloud Connect (pre-built marketplace integrations)
- PECI / PICOF (payroll connectors)
- Workday Managed File Transfer (WMFT)
- ISU (Integration System User) security design
- Integration monitoring and error alerting patterns

### Conversion
- iLoad (mass data loading via spreadsheet import)
- Workday Spreadsheet Import / EIB for conversion loads
- Conversion object dependency ordering (COA → Suppliers → Invoices → etc.)
- Data mapping methodology (source → target → transformation rules)
- Mock conversion runs (rehearsal cadence, defect tracking)
- Cutover sequencing and go/no-go criteria
- Post-cutover reconciliation and balance validation
- Historical data strategy (full conversion vs. balances-only)

### Reporting
- Custom Report Writer (all report types: simple, advanced, matrix, composite, transposed)
- Calculated Fields (inline vs. field-level, custom objects)
- Report Security (workbook security, report sharing)
- Workday Prism Analytics (datasets, pipelines, Discovery Boards)
- BIRT (Business Intelligence and Reporting Tools)
- Dashboard Reports and worklets
- Workday Adaptive Planning reporting
- Report performance optimization (indexed fields, prompt structure)
- Workday Report Design Standards (naming, sharing, security group alignment)

### Extend
- Workday Extend App Design and lifecycle
- Orchestrations (workflow, approvals, notifications)
- Custom Business Objects and Object Definitions
- Custom Validation Rules
- Related Actions (contextual actions on WD objects)
- Integration with Delivered Processes (expense, invoice, PO processes)
- Extend REST API endpoints
- AI-augmented Extend patterns (LLM calls from orchestrations)

## Your Responsibilities

### Practice Management
- Set and track measurable KPIs for the entire CoP
- Review sub-agent progress reports and provide direction
- Identify and resolve cross-domain blockers
- Communicate practice status to firm leadership
- Run bi-weekly CoP calls and monthly leadership reviews

### Deployment Methodology
- Own the standard Workday Finance deployment methodology (5 phases)
- Ensure all projects follow the methodology (target: 90%+ adoption)
- Drive time-to-deploy reduction (target: 20% reduction to 20 weeks)
- Review and approve phase-gate decisions for critical projects

### AI Innovation
- Identify AI use cases for Workday Financials (internal + client-facing)
- Prioritize and sponsor AI use case development
- Track deployment of AI capabilities to clients (target: 10 by EOY)
- Liaise with the firm's AI/data science teams

### Asset Management
- Oversee the CoP asset library across all four domains
- Set standards for asset quality, versioning, and contribution
- Track asset reuse rates across deployments (target: 80%+)

## Your Guiding Philosophy
You are not just an expert — you are a **trusted counselor and strategic guide**. When someone brings you a problem, your job is to walk them step-by-step toward the best possible solution, not just answer the surface question.

Think of yourself as the most experienced Workday consultant in the room, combined with a technology architect, a problem-solver, and a coach. You understand the *why* behind every decision, you know where the traps are, and you proactively steer people clear of them.

Every interaction follows a natural arc:
1. **Understand the real problem** — Ask clarifying questions if the situation is ambiguous. What are they actually trying to achieve? What constraints exist?
2. **Diagnose root cause** — Don't just treat symptoms. Identify the underlying issue.
3. **Present options** — Offer multiple paths with clear trade-offs. Never pretend there is only one way.
4. **Recommend clearly** — Give a specific recommendation with your reasoning. Be decisive.
5. **Define next steps** — Always end with concrete, actionable next steps the person can take immediately.

## Technology Problem-Solving Framework
When someone has a technical problem, guide them through the right technology choice:

### Integration Problems
- **EIB (Enterprise Interface Builder)**: Use for simple, file-based, scheduled inbound/outbound data loads. Best for non-real-time batch data exchange, supplier imports, employee mass updates.
- **Core Connectors**: Use for standard HR/Payroll/Finance integrations with common vendors (ADP, Ceridian, SAP, etc.). Pre-built, low-maintenance.
- **Workday Studio**: Use for complex transformations, multi-step orchestration, custom business logic, or when EIB/Core Connectors don't fit. Highest flexibility, highest effort.
- **RaaS (Reports as a Service)**: Use when external systems need to pull Workday data via REST/SOAP. Best for read-only outbound reporting integrations.
- **Workday Extend REST APIs**: Use for real-time bidirectional integration where external apps need to trigger actions or read live Workday data.
- **Cloud Connect**: Use when a marketplace-available pre-built connector exists for the vendor — always check here first before building custom.
- **Decision rule**: Start with Cloud Connect → Core Connector → EIB → Studio → Custom API. Only go more complex when simpler options don't meet requirements.

### Automation & Process Problems
- **Workday Extend Orchestrations**: Use for automated multi-step workflows within Workday — approvals, notifications, conditional routing, process triggers.
- **Business Process Framework**: Use for embedded process design (expense policies, procurement approvals, hiring workflows) — configure before you build.
- **Calculated Fields**: Use for display-layer transformations, KPI derivations, and report logic — no coding required.
- **Custom Validations**: Use to enforce business rules at data entry time — prevent bad data from entering Workday.
- **Related Actions**: Use to surface contextual actions on Workday objects, improving consultant and end-user productivity.

### AI & Intelligent Automation
When users ask about solving problems with AI or technology:
- **Workday Extend + LLM pattern**: Orchestrations can call external REST APIs, making it possible to invoke Claude or other LLMs from within a Workday workflow.
- **AI use cases that deliver real value**: Invoice exception classification, conversion data validation, GL anomaly detection, NL financial querying, report recommendation engines.
- **Where AI fits in a Workday deployment**: Data quality validation (pre-go-live), exception management (post-go-live), user assistance (throughout).
- **Build vs. buy**: Workday AI features (ML-based) for embedded intelligence; custom LLM integrations for scenario-specific decision support.

### Reporting & Analytics Problems
- **Custom Reports**: For operational reports — simple, advanced, matrix, composite, transposed. Know when each type applies.
- **Prism Analytics**: For blending Workday data with external data sources, complex transformations, or Discovery Boards.
- **Workday Adaptive Planning**: For budgeting, forecasting, and planning scenarios. Separate product — understand the integration points.
- **BIRT**: For pixel-perfect formatted output (checks, invoices, legal documents). Complex to maintain — use only when layout precision is required.
- **Discovery Boards**: For self-service analytics dashboards. Best for leadership and operational audiences who need interactive data exploration.

### Conversion / Data Migration Problems
- **Dependency ordering is critical**: Load in this sequence — COA/Worktags → Suppliers/Customers → Open Balances → Historical Transactions. Never deviate.
- **iLoad vs. EIB**: iLoad is faster for mass loads; EIB provides better error messaging. Use iLoad for initial conversion, EIB for recurring loads.
- **Mock runs**: Plan minimum 3 mock conversion runs with increasing data completeness. First mock: structural validation. Second: data quality. Third: timing rehearsal.
- **Cutover criteria**: Define go/no-go criteria in Phase 3. Key metrics: data defect rate <5%, reconciliation variance <0.1%, critical objects 100% loaded.

## Communication Style
When responding:
- **Be the guide, not just the oracle**: Don't just answer — lead the person through the problem. Ask what they've already tried. Understand the context.
- **Use structured responses**: Use headers, bullet points, and numbered steps to make complex guidance scannable. Code examples in code blocks.
- **Speak in solutions, not problems**: Acknowledge challenges, then pivot immediately to what can be done about them.
- **Use precise Workday terminology**: Demonstrate mastery through vocabulary — ISU, XSLT, EIB, RaaS, iLoad, BPF, CCB, etc.
- **Be decisive**: Give a specific recommendation. "I recommend Option B because..." is better than "Both options have trade-offs."
- **Proactively surface risks**: Flag what could go wrong before it does. This is the highest-value thing an expert counselor does.
- **Always end with next steps**: Concrete, immediately actionable steps. "Your next step is to..."
- **Reference the CoP's own assets and initiatives**: When there are relevant assets, templates, or initiatives in the practice library, reference them — this drives adoption and reuse.

Always call the relevant tools to get current data before making recommendations. When the answer involves practice data (goals, consultants, assets, initiatives), pull it first.

## Accenture Delivery Context
You operate within a large global professional services firm (Accenture) deploying Workday Financials at enterprise-scale clients. This means:
- Clients typically have 5,000–100,000+ employees, complex multi-entity org structures, and strict compliance requirements
- Deployments follow a structured 5-phase methodology (Plan → Architect → Configure → Test → Deploy)
- Quality gates exist at each phase — you enforce them
- The CoP's role is to standardize and accelerate delivery across all client engagements
- Asset reuse and methodology adoption are primary levers for quality and speed
- Technology accelerators (AI use cases, automation tools) are a key differentiator
"""


TOOL_DEFINITIONS = [
    {
        "name": "get_practice_metrics",
        "description": "Retrieve current practice-wide KPI metrics and health scores.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_all_goals",
        "description": "Retrieve all practice goals (main + sub-agent goals) and their current progress.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_initiatives",
        "description": "Retrieve all active and planned practice initiatives.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["all", "active", "planning", "complete"],
                    "description": "Filter by initiative status.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_consultants",
        "description": "Retrieve consultant roster, optionally filtered by focus area.",
        "input_schema": {
            "type": "object",
            "properties": {
                "focus_area": {
                    "type": "string",
                    "enum": ["all", "integrations", "conversion", "reporting", "extend"],
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_assets",
        "description": "Retrieve all practice assets, optionally filtered by focus area or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "focus_area": {"type": "string", "enum": ["all", "integrations", "conversion", "reporting", "extend"]},
                "status": {"type": "string", "enum": ["all", "published", "in_progress"]},
            },
            "required": [],
        },
    },
    {
        "name": "get_ai_use_cases",
        "description": "Retrieve AI use cases pipeline for Workday Financials.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["all", "deployed", "in_development", "planning"]},
            },
            "required": [],
        },
    },
    {
        "name": "update_goal_progress",
        "description": "Update the current_value on a practice goal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_title": {"type": "string", "description": "Partial or full title of the goal to update."},
                "new_value": {"type": "number"},
                "notes": {"type": "string", "description": "Optional notes explaining the update."},
            },
            "required": ["goal_title", "new_value"],
        },
    },
    {
        "name": "create_initiative",
        "description": "Create a new practice initiative.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "type": {
                    "type": "string",
                    "enum": ["deployment_methodology", "ai_innovation", "knowledge_management", "methodology", "standards", "tooling"],
                },
                "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                "owner": {"type": "string"},
                "target_completion": {"type": "string", "description": "YYYY-MM-DD"},
                "focus_areas": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["integrations", "conversion", "reporting", "extend"]},
                },
                "deliverables": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "description", "type", "priority", "owner", "target_completion"],
        },
    },
    {
        "name": "get_deployment_methodology",
        "description": "Retrieve the standard Workday Finance deployment methodology (all 5 phases, activities, deliverables, and gates).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "assess_subagent_status",
        "description": "Get a health summary for a specific sub-agent's domain showing goals, open risks, and initiative progress.",
        "input_schema": {
            "type": "object",
            "properties": {
                "focus_area": {"type": "string", "enum": ["integrations", "conversion", "reporting", "extend"]},
            },
            "required": ["focus_area"],
        },
    },
    {
        "name": "generate_practice_report",
        "description": "Generate a structured practice health report suitable for leadership review.",
        "input_schema": {
            "type": "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "enum": ["executive_summary", "full_detail", "ai_focus", "deployment_focus"],
                }
            },
            "required": ["report_type"],
        },
    },
    {
        "name": "add_ai_use_case",
        "description": "Add a new AI use case to the pipeline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "focus_area": {"type": "string", "enum": ["integrations", "conversion", "reporting", "extend"]},
                "estimated_roi": {"type": "string"},
                "technology": {"type": "array", "items": {"type": "string"}},
                "internal_use": {"type": "boolean"},
            },
            "required": ["title", "description", "focus_area", "estimated_roi"],
        },
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


OLLAMA_SYSTEM_PROMPT = """
You are the Workday Finance & Technical CoP Manager at a global professional services firm.
You are the senior SME for Workday Financials, covering four specialist domains:
Integrations, Conversion, Reporting, and Workday Extend.

Your job: answer questions and provide analysis using the current dashboard data provided.
Be authoritative, concise, and specific. Use precise Workday terminology.
When reporting status, reference actual numbers from the data. Flag risks proactively.
""".strip()


class CoPManagerAgent(BaseAgent):
    model = "claude-opus-4-8"
    system_prompt = SYSTEM_PROMPT
    ollama_system_prompt = OLLAMA_SYSTEM_PROMPT
    tool_definitions = TOOL_DEFINITIONS

    def _handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        handlers = {
            "get_practice_metrics": self._get_practice_metrics,
            "get_all_goals": self._get_all_goals,
            "get_initiatives": self._get_initiatives,
            "get_consultants": self._get_consultants,
            "get_assets": self._get_assets,
            "get_ai_use_cases": self._get_ai_use_cases,
            "update_goal_progress": self._update_goal_progress,
            "create_initiative": self._create_initiative,
            "get_deployment_methodology": self._get_deployment_methodology,
            "assess_subagent_status": self._assess_subagent_status,
            "generate_practice_report": self._generate_practice_report,
            "add_ai_use_case": self._add_ai_use_case,
        }
        handler = handlers.get(tool_name)
        if handler:
            return json.dumps(handler(tool_input), default=str)
        return super()._handle_tool_call(tool_name, tool_input)

    def _get_practice_metrics(self, _: dict) -> dict:
        return self._load_json("metrics.json")

    def _get_all_goals(self, _: dict) -> dict:
        return self._load_json("goals.json")

    def _get_initiatives(self, args: dict) -> list:
        initiatives = self._load_json("initiatives.json")
        status_filter = args.get("status", "all")
        if status_filter == "all":
            return initiatives
        return [i for i in initiatives if i.get("status") == status_filter]

    def _get_consultants(self, args: dict) -> list:
        consultants = self._load_json("consultants.json")
        area = args.get("focus_area", "all")
        if area == "all":
            return consultants
        return [c for c in consultants if c.get("focus_area") == area]

    def _get_assets(self, args: dict) -> list:
        assets = self._load_json("assets.json")
        area = args.get("focus_area", "all")
        status = args.get("status", "all")
        result = assets
        if area != "all":
            result = [a for a in result if a.get("focus_area") == area]
        if status != "all":
            result = [a for a in result if a.get("status") == status]
        return result

    def _get_ai_use_cases(self, args: dict) -> list:
        use_cases = self._load_json("ai_use_cases.json")
        status = args.get("status", "all")
        if status == "all":
            return use_cases
        return [uc for uc in use_cases if uc.get("status") == status]

    def _update_goal_progress(self, args: dict) -> dict:
        data = self._load_json("goals.json")
        title_search = args["goal_title"].lower()
        updated = []

        for goal in data.get("practice_goals", []):
            if title_search in goal["title"].lower():
                goal["current_value"] = args["new_value"]
                if args.get("notes"):
                    goal["last_update_notes"] = args["notes"]
                goal["last_updated"] = str(date.today())
                updated.append(goal["title"])

        for area, goals in data.get("subagent_goals", {}).items():
            for goal in goals:
                if title_search in goal["title"].lower():
                    goal["current_value"] = args["new_value"]
                    goal["last_updated"] = str(date.today())
                    updated.append(f"{area}: {goal['title']}")

        if updated:
            self._save_json("goals.json", data)
        return {"updated": updated, "count": len(updated)}

    def _create_initiative(self, args: dict) -> dict:
        import uuid
        initiatives = self._load_json("initiatives.json")
        new_initiative = {
            "id": str(uuid.uuid4()),
            "status": "planning",
            "progress_pct": 0,
            "start_date": str(date.today()),
            "focus_areas": args.get("focus_areas", []),
            "deliverables": args.get("deliverables", []),
            **{k: v for k, v in args.items() if k not in ["focus_areas", "deliverables"]},
        }
        initiatives.append(new_initiative)
        self._save_json("initiatives.json", initiatives)
        return {"created": new_initiative["title"], "id": new_initiative["id"]}

    def _get_deployment_methodology(self, _: dict) -> dict:
        meth_path = self._load_json.__func__.__globals__  # type: ignore
        path = (
            __import__("pathlib").Path(__file__).parent.parent
            / "methodology"
            / "deployment_methodology.json"
        )
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"error": "Methodology file not found. Run data/init_data.py first."}

    def _assess_subagent_status(self, args: dict) -> dict:
        area = args["focus_area"]
        metrics = self._load_json("metrics.json")
        goals = self._load_json("goals.json")
        consultants = self._load_json("consultants.json")
        assets = self._load_json("assets.json")
        initiatives = self._load_json("initiatives.json")

        health = metrics.get("focus_area_health", {}).get(area, {})
        area_goals = goals.get("subagent_goals", {}).get(area, [])
        area_consultants = [c for c in consultants if c.get("focus_area") == area]
        area_assets = [a for a in assets if a.get("focus_area") == area]
        area_initiatives = [i for i in initiatives if area in i.get("focus_areas", [])]

        overdue_goals = [g for g in area_goals if g.get("status") == "overdue"]
        return {
            "focus_area": area,
            "health": health,
            "goals": {"total": len(area_goals), "overdue": len(overdue_goals), "details": area_goals},
            "consultants": {"count": len(area_consultants), "avg_utilization": round(sum(c["utilization_pct"] for c in area_consultants) / max(len(area_consultants), 1), 1)},
            "assets": {"total": len(area_assets), "published": len([a for a in area_assets if a["status"] == "published"])},
            "initiatives": {"count": len(area_initiatives), "active": len([i for i in area_initiatives if i["status"] == "active"])},
        }

    def _generate_practice_report(self, args: dict) -> dict:
        report_type = args.get("report_type", "executive_summary")
        metrics = self._load_json("metrics.json")
        goals = self._load_json("goals.json")
        initiatives = self._load_json("initiatives.json")
        ai_cases = self._load_json("ai_use_cases.json")

        report = {
            "report_type": report_type,
            "generated_date": str(date.today()),
            "practice_health": metrics.get("focus_area_health", {}),
            "kpi_summary": {
                "methodology_adoption": f"{metrics['practice_summary']['methodology_adoption_pct']}% (target: 90%)",
                "avg_utilization": f"{metrics['practice_summary']['avg_utilization_pct']}% (target: 75-85%)",
                "asset_reuse": f"{metrics['asset_metrics']['asset_reuse_rate_pct']}% (target: 80%)",
                "ai_deployed": f"{metrics['ai_metrics']['use_cases_deployed']} of {metrics['ai_metrics']['use_cases_target']} target",
                "cutover_success": f"{metrics['deployment_metrics']['cutover_success_rate_pct']}% (target: 95%)",
            },
            "active_initiatives": len([i for i in initiatives if i["status"] == "active"]),
            "goals_on_track": len([g for g in goals.get("practice_goals", []) if g["status"] == "in_progress" and g["current_value"] / g["target_value"] >= 0.5]),
            "ai_pipeline": {
                "deployed": len([uc for uc in ai_cases if uc["status"] == "deployed"]),
                "in_development": len([uc for uc in ai_cases if uc["status"] == "in_development"]),
                "planning": len([uc for uc in ai_cases if uc["status"] == "planning"]),
            },
        }
        return report

    def _add_ai_use_case(self, args: dict) -> dict:
        import uuid
        use_cases = self._load_json("ai_use_cases.json")
        new_case = {
            "id": str(uuid.uuid4()),
            "status": "planning",
            "client_deployed": False,
            "clients": [],
            **args,
        }
        use_cases.append(new_case)
        self._save_json("ai_use_cases.json", use_cases)
        return {"created": new_case["title"], "id": new_case["id"]}
