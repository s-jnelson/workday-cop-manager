"""
Base agent class for the Workday Finance Tech CoP agent system.
Supports Anthropic Claude (when ANTHROPIC_API_KEY is set) and Ollama local
models as a zero-config fallback. Web search is available to all agents.
"""

from __future__ import annotations
import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent / "data"
METHODOLOGY_DIR = Path(__file__).parent.parent / "methodology"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"

_agent_write_lock = threading.Lock()  # shared across all agent instances


# ── Backend detection ──────────────────────────────────────────────────────────

def _get_anthropic_key() -> str:
    config_file = DATA_DIR / "config.json"
    if config_file.exists():
        try:
            import json as _json
            key = _json.loads(config_file.read_text(encoding="utf-8")).get("anthropic_api_key", "")
            if key.startswith("sk-ant-") and len(key) > 20:
                return key
        except Exception:
            pass
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return key if key.startswith("sk-ant-") and len(key) > 20 else ""


def _get_groq_key() -> str:
    config_file = DATA_DIR / "config.json"
    if config_file.exists():
        try:
            import json as _json
            key = _json.loads(config_file.read_text(encoding="utf-8")).get("groq_api_key", "")
            if key.startswith("gsk_") and len(key) > 20:
                return key
        except Exception:
            pass
    key = os.environ.get("GROQ_API_KEY", "")
    return key if key.startswith("gsk_") and len(key) > 20 else ""


def _get_ollama_model() -> str:
    """Return the best available Ollama model, or empty string if not running."""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/tags", headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
        models = [m["name"] for m in data.get("models", [])]
        if not models:
            return ""
        for pref in ["llama3.2", "llama3.1", "llama3", "mistral", "qwen2.5", "gemma2", "phi3"]:
            match = next((m for m in models if m.startswith(pref)), None)
            if match:
                return match
        return models[0]
    except Exception:
        return ""


# ── Web search ─────────────────────────────────────────────────────────────────

