#!/usr/bin/env python3
"""Local development server and task execution runner."""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys
import uvicorn

repo_root = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from astra_agent.core.config import settings
from astra_agent.core.models import TaskInput
from astra_agent.execution.orchestrator import AstraOrchestrator
from astra_agent.providers.factory import get_provider


def main():
    parser = argparse.ArgumentParser(description="Run Astra Agent locally")
    parser.add_argument("--mode", choices=["server", "task"], default="server", help="Execution mode")
    parser.add_argument("--objective", default="Calculate '12 * (4.5 + 3.5)'", help="Objective if mode is task")
    parser.add_argument("--provider", default=settings.provider, help="LLM provider")
    parser.add_argument("--port", type=int, default=settings.api_port, help="Server port")
    args = parser.parse_args()

    if args.mode == "server":
        print(f"Starting Astra Agent server on http://localhost:{args.port}...")
        print(f"Web UI available at: http://localhost:{args.port}/ui/")
        print(f"API Docs available at: http://localhost:{args.port}/docs")
        uvicorn.run("astra_agent.api.app:app", host="0.0.0.0", port=args.port, reload=True)
    else:
        async def _run():
            prov = get_provider(provider_name=args.provider)
            orch = AstraOrchestrator(provider=prov)
            await orch.initialize()
            print(f"Running task with provider '{prov.name}': {args.objective}")
            out = await orch.execute_task(TaskInput(objective=args.objective))
            print(f"\nResult: State={out.state.value}, Success={out.success}, Duration={out.duration_seconds}s")
            print(f"Summary: {out.summary}")
            if out.evidence:
                print(f"Evidence: {out.evidence}")

        asyncio.run(_run())


if __name__ == "__main__":
    main()
