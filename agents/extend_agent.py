"""
Workday Extend Solutions Sub-Agent — Workday Finance Tech CoP

Deep expertise in Workday Extend for building custom Finance applications.
Manages Extend consultants, the Extend application template library, Extend
development standards, and Extend-specific practice goals.
Reports to the CoP Manager.

Technologies owned:
  Workday Extend App Design | Orchestrations | Custom Business Objects
  Custom Validation Rules | Related Actions | Delivered Process Integration
  Extend REST API | AI-augmented Extend patterns
"""

from __future__ import annotations
import json
import uuid
from datetime import date
from agents.base_agent import BaseAgent


SYSTEM_PROMPT = """
You are the Workday Extend Solutions Lead for the Workday Finance & Technical Community of Practice at a major global professional services firm. You are the firm's deepest expert on Workday Extend and building custom Finance applications on the Workday platform.

## Your Workday Extend Expertise

### Workday Extend Fundamentals
- Workday Extend is Workday's low-code/pro-code platform for building custom applications that run natively inside Workday
- Extend apps appear in the Workday UI as native worklets, action items, and contextual actions
- Extend integrates deeply with Workday data, business processes, and security model
- Extend apps are fully tenant-specific and portable across environments (Sandbox → Production)
- Lifecycle: Design → Build → Test (Preview tenant) → Deploy (Production tenant)

### App Design & Architecture
- App manifest structure: pages, views, fields, orchestrations, security policies
- Workday Extend Designer (visual low-code builder) vs. Workday Studio integration
- Page types: Form pages, List pages, Detail pages, Report pages
- Field types: Text, Number, Date, Boolean, Multi-select, File attachment, Rich text, Lookup (instance)
- View composition: combining multiple data sources into a unified UI
- Navigation design: breadcrumb patterns, related action links, action buttons
- App security: who can access the app, what data they see, what actions they can take
- Multi-tenant design considerations for reusable app templates

### Orchestrations (Workday Extend's Process Engine)
- Orchestrations define the business logic and workflow of Extend apps
- Step types:
  - **Human Task**: Assign action to a person (approval, review, data entry)
  - **System Task**: Execute automated logic (call API, send notification, update data)
  - **Decision Gateway**: Branch workflow based on condition (if/else logic)
  - **Parallel Gateway**: Execute multiple steps concurrently
  - **Timer**: Schedule a step for a future date/time
  - **Compensation**: Handle rollback/undo logic on process failure
- Condition expression syntax (Workday's expression language)
- Orchestration variables: input, output, intermediate, global
- Calling external REST APIs from orchestrations (HTTP connector steps)
- Calling Workday APIs from orchestrations (Workday connector steps)
- Error handling in orchestrations: retry, escalate, terminate
- Orchestration debugging and log analysis

### Custom Business Objects (BOs)
- Custom BO definition: fields, relationships, constraints
- Relating custom BOs to delivered Workday objects (e.g., Supplier Invoice, Cost Center)
- Custom BO lifecycle: create, update, delete, archive
- Custom BO security: who can create/read/update/delete instances
- Using custom BOs as data stores for Extend app state
- Reporting on custom BO data using Workday Report Writer

### Custom Validation Rules
- Building custom validation logic that fires within delivered Workday processes
- Validation rule conditions: field-level vs. object-level vs. process-level
- Error message design: clear, actionable messages for end users
- Using validation rules to enforce Finance policy (e.g., PO match required for invoices over $10K)
- Performance considerations for validation rules on high-volume processes

### Related Actions
- Adding custom actions to the right-click context menu of Workday objects
- Related Action configuration: which objects, which users, what action
- Typical Finance Related Actions: "View AP Exception History", "Run Reconciliation Check", "Escalate Invoice"
- Triggering orchestrations from Related Actions

### Delivered Process Integration
- Hooking Extend logic into Workday's delivered business processes:
  - Accounts Payable: Invoice verification, payment approval, exception routing
  - Accounts Receivable: Collections workflow, credit approval
  - Expenses: Policy validation, manager review, audit selection
  - Procurement: PO approval, contract compliance check
  - General Ledger: Journal entry review, period close checklist
- Business Process Framework (BPF) integration: where Extend fits alongside BPF
- Triggering Extend apps as subprocess steps within delivered BPs

### Extend REST API
- Extend apps expose REST APIs that external systems can call
- API endpoint structure, authentication (OAuth 2.0), request/response format
- Using Extend APIs to expose Workday data to external AI/ML systems
- Rate limiting and performance considerations

### AI-Augmented Extend Patterns (Key Differentiator)
- Calling external LLM APIs (Claude, OpenAI) from Extend orchestration HTTP steps
- Pattern: Workday event → Orchestration triggered → HTTP call to LLM API → LLM response parsed → Action taken in Workday
- Finance AI use cases built with this pattern:
  - Invoice exception classification and routing
  - Expense policy violation explanation
  - Supplier risk narrative generation
  - Budget variance root cause hypothesis
  - Journal entry anomaly narrative
- Prompt engineering for Finance data (structured, deterministic prompts)
- Handling LLM response parsing and error cases in orchestrations
- Data privacy: what Workday data is safe to send to external APIs
- Latency management: async vs. sync LLM calls in Extend workflows

### Extend Development Standards (Published)
- Development environment: always build in Sandbox, never Production
- Naming convention: [FIRM_PREFIX]_[MODULE]_[AppName] (e.g., ACN_AP_InvoiceExceptionHandler)
- Version control: use Workday Extend's built-in versioning, tag each release
- Testing: unit test each orchestration step, integration test end-to-end flow
- Security review: every app requires security group review before production
- Documentation: each app requires a Solution Design Document (SDD)

## Your Responsibilities

### Consultant Management
- Manage 2 Extend consultants (Senior, Manager)
- Assess App Design, Orchestration, and AI integration skills
- Extend is a growth area — plan for team expansion and certification
- Build internal training materials for Extend development

### Asset Management
- Maintain Extend application template library (target: 5 reusable app templates)
- Currently: 1 published (Invoice Exception Handler), 1 in progress (Expense Compliance Monitor)
- Each template must be fully documented with an SDD and deployment guide

### Methodology Ownership
- Own the Extend chapter of the deployment methodology
- Define Extend discovery, design, build, test, and go-live standards
- Own the Extend Solution Design Document (SDD) template
- Define security review checklist for Extend apps

### Practice Goals (Extend)
- Build 5 Reusable Extend App Templates (currently 1/5)
- Deliver AI Invoice Processing Extend App to 3+ clients (in progress)
- Publish Extend Development Standards (COMPLETE)
- Build Expense Policy AI Compliance app (in development)

## Extend Design Principles
1. **Native experience**: Extend apps should feel like they're part of Workday, not bolted on.
2. **Security-first**: Design Extend security with Workday's role-based model before writing a line of code.
3. **Orchestration over workarounds**: Use Extend orchestrations instead of building external middleware for Workday process automation.
4. **AI as an enhancer**: Use AI (via HTTP connector) to enhance decisions within Extend, not to replace Workday's native logic.
5. **Template mindset**: Every new Extend build should produce a reusable template or at minimum contribute a pattern to the CoP library.
6. **Test with real users**: Extend UX must be validated with the actual end users (AP clerks, accountants, managers) before go-live.
7. **Data minimization for AI calls**: Only send the minimum necessary Workday data fields to external AI APIs.

Be precise about Extend capabilities, proactive about AI augmentation opportunities, and rigorous about security and data privacy in AI-connected Extend patterns.
"""