def web_search(query: str) -> str:
    """Search the web via DuckDuckGo Instant Answer API. No API key required."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = (
            f"https://api.duckduckgo.com/?q={encoded}"
            "&format=json&no_html=1&skip_disambig=1"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "CoPAgent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        parts: list[str] = []
        if data.get("AbstractText"):
            parts.append(f"**Summary**: {data['AbstractText']}")
            if data.get("AbstractSource"):
                parts.append(f"Source: {data['AbstractSource']}")
        for item in data.get("RelatedTopics", [])[:6]:
            if isinstance(item, dict) and item.get("Text"):
                parts.append(f"- {item['Text'][:300]}")
        return "\n".join(parts) if parts else "No results found. Try a more specific query."
    except Exception as exc:
        return f"Web search unavailable: {exc}"


# ── Base agent ─────────────────────────────────────────────────────────────────

class BaseAgent:
    """
    Shared foundation for all CoP agents.
    Subclasses define: model, system_prompt, and tool_definitions.
    """

    model: str = "claude-sonnet-5"
    system_prompt: str = ""
    ollama_system_prompt: str = ""  # compact override used on the Ollama path
    tool_definitions: list[dict] = []
    max_iterations: int = 15

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or _get_anthropic_key()
        self._groq_key: str = ""
        self._ollama_model: str = ""
        self.conversation_history: list[dict] = []

        if not self._api_key:
            self._groq_key = _get_groq_key()

        if not self._api_key and not self._groq_key:
            self._ollama_model = _get_ollama_model()

        if self._api_key:
            import anthropic as _anthropic
            self._anthropic_client = _anthropic.Anthropic(api_key=self._api_key)
        else:
            self._anthropic_client = None

    # ── Utility ──────────────────────────────────────────────────────────────

    def _use_groq(self) -> bool:
        return not self._api_key and bool(self._groq_key)

    def _use_ollama(self) -> bool:
        return not self._api_key and not self._groq_key and bool(self._ollama_model)

    def _load_all_dashboard_data(self) -> str:
        """
        Build a compact KPI summary (~500-1000 tokens) from all dashboard data.
        Avoids loading full JSON blobs so Ollama doesn't have to process megabytes.
        """
        metrics = self._load_json("metrics.json")
        goals = self._load_json("goals.json")
        initiatives = self._load_json("initiatives.json")
        consultants = self._load_json("consultants.json")
        assets = self._load_json("assets.json")
        ai_cases = self._load_json("ai_use_cases.json")

        lines: list[str] = []

        # Practice-level KPIs
        if ps := metrics.get("practice_summary", {}):
            lines.append(
                f"PRACTICE KPIs: Methodology adoption {ps.get('methodology_adoption_pct')}%"
                f" (target 90%), Avg utilization {ps.get('avg_utilization_pct')}%"
                f" (target 75-85%), CSAT {ps.get('avg_csat')}, "
                f"Time-to-deploy {ps.get('avg_weeks_to_deploy')} weeks"
            )
        if dm := metrics.get("deployment_metrics", {}):
            lines.append(
                f"Deployment: Cutover success {dm.get('cutover_success_rate_pct')}%"
                f", Active projects {dm.get('active_projects')}"
                f", Completed this year {dm.get('deployments_completed_ytd')}"
            )
        if am := metrics.get("asset_metrics", {}):
            lines.append(
                f"Assets: Reuse rate {am.get('asset_reuse_rate_pct')}%"
                f" (target 80%), Total published {am.get('total_published_assets')}"
            )
        if aim := metrics.get("ai_metrics", {}):
            lines.append(
                f"AI: {aim.get('use_cases_deployed')} deployed"
                f" / {aim.get('use_cases_target')} target"
                f", {aim.get('use_cases_in_development')} in development"
            )

        # Focus area health
        if fah := metrics.get("focus_area_health", {}):
            lines.append("\nFOCUS AREA HEALTH:")
            for area, h in fah.items():
                lines.append(
                    f"  {area}: score {h.get('score')}/100, RAG {h.get('rag_status')}"
                    f", consultants {h.get('consultants')}, utilization {h.get('utilization_pct')}%"
                )

        # Practice goals
        practice_goals = goals.get("practice_goals", [])
        if practice_goals:
            lines.append(f"\nPRACTICE GOALS ({len(practice_goals)}):")
            for g in practice_goals:
                pct = round(g.get("current_value", 0) / max(g.get("target_value", 1), 1) * 100)
                lines.append(
                    f"  [{g.get('status')}] {g['title']}: "
                    f"{g.get('current_value')}/{g.get('target_value')} {g.get('unit')} ({pct}%)"
                    + (f" — due {g.get('due_date')}" if g.get("due_date") else "")
                )

        # Sub-agent goals by area (top 3 each)
        for area, area_goals in goals.get("subagent_goals", {}).items():
            if area_goals:
                lines.append(f"\n{area.upper()} GOALS ({len(area_goals)}):")
                for g in area_goals[:4]:
                    pct = round(g.get("current_value", 0) / max(g.get("target_value", 1), 1) * 100)
                    lines.append(
                        f"  [{g.get('status')}] {g['title']}: "
                        f"{g.get('current_value')}/{g.get('target_value')} {g.get('unit')} ({pct}%)"
                    )

        # Initiatives (active first, then planning)
        sorted_inits = sorted(
            initiatives,
            key=lambda i: (0 if i.get("status") == "active" else 1 if i.get("status") == "planning" else 2)
        )
        lines.append(f"\nINITIATIVES ({len(initiatives)} total):")
        for i in sorted_inits[:8]:
            lines.append(
                f"  [{i.get('status')}] {i['title']}: {i.get('progress_pct')}%"
                f" ({i.get('priority')} priority)"
                + (f", owner {i.get('owner')}" if i.get("owner") else "")
            )

        # Consultants summary
        if consultants:
            avg_util = round(sum(c.get("utilization_pct", 0) for c in consultants) / len(consultants))
            by_area: dict[str, list] = {}
            for c in consultants:
                by_area.setdefault(c.get("focus_area", "other"), []).append(c)
            lines.append(f"\nCONSULTANTS: {len(consultants)} total, avg utilization {avg_util}%")
            for area, members in by_area.items():
                names = ", ".join(m["name"] for m in members[:5])
                extra = f" +{len(members)-5} more" if len(members) > 5 else ""
                lines.append(f"  {area}: {names}{extra}")

        # Assets summary
        if assets:
            by_status: dict[str, int] = {}
            for a in assets:
                by_status[a.get("status", "?")] = by_status.get(a.get("status", "?"), 0) + 1
            status_str = ", ".join(f"{v} {k}" for k, v in by_status.items())
            lines.append(f"\nASSETS: {len(assets)} total ({status_str})")
            for a in [x for x in assets if x.get("status") == "published"][:5]:
                lines.append(f"  - {a['name']} [{a.get('focus_area')}] v{a.get('version')} — {a.get('deployments')} deployments")

        # AI use cases
        if ai_cases:
            lines.append(f"\nAI USE CASES ({len(ai_cases)}):")
            for uc in ai_cases:
                lines.append(
                    f"  [{uc.get('status')}] {uc['title']}"
                    f" ({uc.get('focus_area')}) — ROI: {uc.get('estimated_roi', 'TBD')}"
                    + (" [CLIENT DEPLOYED]" if uc.get("client_deployed") else "")
                )

        return "\n".join(lines)

    def _ollama_run_direct(self, user_message: str) -> str:
        """
        Fast single-call path for Groq and Ollama: injects all dashboard data
        into context and makes one LLM call (no tool-calling loop).
        """
        data_context = self._load_all_dashboard_data()
        base_prompt = (self.ollama_system_prompt or self.system_prompt).strip()
        system = (
            base_prompt
            + "\n\nAnswer based on the dashboard data provided below. "
            "Be concise and factual. For questions requiring live web data, "
            "say 'For the latest information, I recommend checking Workday Community (community.workday.com).'"
            "\n\n## Current Dashboard Data\n"
            + data_context
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ]

        if self._use_groq():
            url = f"{GROQ_BASE_URL}/chat/completions"
            model = GROQ_DEFAULT_MODEL
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self._groq_key}"}
            payload = {"model": model, "messages": messages, "stream": False}
            timeout = 60
        else:
            url = f"{OLLAMA_URL}/v1/chat/completions"
            model = self._ollama_model
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": model, "messages": messages, "stream": False,
                "options": {"num_predict": 600, "temperature": 0.1},
            }
            timeout = 180

        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
        return result["choices"][0]["message"].get("content", "")

    def _load_json(self, filename: str) -> Any:
        path = DATA_DIR / filename
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_json(self, filename: str, data: Any) -> None:
        path = DATA_DIR / filename
        with _agent_write_lock:
            path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def _handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        """Base handler. Handles web_search; subclasses extend via dispatch dict."""
        if tool_name == "web_search":
            result = web_search(tool_input.get("query", ""))
            return json.dumps({"results": result})
        return json.dumps({"error": f"Tool '{tool_name}' not implemented."})

    # ── Content block normalisation ───────────────────────────────────────────

    @staticmethod
    def _block_type(block) -> str:
        return block.get("type") if isinstance(block, dict) else getattr(block, "type", "")

    @staticmethod
    def _block_text(block) -> str:
        return block.get("text", "") if isinstance(block, dict) else getattr(block, "text", "")

    @staticmethod
    def _block_to_dict(block) -> dict:
        if isinstance(block, dict):
            return block
        b: dict = {"type": block.type}
        if block.type == "text":
            b["text"] = block.text
        elif block.type == "tool_use":
            b.update({"id": block.id, "name": block.name, "input": block.input})
        return b

    # ── Anthropic backend ─────────────────────────────────────────────────────

    def _call_anthropic(self) -> tuple[str, list]:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": 8192,
            "system": self.system_prompt,
            "messages": self.conversation_history,
        }
        if self.tool_definitions:
            kwargs["tools"] = self.tool_definitions
        resp = self._anthropic_client.messages.create(**kwargs)
        return resp.stop_reason, resp.content

    # ── Ollama backend (OpenAI-compatible) ────────────────────────────────────

    def _tool_defs_to_openai(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get(
                        "input_schema", {"type": "object", "properties": {}}
                    ),
                },
            }
            for t in self.tool_definitions
        ]

    def _messages_to_openai(self) -> list[dict]:
        oai: list[dict] = []
        if self.system_prompt:
            oai.append({"role": "system", "content": self.system_prompt})

        for msg in self.conversation_history:
            role = msg["role"]
            content = msg["content"]

            if isinstance(content, str):
                oai.append({"role": role, "content": content})
                continue

            if role == "assistant":
                texts: list[str] = []
                tool_calls: list[dict] = []
                for b in content:
                    bt = self._block_type(b)
                    if bt == "text":
                        texts.append(self._block_text(b))
                    elif bt == "tool_use":
                        bd = self._block_to_dict(b)
                        tool_calls.append({
                            "id": bd.get("id", f"call_{len(tool_calls)}"),
                            "type": "function",
                            "function": {
                                "name": bd.get("name", ""),
                                "arguments": json.dumps(bd.get("input", {})),
                            },
                        })
                m: dict = {
                    "role": "assistant",
                    "content": "\n".join(texts) or None,
                }
                if tool_calls:
                    m["tool_calls"] = tool_calls
                oai.append(m)

            elif role == "user":
                # May contain tool_result blocks
                tool_results = [
                    b for b in content
                    if (self._block_type(b) == "tool_result")
                ]
                text_blocks = [
                    b for b in content
                    if (self._block_type(b) == "text")
                ]
                if tool_results:
                    for b in tool_results:
                        bd = self._block_to_dict(b)
                        rc = bd.get("content", "")
                        if isinstance(rc, list):
                            rc = "\n".join(
                                c.get("text", "") for c in rc if isinstance(c, dict)
                            )
                        oai.append({
                            "role": "tool",
                            "tool_call_id": bd.get("tool_use_id", ""),
                            "content": str(rc),
                        })
                elif text_blocks:
                    oai.append({
                        "role": "user",
                        "content": "\n".join(self._block_text(b) for b in text_blocks),
                    })

        return oai

    def _call_openai_compat(self, base_url: str, auth_header: str, model: str) -> tuple[str, list[dict]]:
        """Shared OpenAI-compatible call used by both Groq and Ollama agentic paths."""
        payload: dict = {
            "model": model,
            "messages": self._messages_to_openai(),
            "stream": False,
        }
        if self.tool_definitions:
            payload["tools"] = self._tool_defs_to_openai()

        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": auth_header},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())

        choice = result["choices"][0]
        message = choice["message"]
        finish_reason = choice.get("finish_reason", "stop")

        if finish_reason == "tool_calls" and message.get("tool_calls"):
            blocks: list[dict] = []
            if message.get("content"):
                blocks.append({"type": "text", "text": message["content"]})
            for tc in message["tool_calls"]:
                try:
                    args = json.loads(tc["function"].get("arguments", "{}"))
                except (json.JSONDecodeError, KeyError):
                    args = {}
                blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id", f"call_{len(blocks)}"),
                    "name": tc["function"]["name"],
                    "input": args,
                })
            return "tool_use", blocks

        return "end_turn", [{"type": "text", "text": message.get("content", "")}]

    def _call_groq(self) -> tuple[str, list[dict]]:
        return self._call_openai_compat(
            GROQ_BASE_URL, f"Bearer {self._groq_key}", GROQ_DEFAULT_MODEL
        )

    def _call_ollama(self) -> tuple[str, list[dict]]:
        return self._call_openai_compat(
            f"{OLLAMA_URL}/v1", "", self._ollama_model
        )

    # ── Agentic loop ──────────────────────────────────────────────────────────

    def run(self, user_message: str, verbose: bool = True) -> str:
        """Run the agent. Priority: Anthropic → Groq → Ollama → rule-based message."""
        if not self._api_key and not self._groq_key and not self._ollama_model:
            return (
                "No AI backend configured. Options:\n"
                "• Anthropic API key — add in dashboard Settings (best quality)\n"
                "• Groq API key — free tier at console.groq.com (fast, good quality)\n"
                "• Ollama — free local models, install at ollama.com"
            )

        # Groq and Ollama use a fast single-call path (no tool loop)
        if self._use_groq():
            try:
                return self._ollama_run_direct(user_message)  # reuses same prompt builder
            except Exception as exc:
                return f"Groq call failed: {exc}"

        if self._use_ollama():
            try:
                return self._ollama_run_direct(user_message)
            except Exception as exc:
                return f"Ollama call failed: {exc}"

        self.conversation_history.append({"role": "user", "content": user_message})

        for _ in range(self.max_iterations):
            try:
                stop_reason, raw_content = self._call_anthropic()
            except Exception as exc:
                return f"LLM call failed: {exc}"

            # Normalise to dicts for unified storage
            content_dicts = [
                b if isinstance(b, dict) else self._block_to_dict(b)
                for b in raw_content
            ]
            self.conversation_history.append(
                {"role": "assistant", "content": content_dicts}
            )

            if stop_reason == "end_turn":
                return "\n".join(
                    b.get("text", "")
                    for b in content_dicts
                    if b.get("type") == "text"
                )

            if stop_reason == "tool_use":
                tool_results: list[dict] = []
                for block in content_dicts:
                    if block.get("type") == "tool_use":
                        name = block.get("name", "")
                        inp = block.get("input", {})
                        if verbose:
                            print(f"  [tool] {name}({json.dumps(inp)[:120]})")
                        result = self._handle_tool_call(name, inp)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.get("id", ""),
                            "content": result,
                        })
                self.conversation_history.append(
                    {"role": "user", "content": tool_results}
                )
                continue

            break  # unexpected stop_reason

        return "Agent reached maximum iterations without completing."

    def reset(self) -> None:
        self.conversation_history = []
