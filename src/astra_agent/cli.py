"""Command line interface for Astra Agent."""

from __future__ import annotations

import argparse
import asyncio
import sys
import uvicorn

from astra_agent.core.config import settings
from astra_agent.core.models import TaskInput
from astra_agent.execution.orchestrator import AstraOrchestrator
from astra_agent.providers.factory import get_provider


def main() -> None:
    """CLI entrypoint for Astra Agent."""
    parser = argparse.ArgumentParser(description="Astra Agent: Production-Oriented Autonomous AI Agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Server command
    server_parser = subparsers.add_parser("serve", help="Start the Astra Agent FastAPI server")
    server_parser.add_argument("--host", default=settings.api_host, help="Bind host (default: 0.0.0.0)")
    server_parser.add_argument("--port", type=int, default=settings.api_port, help="Bind port (default: 8000)")
    server_parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a single task directly via CLI")
    run_parser.add_argument("objective", help="Task objective string to execute")
    run_parser.add_argument("--provider", default=settings.provider, help="LLM provider (mock, deterministic, openai, etc.)")
    run_parser.add_argument("--workspace", default=settings.workspace_dir, help="Workspace directory")

    args = parser.parse_args()

    if args.command == "serve":
        print(f"Starting Astra Agent server on {args.host}:{args.port}...")
        uvicorn.run("astra_agent.api.app:app", host=args.host, port=args.port, reload=args.reload)

    elif args.command == "run":
        async def _run_task():
            prov = get_provider(provider_name=args.provider)
            orch = AstraOrchestrator(provider=prov, workspace_dir=args.workspace)
            await orch.initialize()
            print(f"Executing task with provider '{prov.name}': {args.objective}")
            output = await orch.execute_task(TaskInput(objective=args.objective))
            print("\n=== TASK EXECUTION REPORT ===")
            print(f"Task ID: {output.task_id}")
            print(f"State: {output.state.value}")
            print(f"Success: {output.success}")
            print(f"Duration: {output.duration_seconds}s")
            print(f"Summary: {output.summary}")
            if output.evidence:
                print(f"Evidence items: {len(output.evidence)}")
            if output.error:
                print(f"Error category: {output.error}")

        asyncio.run(_run_task())


if __name__ == "__main__":
    main()
