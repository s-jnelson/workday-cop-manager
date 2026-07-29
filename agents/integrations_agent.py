"""
Integrations Sub-Agent — Workday Finance Tech CoP

Deep expertise in all Workday integration technologies. Manages the integrations
consultant team, integration asset library, integration methodology, and
integration-specific practice goals. Reports to the main CoP Manager agent.

Technologies owned:
  Workday Studio | Core Connectors | EIB | RaaS | REST API | SOAP API
  Document Transformation | PECI/PICOF | Cloud Connect | WMFT | ISU Security
"""

from __future__ import annotations
import json
import uuid
from datetime import date
from agents.base_agent import BaseAgent


SYSTEM_PROMPT = """
You are the Integrations Lead for the Workday Finance & Technical Community of Practice at a major global professional services firm. You are the deepest integration expert in the CoP and are responsible for all Workday integration work across Workday Financial deployments.

## Your Integration Technology Expertise

### Workday Studio
- Enterprise Service Bus (ESB) architecture within Studio
- XSLT 2.0 transformation development for complex data reshaping
- Java/Groovy scripting within Studio connectors
- Sub-process design and reuse patterns
- Error handling: fault sequences, dead letter queues, retry logic
- Studio performance optimization (batching, parallel processing)
- ISU (Integration System User) credential management within Studio
- Studio deployment (packaging, transport, environment promotion)
- Workday Studio debugging and log analysis

### Core Connectors
- All Finance Core Connectors: AP Payment, Supplier Invoice, Journal Entry, Expense Report, Customer Invoice
- Configuration of connector field mappings and transformations
- Core Connector security and ISU setup
- Troubleshooting connector failures and data validation errors
- Using Document Transformation with Core Connectors for format conversion

### Enterprise Interface Builder (EIB)
- Inbound EIB (loading data into Workday via spreadsheet/CSV/XML)
- Outbound EIB (extracting data from Workday via reports)
- EIB scheduling and automation
- EIB error handling and exception management
- Using EIB for conversion loads and ongoing interfaces

### RaaS (Reports as a Service)
- Exposing Workday reports as REST or SOAP web services
- RaaS URL construction and authentication (Basic Auth, OAuth 2.0)
- Using RaaS for real-time data extraction and system-to-system integration
- RaaS performance considerations (report design, output format)
- Securing RaaS endpoints with ISU credentials

### REST & SOAP APIs
- Workday REST API: endpoints, authentication (OAuth 2.0 PKCE, Bearer Token), pagination
- Workday SOAP API (WSDL-based): all Finance web services (Financial Management, Revenue Management, etc.)
- API rate limiting, error codes, and retry patterns
- Postman/curl usage for Workday API testing
- Building custom integrations consuming Workday APIs

### Document Transformation
- XSLT stylesheet development for document format conversion
- Content Handler configuration (input/output format, delimiter, encoding)
- Using Document Transformation to convert between XML, CSV, JSON, fixed-width
- Chaining Document Transformations

### PECI / PICOF
- Payroll Effective Change Integration (PECI) for payroll system integration
- PICOF (Payroll Input on Change Output File) patterns
- Configuring payroll connectors for Finance integration touchpoints

### Cloud Connect
- Workday Cloud Connect marketplace connectors
- Pre-built Finance connectors (banks, payment processors, tax engines)
- Configuring and customizing Cloud Connect packages

### Integration Security & ISU Design
- ISU account provisioning and credential management
- Integration Security Group design (least-privilege model)
- Network connectivity: Workday IP allowlisting, SFTP, HTTPS
- Certificate management for encrypted integrations

### Integration Monitoring & Operations
- Workday integration dashboard monitoring
- Event-driven alerting for failed integrations
- SLA-based monitoring design
- Self-healing integration patterns
- Integration incident response and root cause analysis

## Your Responsibilities

### Consultant Management
- Manage 3 integrations consultants (Senior, Consultant, Manager level)
- Monitor utilization, assess skills, plan training and certification paths
- Assign consultants to projects based on complexity and skill match
- Conduct technical reviews of integration work

### Asset Management
- Maintain the integrations template library (target: 50 templates)
- Ensure all templates are tested, versioned, and documented
- Review contribution requests from project teams
- Track asset deployment rates and gather feedback

### Methodology Ownership
- Own the integrations chapter of the standard deployment methodology
- Define integration discovery, design, build, test, and go-live standards
- Set integration naming conventions and documentation standards
- Define ISU naming and security design standards
- Own the integration cutover checklist and smoke test protocol

### Practice Goals (Integrations)
- Build Integration Template Library to 50 templates (currently 18)
- Reduce integration build time by 30% (currently at 12%)
- Deliver AI-powered Integration Error Diagnostics tool
- Achieve Integration Monitoring Framework deployment across 100% of projects

### Reporting to CoP Manager
- Provide weekly status updates on goals, team utilization, and initiative progress
- Escalate blockers and risks requiring CoP Manager intervention
- Surface new integration patterns and technologies worth adopting

## Integration Design Principles
When advising on integrations, always apply these principles:
1. **Reuse first**: Check the asset library before building from scratch
2. **Error-first design**: Design the error path before the happy path
3. **ISU least privilege**: ISU accounts should have minimum required permissions
4. **Environment parity**: Dev → Test → Production configurations should be identical except for endpoints and credentials
5. **Monitoring by default**: Every production integration must have alerting configured
6. **Document the interface**: Every integration must have a completed Interface Design Document (IDD)
7. **Version and tag**: All integration bundles must follow naming convention and be tagged in the asset library

When responding, be precise about Workday integration technology, always recommend the right tool for the job (Studio vs. EIB vs. Core Connector vs. API), and flag risks proactively.
"""


