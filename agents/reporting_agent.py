"""
Reporting, Report Design & Deployment Sub-Agent — Workday Finance Tech CoP

Deep expertise in all Workday reporting technologies for Finance. Manages
reporting consultants, the standard financial report library, report design
standards, Prism Analytics deployments, and reporting-specific practice goals.
Reports to the CoP Manager.

Technologies owned:
  Custom Reports | Matrix Reports | Composite Reports | Transposed Reports
  Calculated Fields | Prism Analytics | Discovery Boards | BIRT | Dashboard Reports
  Workday Adaptive Planning Reporting | Report Security | Performance Optimization
"""

from __future__ import annotations
import json
import uuid
from datetime import date
from agents.base_agent import BaseAgent


SYSTEM_PROMPT = """
You are the Reporting, Report Design & Deployment Lead for the Workday Finance & Technical Community of Practice at a major global professional services firm. You are the firm's deepest expert on Workday Financial reporting across all report types and analytics platforms.

## Your Reporting Technology Expertise

### Workday Custom Report Writer
**Report Types and When to Use Each**:
- **Simple Reports**: Single data source, flat output. Best for: operational lists, quick lookups, simple data dumps.
- **Advanced Reports**: Multiple related data sources, joins, filtering, grouping. Best for: most Finance operational reports.
- **Matrix Reports**: Cross-tab layout with row/column headers and aggregate values. Best for: trial balances, budget vs. actuals, period comparisons.
- **Composite Reports**: Combines multiple subreports into a single output. Best for: financial statements (P&L + Balance Sheet in one report), management packs.
- **Transposed Reports**: Rotates rows into columns dynamically. Best for: multi-period trend analysis where periods are columns.
- **nBox Reports**: Grid visualization (e.g., 2x2 talent matrix). Rarely used in Finance.

**Report Design Best Practices**:
- Primary Business Object selection: always choose the most specific BO for the data needed
- Filter design: use indexed fields for primary filters to maximize performance
- Subfilters vs. Filters: understand Workday's two-pass filtering and when each applies
- Output format: report output types (PDF, Excel, CSV, XBRL), format configuration
- Prompt design: required vs. optional prompts, default values, multi-select prompts
- Report sharing: Share with security groups, not individuals
- Report naming convention: [AREA]-[MODULE]-[DESCRIPTION]-[v#] (e.g., FIN-GL-TrialBalance-v2)

### Calculated Fields
- Inline calculated fields (available only within the report, no persistence)
- Field-level calculated fields (stored on the Business Object, reusable)
- Calculation types: Text, Number, Date, Boolean, Enumeration, Instance
- Common Finance calculated field patterns:
  - YTD vs. prior year comparison
  - Budget variance ($ and %)
  - Days Sales Outstanding (DSO) calculation
  - Aging bucket classification
  - Conditional formatting lookups (Red/Amber/Green)
- Custom Object design for extending Workday data model for reporting
- Performance considerations: avoid heavy calculated fields on large datasets

### Report Security
- Security Groups: Role-based, User-based, Intersection
- Report-level security: View Report Definition vs. Run Report
- Data-level security: what data a user can see when running the report
- Workbook security for scheduled report distribution
- ISU for RaaS-based reporting integrations

### Workday Prism Analytics
- Prism data pipeline architecture (Extract → Transform → Load into Prism dataset)
- Supported data sources: Workday data, external data (S3, SFTP, API), uploaded files
- Dataset types: Workday Dataset, Custom Dataset, Joined Dataset, Curated Dataset
- Pipeline transformations: filter, aggregate, join, union, expression (calculated fields in Prism)
- Discovery Boards: dashboard canvas with Workday data visualizations
- Prism permission model: Dataset access, Discovery Board sharing
- Use cases: cross-module financial analytics, external benchmark data integration, historical data beyond Workday's native retention
- Performance optimization: dataset partitioning, incremental refresh scheduling

### BIRT (Business Intelligence and Reporting Tools)
- BIRT report development within Workday's embedded analytics
- BIRT vs. Custom Reports: when BIRT adds value (pixel-perfect formatting, complex layouts)
- BIRT data source connection to Workday
- BIRT deployment and scheduling

### Dashboard Reports & Worklets
- Building Dashboard Report components (metric tiles, charts, tables)
- Worklet configuration and placement in Workday Home
- Finance Executive Dashboard design patterns
- Role-based dashboard personalization

### Workday Adaptive Planning Reporting
- Adaptive Planning report types: Sheet reports, Analysis reports, OfficeConnect
- Integration between Adaptive Planning and Workday Financials for actuals import
- Dimension mapping between Adaptive and Workday
- Budget vs. actuals reporting across both platforms

### Report Performance Optimization
- Indexed fields for prompt-based filtering (use over non-indexed fields)
- Avoid "Get All" prompts on large datasets — always require a filter
- Matrix report aggregation: pre-aggregate at the report level vs. calculated field
- Scheduled report vs. on-demand report: which to use based on data freshness needs
- RaaS pagination for large output sets
- Prism dataset refresh scheduling for freshness/performance balance

## Your Responsibilities

### Consultant Management
- Manage 3 reporting consultants (Consultant, Senior, Manager)
- Assess Report Writer, Calculated Fields, and Prism Analytics skills
- Ensure all consultants can build all report types independently
- Plan training: Prism Analytics is a growth area requiring upskilling

### Asset Management — Standard Financial Report Package
- Build the Standard Financial Report Package to 100+ reports (currently 43)
- Organize by module: GL, AP, AR, Fixed Assets, Expenses, Procurement, Banking
- Each report must have: description, prompt guide, security group mapping, version
- Track deployment rates and gather feedback from project teams

### Report Design Standards (Overdue Initiative)
- Publish the Report Design Standards Guide (overdue from 2026-03-31)
- Define naming conventions, security group standards, performance requirements
- Launch an internal certification for report quality

### Practice Goals (Reporting)
- Build Standard Financial Report Package to 100+ reports (currently 43/100)
- Publish Report Design Standards Guide (currently overdue)
- Deploy AI Financial Insights Dashboard to 3 clients (currently 0/3)
- Deliver Financial Prism Analytics Data Model (in progress)

## Report Design Principles
1. **Security by design**: Design the security group mapping before the report, not after.
2. **Performance first**: Every report must pass a performance test with production-scale data before publication.
3. **Prompt discipline**: Require filters on large datasets. Never allow unrestricted queries on GL or AP tables.
4. **Reuse over rebuild**: Check the Standard Report Package before building from scratch.
5. **Version and document**: All published reports must have a version number and a one-paragraph description.
6. **Test with real users**: Reports must be UAT-tested with actual finance users, not just developers.
7. **Standards before style**: Conform to CoP naming and security standards; customize style within those bounds.

Be precise about Workday report types, proactive about performance risks, and rigorous about security standards.
"""


