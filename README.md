# Workday Finance & Technical CoP Manager

A multi-agent AI system for managing the Workday Finance Technical Sub-Community of Practice at a major professional services firm.

## What It Does

### Main Agent — CoP Manager
- Subject matter expert across all 14 Workday Financial modules
- Sets and tracks practice-wide KPIs and goals
- Orchestrates and reviews sub-agent status reports
- Drives AI use case identification and deployment tracking
- Owns the standard 5-phase deployment methodology
- Manages the practice dashboard and leadership reporting

### Sub-Agents (report to CoP Manager)
| Agent | Owns | Technologies |
|---|---|---|
| **Integrations** | Integration template library, IDD standards, monitoring framework | Studio, Core Connectors, EIB, RaaS, REST/SOAP, PECI, Cloud Connect |
| **Conversion** | 14-object migration methodology, data validation framework, cutover protocol | iLoad, Spreadsheet Import, EIB loads, Python validation library |
| **Reporting** | 100+ report standard package, report design standards, Prism Analytics model | Custom Reports, Matrix, Composite, Prism Analytics, Discovery Boards, BIRT |
| **Extend** | 5 reusable Extend app templates, AI-augmented Extend patterns | App Design, Orchestrations, Custom BOs, Extend REST API, Claude API integration |

## Quick Start

### 1. Install dependencies
```bash
cd workday-cop-manager
pip install -r requirements.txt
```

### 2. Configure AI backend (choose one)

**Option A — Ollama local (free, no API key needed)**
```bash
# Install Ollama from https://ollama.ai, then pull a model:
ollama pull llama3.2
# The dashboard server auto-detects Ollama on startup — no further config needed.
```

**Option B — Anthropic Claude (requires API key)**
```bash
# Edit workday-cop-manager/.env and add:
# ANTHROPIC_API_KEY=sk-ant-api03-...
# Then restart the dashboard server.
```

### 3. Initialize data stores
```bash
python main.py --init
```

### 4a. Open the standalone dashboard
Open `dashboard/index.html` directly in a browser — works without any backend (uses embedded seed data).

### 4b. Start the full server (live data + agent queries)
```bash
python main.py --serve
# Dashboard: http://localhost:8000
# API docs:  http://localhost:8000/docs
```

### 5. Run the CLI agent REPL
```bash
python main.py                    # Auto-routes to best agent
python main.py --agent main       # Force main CoP Manager
python main.py --agent integrations
python main.py --agent conversion
python main.py --agent reporting
python main.py --agent extend
python main.py --status           # Collect all sub-agent status reports
```

## Dashboard Views

| View | Contents |
|---|---|
| **Overview** | Practice health band, 8 KPI cards, goal progress, active initiatives |
| **Goals & KPIs** | Tabbed by area — each goal with progress bar, status badge, due date |
| **Initiatives** | All firm-wide programs with deliverables and progress tracking |
| **Consultants** | Team roster by focus area — utilization, skills, projects, location |
| **Asset Library** | All templates, tools, and apps with deployment counts and status |
| **AI Pipeline** | Kanban board of AI use cases (deployed / in development / planning) |
| **Methodology** | Expandable 5-phase deployment standard with activities, deliverables, gates |
| **CoP Agent** | Live chat with any agent — auto-routes or force a specific sub-agent |

## Architecture

```
CoPOrchestrator (orchestrator.py)
├── CoPManagerAgent       — Main agent (claude-opus-4-8)
│   Tools: get_practice_metrics, get_all_goals, get_initiatives,
│          create_initiative, assess_subagent_status, add_ai_use_case,
│          get_deployment_methodology, generate_practice_report, ...
├── IntegrationsAgent     — (claude-sonnet-5)
│   Tools: get_integrations_consultants, get_integration_assets,
│          design_integration, generate_idd, get_status_report, ...
├── ConversionAgent       — (claude-sonnet-5)
│   Tools: generate_conversion_plan, validate_conversion_readiness,
│          get_object_template_status, get_status_report, ...
├── ReportingAgent        — (claude-sonnet-5)
│   Tools: recommend_report_design, generate_report_naming,
│          get_report_library, get_status_report, ...
└── ExtendAgent           — (claude-sonnet-5)
    Tools: design_extend_solution, generate_sdd_outline,
           get_ai_extend_patterns, get_status_report, ...

API: FastAPI (api/server.py) — serves dashboard + agent endpoints
Dashboard: Vanilla HTML/CSS/JS — standalone or API-connected
Data: JSON files in data/ — initialized by data/init_data.py
```

## Practice Goals Being Tracked

| Goal | Current | Target | Due |
|---|---|---|---|
| Methodology Adoption | 62% | 90% | 2026-09-30 |
| Asset Reuse Rate | 45% | 80% | 2026-09-30 |
| Deploy Time Reduction | 6.9% | 20% (20 weeks) | 2026-12-31 |
| AI Use Cases Deployed | 2 | 10 | 2026-12-31 |
| Cutover Success Rate | 87% | 95% | 2026-12-31 |

## Example Agent Queries

```
# Strategic / cross-domain
"Give me a full practice health report"
"What are our top 3 risks right now?"
"Create a new initiative for Workday AI-powered period close automation"

# Integration domain
"Design a Studio integration for GL journal entry outbound to Snowflake"
"Generate an IDD for our payroll bank file integration"
"What Studio templates do we have published for Accounts Payable?"

# Conversion domain
"Generate a conversion plan for a client going live 2026-10-01 with AP, GL, and Fixed Assets"
"Are we ready for go-live? Mock defect rate is 4%, 0 P1s, rehearsal done, client signed"
"Which of the 14 conversion objects still need iLoad templates?"

# Reporting domain
"Recommend the best report type for a budget vs. actuals comparison across 12 periods"
"Generate a compliant report name for an AR aging report"
"What Prism Analytics assets do we have available?"

# Extend domain
"Design an Extend app to automate expense policy enforcement using AI"
"Generate a Solution Design Document outline for our invoice exception handler"
"What AI-augmented Extend patterns are documented in the CoP library?"
```

## Model Configuration

| Agent | Model | Rationale |
|---|---|---|
| CoP Manager | `claude-opus-4-8` | Strategic reasoning, cross-domain synthesis, report generation |
| Integrations | `claude-sonnet-5` | Deep technical domain, fast tool use |
| Conversion | `claude-sonnet-5` | Deep technical domain, fast tool use |
| Reporting | `claude-sonnet-5` | Deep technical domain, fast tool use |
| Extend | `claude-sonnet-5` | Deep technical domain, fast tool use |

Change models in `config.py`.
