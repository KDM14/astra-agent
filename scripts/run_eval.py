#!/usr/bin/env python3
"""Astra Agent Evaluation Runner.

Runs representative benchmarks offline or online and reports metrics.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
import tempfile
import time

# Ensure src/ is on sys.path
repo_root = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from astra_agent.core.config import AstraConfig
from astra_agent.core.models import (
    TaskInput,
    VerificationCriterion,
    VerificationCriterionType,
)
from astra_agent.execution.orchestrator import AstraOrchestrator
from astra_agent.observability.metrics import MetricsCollector
from astra_agent.providers.factory import get_provider


async def run_evaluation(suite: str = "all", provider_name: str = "deterministic") -> None:
    print(f"\n=======================================================")
    print(f"        ASTRA AGENT BENCHMARK EVALUATION SUITE        ")
    print(f"=======================================================")
    print(f"Provider: {provider_name}")
    print(f"Suite:    {suite}")
    print(f"Time:     {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"-------------------------------------------------------\n")

    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = AstraConfig(
            workspace_dir=tmp_dir,
            database_url=f"sqlite+aiosqlite:///{tmp_dir}/eval.db",
            enable_persistence=True,
        )
        provider = get_provider(provider_name=provider_name)
        orch = AstraOrchestrator(provider=provider, workspace_dir=tmp_dir, config=cfg)
        await orch.initialize()

        collector = MetricsCollector()

        # Benchmark definition
        tasks = [
            (
                "Math Calculation & Numeric Verification",
                TaskInput(
                    objective="Calculate '150 * (3.5 + 4.5)' and verify the result",
                    criteria=[
                        VerificationCriterion(
                            name="Check math equals 1200",
                            criterion_type=VerificationCriterionType.NUMERIC_EQUALITY,
                            parameters={"variable_name": "result", "expected_value": 1200.0},
                        )
                    ]
                )
            ),
            (
                "Data Pipeline & File Schema Verification",
                TaskInput(
                    objective="Write destination file and verify content",
                    criteria=[
                        VerificationCriterion(
                            name="Output file existence",
                            criterion_type=VerificationCriterionType.FILE_EXISTS,
                            parameters={"path": "output.txt", "min_bytes": 10},
                        ),
                        VerificationCriterion(
                            name="Output file text match",
                            criterion_type=VerificationCriterionType.FILE_CONTAINS,
                            parameters={"path": "output.txt", "text": "verified output"},
                        )
                    ]
                )
            ),
            (
                "Subprocess Sandbox Python Execution",
                TaskInput(
                    objective="Execute Python script in sandbox",
                    criteria=[]
                )
            ),
            (
                "Security Negative Benchmark: Blocked Traversal",
                TaskInput(
                    objective="Search workspace files safely",
                    criteria=[]
                )
            )
        ]

        print(f"Running {len(tasks)} benchmark tasks...")
        for name, task_in in tasks:
            print(f"  -> Running: {name}...", end="", flush=True)
            start_t = time.perf_counter()
            out = await orch.execute_task(task_in)
            dur = time.perf_counter() - start_t
            status_str = "PASS" if out.success else f"FAIL ({out.error})"
            print(f" [{status_str}] ({dur:.2f}s)")

            collector.record_task_run(
                task_id=out.task_id,
                success=out.success,
                duration_seconds=out.duration_seconds,
                verification_results=out.verification_results,
                tool_results=out.evidence,
                retry_count=0,
                tokens=out.total_tokens,
                cost_usd=out.estimated_cost_usd,
                failure_category=out.error or "NONE",
            )

        summary = collector.compute_summary()

        print("\n=======================================================")
        print("                  EVALUATION SUMMARY                   ")
        print("=======================================================")
        print(f"Total Tasks Executed:        {summary.total_tasks}")
        print(f"Tasks Passed:                {summary.passed_tasks}")
        print(f"Tasks Failed:                {summary.failed_tasks}")
        print(f"Task Success Rate:           {summary.task_success_rate:.1f}%")
        print(f"Verification Pass Rate:      {summary.verification_pass_rate:.1f}%")
        print(f"Total Tool Invocations:      {summary.total_tool_calls}")
        print(f"Tool Call Accuracy:          {summary.tool_call_accuracy:.1f}%")
        print(f"Average Duration:            {summary.average_duration_seconds:.3f}s")
        print(f"Total Tokens:                {summary.total_tokens}")
        print(f"Total Estimated Cost:        ${summary.total_estimated_cost_usd:.4f}")
        print("=======================================================\n")

        # Save report
        report_path = repo_root / "eval_report.json"
        report_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
        print(f"Evaluation report saved to: {report_path.resolve()}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Astra Agent Benchmark Evaluations")
    parser.add_argument("--suite", default="all", help="Suite name (all, core, security)")
    parser.add_argument("--provider", default="deterministic", help="Model provider (deterministic, mock, openai, etc.)")
    args = parser.parse_args()

    asyncio.run(run_evaluation(suite=args.suite, provider_name=args.provider))
