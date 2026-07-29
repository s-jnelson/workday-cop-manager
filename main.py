#!/usr/bin/env python3
"""
Workday Finance & Technical CoP Manager — CLI entry point

Usage:
    python main.py                          # Interactive REPL (auto-routes)
    python main.py --agent main             # Force main CoP Manager
    python main.py --agent integrations     # Force Integrations sub-agent
    python main.py --agent conversion       # Force Conversion sub-agent
    python main.py --agent reporting        # Force Reporting sub-agent
    python main.py --agent extend           # Force Extend sub-agent
    python main.py --status                 # Collect all sub-agent status reports
    python main.py --init                   # (Re-)initialize data stores
    python main.py --serve                  # Start FastAPI dashboard server

Prerequisites:
    pip install anthropic fastapi uvicorn
    export ANTHROPIC_API_KEY=sk-...
    python main.py --init   (first run)
"""

import sys
import argparse
import os
from pathlib import Path


def ensure_data_initialized():
    data_dir = Path(__file__).parent / "data"
    if not (data_dir / "metrics.json").exists():
        print("[info] Data stores not found — initializing...")
        import subprocess
        subprocess.run([sys.executable, str(data_dir / "init_data.py")], check=True)
        print()


def run_cli(agent_name: str | None = None):
    ensure_data_initialized()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    from orchestrator import CoPOrchestrator
    cop = CoPOrchestrator(api_key=api_key)

    focus_map = {
        "integrations": "integrations",
        "int":          "integrations",
        "conversion":   "conversion",
        "conv":         "conversion",
        "reporting":    "reporting",
        "rep":          "reporting",
        "extend":       "extend",
        "ext":          "extend",
        "main":         "main",
    }
    force = focus_map.get(agent_name or "", None)

    print("\n" + "═" * 60)
    print("  Workday Finance & Technical CoP Manager")
    if force:
        labels = {"main": "CoP Manager (Main)", "integrations": "Integrations Sub-agent", "conversion": "Conversion Sub-agent", "reporting": "Reporting Sub-agent", "extend": "Extend Sub-agent"}
        print(f"  Agent: {labels.get(force, force)}")
    else:
        print("  Agent: Auto-route (type 'exit' to quit)")
    print("═" * 60 + "\n")

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not query:
            continue
        if query.lower() in ("exit", "quit", "q"):
            print("Bye.")
            break

        print("\nAgent: ", end="", flush=True)
        response = cop.run(query, force_agent=force, verbose=True)
        print(f"\n{response}\n")
        print("─" * 60)


def run_status():
    ensure_data_initialized()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    from orchestrator import CoPOrchestrator
    cop = CoPOrchestrator(api_key=api_key)
    print("\nCollecting sub-agent status reports...\n")
    reports = cop.collect_all_status_reports()

    print("\n" + "═" * 60)
    print("  CoP STATUS REPORT SUMMARY")
    print("═" * 60)
    for area, report in reports.items():
        print(f"\n{'─'*40}")
        print(f"  {area.upper()}")
        print(f"{'─'*40}")
        print(report)


def run_server():
    ensure_data_initialized()
    try:
        import uvicorn
        print("\nStarting Workday Finance Tech CoP Manager Dashboard...")
        print("  Dashboard: http://localhost:8000")
        print("  API docs:  http://localhost:8000/docs")
        print("  Press Ctrl+C to stop\n")
        uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
    except ImportError:
        print("ERROR: uvicorn not installed. Run: pip install uvicorn fastapi")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Workday Finance Tech CoP Manager")
    parser.add_argument("--agent", choices=["main","integrations","conversion","reporting","extend","int","conv","rep","ext"], help="Force a specific agent")
    parser.add_argument("--status", action="store_true", help="Collect all sub-agent status reports")
    parser.add_argument("--init", action="store_true", help="Initialize (or re-initialize) all data stores")
    parser.add_argument("--serve", action="store_true", help="Start the FastAPI dashboard server")
    args = parser.parse_args()

    if args.init:
        import subprocess
        data_dir = Path(__file__).parent / "data"
        subprocess.run([sys.executable, str(data_dir / "init_data.py")], check=True)
        return

    if args.serve:
        run_server()
        return

    if args.status:
        run_status()
        return

    run_cli(agent_name=args.agent)


if __name__ == "__main__":
    main()
