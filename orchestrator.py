"""
Multi-agent orchestrator for the Workday Finance Tech CoP.

The CoP Manager agent is the root. It can spin up sub-agents for domain-specific
work, receive their status reports, and coordinate cross-domain decisions.

Usage:
    from orchestrator import CoPOrchestrator
    cop = CoPOrchestrator()
    result = cop.run("Give me a full practice health report")
"""

from __future__ import annotations
import json
from agents.cop_manager import CoPManagerAgent
from agents.integrations_agent import IntegrationsAgent
from agents.conversion_agent import ConversionAgent
from agents.reporting_agent import ReportingAgent
from agents.extend_agent import ExtendAgent


FOCUS_AREA_KEYWORDS = {
    "integrations": ["integration", "studio", "eib", "connector", "raas", "api", "soap", "rest", "peci", "isu", "interface"],
    "conversion": ["conversion", "convert", "iload", "migration", "migrate", "cutover", "mock run", "data load", "mapping"],
    "reporting": ["report", "reporting", "matrix", "composite", "prism", "dashboard", "discovery board", "birt", "calculated field"],
    "extend": ["extend", "orchestration", "custom app", "related action", "business object", "custom validation"],
}


def _detect_focus_area(query: str) -> str | None:
    q = query.lower()
    for area, keywords in FOCUS_AREA_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return area
    return None


class CoPOrchestrator:
    """
    Routes queries to the appropriate agent (main or sub-agent).
    Main CoP Manager handles strategic/cross-domain questions.
    Sub-agents handle domain-specific deep dives.
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key
        self._main = CoPManagerAgent(api_key=api_key)
        self._sub_agents: dict[str, object] = {}

    def _get_sub_agent(self, area: str):
        if area not in self._sub_agents:
            cls = {
                "integrations": IntegrationsAgent,
                "conversion": ConversionAgent,
                "reporting": ReportingAgent,
                "extend": ExtendAgent,
            }[area]
            self._sub_agents[area] = cls(api_key=self._api_key)
        return self._sub_agents[area]

    def run(self, query: str, force_agent: str | None = None, history: list | None = None, verbose: bool = True) -> str:
        """
        Route the query to the best agent.

        Args:
            query: The question or task.
            force_agent: One of 'main', 'integrations', 'conversion', 'reporting', 'extend'.
            history: Prior conversation turns [{role, content}] for multi-turn context.
            verbose: Print tool call traces.
        """
        if force_agent == "main" or force_agent is None:
            detected = _detect_focus_area(query) if force_agent is None else None
            if detected and "practice" not in query.lower() and "overall" not in query.lower() and "all" not in query.lower():
                agent = self._get_sub_agent(detected)
                if verbose:
                    print(f"\n[orchestrator] Routing to {detected.capitalize()} sub-agent")
            else:
                agent = self._main
                if verbose:
                    print("\n[orchestrator] Routing to CoP Manager (main agent)")
        else:
            agent = self._get_sub_agent(force_agent) if force_agent != "main" else self._main

        return agent.run(query, history=history or [], verbose=verbose)

    def collect_all_status_reports(self, verbose: bool = True) -> dict:
        """Pull status reports from all four sub-agents and return compiled results."""
        reports = {}
        for area in ["integrations", "conversion", "reporting", "extend"]:
            if verbose:
                print(f"\n[orchestrator] Collecting status from {area} sub-agent...")
            agent = self._get_sub_agent(area)
            report = agent.run(f"Generate a status report for the {area} focus area.", verbose=verbose)
            reports[area] = report
        return reports

    def generate_dashboard_data(self) -> dict:
        """Collect all data needed to render the practice dashboard. No LLM calls — pure data."""
        from pathlib import Path
        import json

        data_dir = Path(__file__).parent / "data"
        meth_dir = Path(__file__).parent / "methodology"

        def load(f):
            p = data_dir / f
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

        return {
            "metrics": load("metrics.json"),
            "goals": load("goals.json"),
            "initiatives": load("initiatives.json"),
            "consultants": load("consultants.json"),
            "assets": load("assets.json"),
            "ai_use_cases": load("ai_use_cases.json"),
        }

    def reset_all(self) -> None:
        self._main.reset()
        for agent in self._sub_agents.values():
            agent.reset()