TOOL_DEFINITIONS = [
    {
        "name": "get_integrations_consultants",
        "description": "Get the integrations team consultant roster with utilization and project assignments.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_integration_assets",
        "description": "Get integration templates and tools from the asset library.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["all", "published", "in_progress"]},
                "module": {"type": "string", "description": "Filter by Workday module (e.g., 'Accounts Payable')"},
            },
            "required": [],
        },
    },
    {
        "name": "get_integration_goals",
        "description": "Get integrations-specific goals and progress.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "add_integration_template",
        "description": "Add a new integration template to the asset library.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "format": {"type": "string", "description": "e.g., 'Workday Studio', 'EIB', 'Core Connector', 'REST API'"},
                "modules": {"type": "array", "items": {"type": "string"}},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["name", "description", "format", "modules"],
        },
    },
    {
        "name": "design_integration",
        "description": "Generate a recommended integration design for a described use case, including technology choice rationale, design considerations, ISU requirements, and monitoring approach.",
        "input_schema": {
            "type": "object",
            "properties": {
                "use_case": {"type": "string", "description": "Description of the integration requirement."},
                "direction": {"type": "string", "enum": ["inbound", "outbound", "bidirectional"]},
                "source_system": {"type": "string"},
                "target_system": {"type": "string"},
                "volume": {"type": "string", "description": "Estimated transaction volume (e.g., '5000 invoices/day')"},
                "frequency": {"type": "string", "description": "Integration trigger (real-time, scheduled batch, event-driven)"},
            },
            "required": ["use_case", "direction"],
        },
    },
    {
        "name": "generate_idd",
        "description": "Generate an Interface Design Document (IDD) outline for a Workday integration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "integration_name": {"type": "string"},
                "integration_type": {"type": "string"},
                "source": {"type": "string"},
                "target": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["integration_name", "integration_type", "source", "target", "description"],
        },
    },
    {
        "name": "get_status_report",
        "description": "Generate a status report for the Integrations sub-agent suitable for reporting to the CoP Manager.",
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
You are the Workday Integrations specialist for the Finance Tech CoP.
You are an expert in Workday Studio, Core Connectors, EIB, RaaS, REST/SOAP APIs, PECI/PICOF, Document Transformation, and Cloud Connect.
Answer questions and provide analysis using the dashboard data. Be concise and use precise Workday terminology.
""".strip()


class IntegrationsAgent(BaseAgent):
    model = "claude-sonnet-5"
    system_prompt = SYSTEM_PROMPT
    ollama_system_prompt = OLLAMA_SYSTEM_PROMPT
    tool_definitions = TOOL_DEFINITIONS

    def _handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        handlers = {
            "get_integrations_consultants": self._get_consultants,
            "get_integration_assets": self._get_assets,
            "get_integration_goals": self._get_goals,
            "add_integration_template": self._add_template,
            "design_integration": self._design_integration,
            "generate_idd": self._generate_idd,
            "get_status_report": self._get_status_report,
        }
        handler = handlers.get(tool_name)
        if handler:
            return json.dumps(handler(tool_input), default=str)
        return super()._handle_tool_call(tool_name, tool_input)

    def _get_consultants(self, _: dict) -> list:
        consultants = self._load_json("consultants.json")
        return [c for c in consultants if c.get("focus_area") == "integrations"]

    def _get_assets(self, args: dict) -> list:
        assets = self._load_json("assets.json")
        result = [a for a in assets if a.get("focus_area") == "integrations"]
        status = args.get("status", "all")
        if status != "all":
            result = [a for a in result if a.get("status") == status]
        module = args.get("module")
        if module:
            result = [a for a in result if any(module.lower() in m.lower() for m in a.get("modules", []))]
        return result

    def _get_goals(self, _: dict) -> list:
        goals = self._load_json("goals.json")
        return goals.get("subagent_goals", {}).get("integrations", [])

    def _add_template(self, args: dict) -> dict:
        assets = self._load_json("assets.json")
        new_asset = {
            "id": str(uuid.uuid4()),
            "focus_area": "integrations",
            "type": "integration_template",
            "version": "1.0",
            "status": "in_progress",
            "deployments": 0,
            **args,
        }
        assets.append(new_asset)
        self._save_json("assets.json", assets)
        return {"created": new_asset["name"], "id": new_asset["id"]}

    def _design_integration(self, args: dict) -> dict:
        use_case = args.get("use_case", "")
        direction = args.get("direction", "outbound")
        volume = args.get("volume", "unknown")
        freq = args.get("frequency", "batch")

        tech_choice = "Workday Studio"
        rationale = "Complex transformation required — Studio provides full XSLT control."

        if "eib" in use_case.lower() or ("simple" in use_case.lower() and direction == "inbound"):
            tech_choice = "EIB (Enterprise Interface Builder)"
            rationale = "Simple flat-file inbound load — EIB is fastest to configure and requires no code."
        elif "report" in use_case.lower() or "extract" in use_case.lower():
            tech_choice = "RaaS (Reports as a Service)"
            rationale = "Data extraction pattern — RaaS exposes Workday reports as APIs without custom build."
        elif "real-time" in freq.lower() or "api" in use_case.lower():
            tech_choice = "Workday REST API"
            rationale = "Real-time requirement — REST API provides synchronous, event-driven integration."
        elif "connector" in use_case.lower() or "core connector" in use_case.lower():
            tech_choice = "Core Connector"
            rationale = "Standard Workday connector pattern available — Core Connector reduces build time vs. Studio."

        return {
            "recommended_technology": tech_choice,
            "rationale": rationale,
            "direction": direction,
            "isu_requirements": {
                "account_type": "Integration System User",
                "naming_convention": f"ISU_INT_{args.get('integration_name', 'NAME').upper().replace(' ', '_')}",
                "recommended_permissions": ["Get Financials", "Put Financials"] if direction == "bidirectional" else ([f"{'Get' if direction == 'outbound' else 'Put'} Financials"]),
                "security_group": "Integration Security Group (read-only where applicable)",
            },
            "design_considerations": [
                "Define error handling and retry strategy before build",
                "Use non-production tenant for development and unit testing",
                "Document in Interface Design Document (IDD) before build begins",
                "Configure monitoring alert before production activation",
                f"Volume consideration: {volume} — {'batch processing recommended' if 'day' in str(volume) else 'review scheduling window'}",
            ],
            "monitoring_approach": "Configure Workday integration event notification with email alert on failure. Set retry to 3 attempts with 15-minute backoff.",
            "estimated_build_days": 5 if tech_choice in ["EIB (Enterprise Interface Builder)", "RaaS (Reports as a Service)"] else (10 if tech_choice == "Core Connector" else 15),
        }

    def _generate_idd(self, args: dict) -> dict:
        return {
            "document_title": f"Interface Design Document — {args['integration_name']}",
            "version": "0.1 (Draft)",
            "sections": {
                "1_overview": {"integration_name": args["integration_name"], "type": args["integration_type"], "source": args["source"], "target": args["target"], "description": args["description"]},
                "2_technical_design": {"technology": "TBD — complete after design_integration call", "trigger": "TBD", "frequency": "TBD", "format": "TBD"},
                "3_field_mapping": "Complete field-by-field mapping table here",
                "4_error_handling": {"strategy": "TBD", "retry_logic": "TBD", "dead_letter": "TBD", "notification": "TBD"},
                "5_security": {"isu_account": "TBD", "security_group": "TBD", "network": "TBD"},
                "6_testing": {"unit_test_approach": "TBD", "sit_approach": "TBD", "uat_sign_off": "Required"},
                "7_monitoring": {"dashboard": "Workday Integration Dashboard", "alerting": "TBD", "sla": "TBD"},
                "8_approvals": {"functional_lead": "Pending", "technical_lead": "Pending", "client_architect": "Pending"},
            },
        }

    def _get_status_report(self, _: dict) -> dict:
        consultants = self._get_consultants({})
        assets = self._get_assets({})
        goals = self._get_goals({})
        metrics = self._load_json("metrics.json")

        published = len([a for a in assets if a["status"] == "published"])
        overdue = [g for g in goals if g.get("status") == "overdue"]
        return {
            "focus_area": "Integrations",
            "report_date": str(date.today()),
            "team": {"headcount": len(consultants), "avg_utilization": round(sum(c["utilization_pct"] for c in consultants) / max(len(consultants), 1), 1)},
            "assets": {"total": len(assets), "published": published, "in_progress": len(assets) - published},
            "goals": {"total": len(goals), "overdue": len(overdue), "details": goals},
            "health": metrics.get("focus_area_health", {}).get("integrations", {}),
            "risks": overdue,
        }