TOOL_DEFINITIONS = [
    {
        "name": "get_extend_consultants",
        "description": "Get the Extend team consultant roster.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_extend_assets",
        "description": "Get Extend application templates from the asset library.",
        "input_schema": {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["all", "published", "in_progress"]}},
            "required": [],
        },
    },
    {
        "name": "get_extend_goals",
        "description": "Get Extend-specific practice goals and progress.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "design_extend_solution",
        "description": "Generate a Workday Extend solution design for a described Finance automation or AI use case.",
        "input_schema": {
            "type": "object",
            "properties": {
                "use_case": {"type": "string", "description": "Business requirement or automation need."},
                "workday_module": {"type": "string", "description": "Primary Workday Finance module involved."},
                "ai_component": {"type": "boolean", "description": "Does this solution include an AI/LLM component?"},
                "trigger": {"type": "string", "description": "What triggers the Extend app (e.g., 'invoice submitted', 'expense report created', 'user clicks Related Action')"},
                "stakeholders": {"type": "array", "items": {"type": "string"}, "description": "Who interacts with the app (e.g., 'AP Clerk', 'Finance Manager', 'CFO')"},
            },
            "required": ["use_case", "workday_module"],
        },
    },
    {
        "name": "generate_sdd_outline",
        "description": "Generate a Solution Design Document (SDD) outline for a Workday Extend application.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string"},
                "module": {"type": "string"},
                "description": {"type": "string"},
                "has_ai": {"type": "boolean"},
            },
            "required": ["app_name", "module", "description"],
        },
    },
    {
        "name": "get_ai_extend_patterns",
        "description": "Get documented AI-augmented Extend patterns available in the CoP library.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_status_report",
        "description": "Generate a status report for the Extend sub-agent suitable for CoP Manager review.",
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


OLLAMA_SYSTEM_PROMPT = """
You are the Workday Extend specialist for the Finance Tech CoP.
You are an expert in Workday Extend app design, Orchestrations, Custom Business Objects, Custom Validation Rules, Related Actions, and AI-augmented Extend patterns.
Answer questions and provide analysis using the dashboard data. Be concise and use precise Workday terminology.
""".strip()


class ExtendAgent(BaseAgent):
    model = "claude-sonnet-5"
    system_prompt = SYSTEM_PROMPT
    ollama_system_prompt = OLLAMA_SYSTEM_PROMPT
    tool_definitions = TOOL_DEFINITIONS

    def _handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        handlers = {
            "get_extend_consultants": self._get_consultants,
            "get_extend_assets": self._get_assets,
            "get_extend_goals": self._get_goals,
            "design_extend_solution": self._design_solution,
            "generate_sdd_outline": self._generate_sdd,
            "get_ai_extend_patterns": self._get_ai_patterns,
            "get_status_report": self._get_status_report,
        }
        handler = handlers.get(tool_name)
        if handler:
            return json.dumps(handler(tool_input), default=str)
        return super()._handle_tool_call(tool_name, tool_input)

    def _get_consultants(self, _: dict) -> list:
        return [c for c in self._load_json("consultants.json") if c.get("focus_area") == "extend"]

    def _get_assets(self, args: dict) -> list:
        assets = [a for a in self._load_json("assets.json") if a.get("focus_area") == "extend"]
        status = args.get("status", "all")
        return [a for a in assets if status == "all" or a.get("status") == status]

    def _get_goals(self, _: dict) -> list:
        return self._load_json("goals.json").get("subagent_goals", {}).get("extend", [])

    def _design_solution(self, args: dict) -> dict:
        use_case = args.get("use_case", "")
        module = args.get("workday_module", "")
        has_ai = args.get("ai_component", False)
        trigger = args.get("trigger", "user action")
        stakeholders = args.get("stakeholders", ["Finance user"])

        ai_steps = []
        if has_ai:
            ai_steps = [
                "HTTP System Task: Call Claude API with structured prompt containing relevant Workday data fields",
                "Parse LLM response JSON in orchestration expression",
                "Branch orchestration based on LLM classification/recommendation",
                "Persist AI output to Custom Business Object for audit trail",
            ]

        return {
            "solution_design": {
                "app_name_suggestion": f"ACN_{module[:4].upper()}_{use_case[:20].replace(' ', '')}",
                "architecture": {
                    "trigger": trigger,
                    "pages": ["Form page (data display and action capture)", "List page (queue view for managers)", "Detail page (full record view)"],
                    "orchestration_steps": [
                        f"Trigger: {trigger}",
                        "Decision Gateway: Apply routing/classification logic",
                        *ai_steps,
                        "Human Task: Route to appropriate stakeholder for action" if stakeholders else None,
                        "System Task: Update Workday object (approve/reject/notify)",
                        "Notification: Send confirmation to all relevant parties",
                    ],
                    "custom_business_objects": [f"Custom BO to store {use_case[:30]} history and audit trail"],
                    "related_actions": [f"View {use_case[:20]} History on relevant Workday object"],
                },
                "security_design": {
                    "access_groups": [f"{s} Security Group" for s in stakeholders],
                    "data_access": "Restrict to security group — do not use admin bypass",
                },
                "ai_considerations": {
                    "api": "Claude API (claude-sonnet-5 for cost/performance balance)",
                    "data_sent": "Send only anonymized/necessary fields — avoid PII and sensitive financial data",
                    "latency": "Use async orchestration pattern for AI calls >2 seconds",
                    "fallback": "Design explicit fallback if AI API is unavailable — route to human review",
                } if has_ai else None,
                "estimated_build_weeks": 4 if has_ai else 2,
                "prerequisites": ["Extend license enabled on tenant", "Security review approved", "SDD signed off"],
            }
        }

    def _generate_sdd(self, args: dict) -> dict:
        return {
            "document_title": f"Solution Design Document — {args['app_name']}",
            "version": "0.1 (Draft)",
            "sections": {
                "1_overview": {"app_name": args["app_name"], "module": args["module"], "description": args["description"], "ai_enabled": args.get("has_ai", False)},
                "2_business_requirements": "List business requirements the app satisfies",
                "3_architecture": {"pages": "TBD", "orchestrations": "TBD", "custom_objects": "TBD", "integrations": "TBD"},
                "4_security_design": {"security_groups": "TBD", "data_access_model": "TBD"},
                "5_ai_design": {"api": "TBD", "prompt_design": "TBD", "data_privacy": "TBD", "fallback": "TBD"} if args.get("has_ai") else "N/A",
                "6_testing": {"unit_tests": "TBD", "integration_tests": "TBD", "uat": "Required"},
                "7_deployment": {"sandbox_steps": "TBD", "production_steps": "TBD", "rollback": "TBD"},
                "8_approvals": {"tech_lead": "Pending", "security_review": "Pending", "client_sign_off": "Pending"},
            },
        }

    def _get_ai_patterns(self, _: dict) -> list:
        return [
            {
                "pattern": "Invoice Exception AI Classifier",
                "trigger": "Supplier invoice enters exception state in Workday AP",
                "ai_role": "Classify exception type, recommend resolver, generate plain-English explanation",
                "status": "Published — deployed in Invoice Exception Handler app",
            },
            {
                "pattern": "Expense Policy AI Reviewer",
                "trigger": "Expense report submitted by employee",
                "ai_role": "Review against policy, flag violations with specific rule citations, suggest corrections",
                "status": "In Development — Expense Compliance Monitor app",
            },
            {
                "pattern": "Budget Variance AI Analyst",
                "trigger": "Budget variance threshold exceeded (configurable %)",
                "ai_role": "Generate hypothesis for variance root cause using GL, AP, and Expense data context",
                "status": "Pattern documented — not yet built as Extend app",
            },
            {
                "pattern": "Journal Entry Anomaly Narrator",
                "trigger": "Journal entry posted outside normal range or pattern",
                "ai_role": "Generate anomaly description and risk assessment for accounting manager review",
                "status": "Pattern documented — candidate for next Extend build",
            },
        ]

    def _get_status_report(self, _: dict) -> dict:
        consultants = self._get_consultants({})
        assets = self._get_assets({})
        goals = self._get_goals({})
        metrics = self._load_json("metrics.json")
        published = len([a for a in assets if a["status"] == "published"])
        return {
            "focus_area": "Extend",
            "report_date": str(date.today()),
            "team": {"headcount": len(consultants), "avg_utilization": round(sum(c["utilization_pct"] for c in consultants) / max(len(consultants), 1), 1)},
            "apps": {"total": len(assets), "published": published, "in_progress": len(assets) - published, "target": 5},
            "goals": goals,
            "ai_patterns_documented": 4,
            "health": metrics.get("focus_area_health", {}).get("extend", {}),
        }
