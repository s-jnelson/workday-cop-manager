"""
Workday Finance & Technical CoP Manager — Configuration
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
METHODOLOGY_DIR = BASE_DIR / "methodology"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Model routing — main agent uses Opus for strategic reasoning, sub-agents use Sonnet
MAIN_AGENT_MODEL = "claude-opus-4-8"
SUB_AGENT_MODEL = "claude-sonnet-5"

# Sub-agent focus areas
FOCUS_AREAS = ["integrations", "conversion", "reporting", "extend"]

# Workday Financial Modules tracked by the CoP
WORKDAY_FINANCIAL_MODULES = [
    "Financial Accounting (GL)",
    "Accounts Payable",
    "Accounts Receivable",
    "Fixed Assets",
    "Expenses",
    "Procurement",
    "Banking & Settlement",
    "Financial Projects",
    "Budget & Planning",
    "Tax Management",
    "Consolidation & Intercompany",
    "Revenue Management",
    "Cash Management",
    "Financial Reporting",
]

# KPI definitions for practice measurement
PRACTICE_KPIS = {
    "time_to_deploy_reduction": {
        "description": "% reduction in average deployment time vs. prior year baseline",
        "unit": "percent",
        "target_direction": "decrease",
        "baseline_weeks": 26,
    },
    "client_satisfaction": {
        "description": "Average client satisfaction score across all active engagements",
        "unit": "score_1_to_10",
        "target_direction": "increase",
    },
    "asset_reuse_rate": {
        "description": "% of deployments leveraging standardized CoP assets",
        "unit": "percent",
        "target_direction": "increase",
    },
    "consultant_utilization": {
        "description": "Average billable utilization across CoP consultants",
        "unit": "percent",
        "target_direction": "optimize",
        "optimal_range": [75, 85],
    },
    "ai_use_cases_deployed": {
        "description": "Number of AI use cases deployed to clients",
        "unit": "count",
        "target_direction": "increase",
    },
    "methodology_adoption": {
        "description": "% of projects following the standard CoP deployment methodology",
        "unit": "percent",
        "target_direction": "increase",
    },
    "defect_escape_rate": {
        "description": "% of go-live defects that were not caught in testing",
        "unit": "percent",
        "target_direction": "decrease",
    },
    "cutover_success_rate": {
        "description": "% of cutovers completed on first attempt without rollback",
        "unit": "percent",
        "target_direction": "increase",
    },
}

API_HOST = "0.0.0.0"
API_PORT = 8000
DASHBOARD_PORT = 8001