TOOL_DEFINITIONS = [
    {
        "name": "get_reporting_consultants",
        "description": "Get the reporting team consultant roster.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_report_library",
        "description": "Get reports from the standard financial report library.",
        "input_schema": {
            "type": "object",
            "properties": {
                "focus_area": {"type": "string", "description": "Filter by Workday module"},
                "status": {"type": "string", "enum": ["all", "published", "in_progress"]},
            },
            "required": [],
        },
    },
    {
        "name": "get_reporting_goals",
        "description": "Get reporting-specific practice goals and progress.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "recommend_report_design",
        "description": "Recommend the optimal Workday report type, design approach, and performance strategy for a described reporting requirement.",
        "input_schema": {
            "type": "object",
            "properties": {
                "requirement": {"type": "string", "description": "Description of the reporting requirement."},
                "audience": {"type": "string", "description": "Who will use this report (e.g., 'Finance Controller', 'AP Manager', 'CFO')"},
                "data_volume": {"type": "string", "description": "Estimated data volume (e.g., '50,000 GL lines/month')"},
                "output_format": {"type": "string", "description": "How will the report be consumed (on-screen, Excel, PDF, API)"},
                "modules": {"type": "array", "items": {"type": "string"}, "description": "Workday modules involved"},
            },
            "required": ["requirement"],
        },
    },
    {
        "name": "generate_report_naming",
        "description": "Generate a compliant report name following CoP naming conventions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "module": {"type": "string", "description": "Workday module abbreviation (GL, AP, AR, FA, EXP, PROC, BANK, PROJ)"},
                "description": {"type": "string", "description": "Short description of what the report shows"},
                "version": {"type": "integer", "default": 1},
            },
            "required": ["module", "description"],
        },
    },
    {
        "name": "get_status_report",
        "description": "Generate a status report for the Reporting sub-agent suitable for CoP Manager review.",
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
You are the Workday Reporting specialist for the Finance Tech CoP.
You are an expert in Custom Reports, Matrix Reports, Composite Reports, Calculated Fields, Prism Analytics, Discovery Boards, and BIRT.
Answer questions and provide analysis using the dashboard data. Be concise and use precise Workday terminology.
""".strip()


class ReportingAgent(BaseAgent):
    model = "claude-sonnet-5"
    system_prompt = SYSTEM_PROMPT
    ollama_system_prompt = OLLAMA_SYSTEM_PROMPT
    tool_definitions = TOOL_DEFINITIONS

    def _handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        handlers = {
            "get_reporting_consultants": self._get_consultants,
            "get_report_library": self._get_assets,
            "get_reporting_goals": self._get_goals,
            "recommend_report_design": self._recommend_report_design,
            "generate_report_naming": self._generate_report_naming,
            "get_status_report": self._get_status_report,
        }
        handler = handlers.get(tool_name)
        if handler:
            return json.dumps(handler(tool_input), default=str)
        return super()._handle_tool_call(tool_name, tool_input)

    def _get_consultants(self, _: dict) -> list:
        return [c for c in self._load_json("consultants.json") if c.get("focus_area") == "reporting"]

    def _get_assets(self, args: dict) -> list:
        assets = [a for a in self._load_json("assets.json") if a.get("focus_area") == "reporting"]
        status = args.get("status", "all")
        return [a for a in assets if status == "all" or a.get("status") == status]

    def _get_goals(self, _: dict) -> list:
        return self._load_json("goals.json").get("subagent_goals", {}).get("reporting", [])

    def _recommend_report_design(self, args: dict) -> dict:
        req = args.get("requirement", "").lower()
        volume = args.get("data_volume", "unknown")
        output = args.get("output_format", "on-screen")

        # Determine report type
        if "compare" in req or "vs" in req or "variance" in req or "budget" in req or "period" in req:
            report_type = "Matrix Report"
            type_reason = "Cross-tab format is ideal for period-over-period comparisons and budget vs. actuals."
        elif "statement" in req or "balance sheet" in req or "p&l" in req or "income statement" in req:
            report_type = "Composite Report"
            type_reason = "Financial statements require combining multiple report sections (header, detail, totals) — Composite Report handles this."
        elif "trend" in req or "multi-period" in req or "monthly" in req:
            report_type = "Transposed Report"
            type_reason = "Dynamic period columns are best served by Transposed Report for multi-period trend views."
        elif "dashboard" in req or "executive" in req or "kpi" in req:
            report_type = "Dashboard Report / Discovery Board"
            type_reason = "Executive consumption and KPI display is best served by Workday Dashboard or Prism Discovery Board."
        elif "external data" in req or "prism" in req or "cross-system" in req:
            report_type = "Prism Analytics Dataset + Discovery Board"
            type_reason = "External data or cross-system requirements need Prism Analytics to join non-Workday data."
        else:
            report_type = "Advanced Report"
            type_reason = "Standard operational reporting with filtering and grouping — Advanced Report is the appropriate type."

        performance_guidance = []
        if "large" in str(volume).lower() or "50,000" in str(volume) or "100,000" in str(volume):
            performance_guidance.append("High volume detected: use indexed fields as primary prompt filters.")
            performance_guidance.append("Consider scheduled report delivery instead of on-demand for large datasets.")
        performance_guidance.append("Test with production-scale data before publishing to the report library.")
        performance_guidance.append("Avoid calculated fields that call sub-reports on every row — pre-aggregate where possible.")

        return {
            "recommended_report_type": report_type,
            "rationale": type_reason,
            "performance_guidance": performance_guidance,
            "security_design": {
                "recommendation": "Define security group mapping before building the report.",
                "approach": "Use Role-Based Security Groups, not individual user sharing.",
                "testing": "Test data visibility with a user in the target security group, not as an admin.",
            },
            "naming_convention": f"FIN-[MODULE]-{args.get('requirement','DESC')[:20].upper().replace(' ','-')}-v1",
            "estimated_build_days": 2 if report_type in ["Advanced Report"] else (5 if report_type == "Matrix Report" else (8 if report_type == "Composite Report" else 10)),
        }

    def _generate_report_naming(self, args: dict) -> dict:
        module = args.get("module", "GEN").upper()
        desc = args.get("description", "Report").title().replace(" ", "")
        version = args.get("version", 1)
        name = f"FIN-{module}-{desc}-v{version}"
        return {
            "report_name": name,
            "format": "FIN-[MODULE]-[Description]-v[Version]",
            "example": name,
            "notes": "Keep description under 30 characters. Use PascalCase with no spaces.",
        }

    def _get_status_report(self, _: dict) -> dict:
        consultants = self._get_consultants({})
        assets = self._get_assets({})
        goals = self._get_goals({})
        metrics = self._load_json("metrics.json")
        published = len([a for a in assets if a["status"] == "published"])
        overdue = [g for g in goals if g.get("status") == "overdue"]
        return {
            "focus_area": "Reporting",
            "report_date": str(date.today()),
            "team": {"headcount": len(consultants), "avg_utilization": round(sum(c["utilization_pct"] for c in consultants) / max(len(consultants), 1), 1)},
            "report_library": {"total": len(assets), "published": published, "target": 100, "pct_complete": round(published / 100 * 100, 1)},
            "goals": goals,
            "overdue_items": overdue,
            "health": metrics.get("focus_area_health", {}).get("reporting", {}),
        }
