"""Evaluation benchmark suite measuring task success, tool accuracy, and metrics."""

import pytest
from pathlib import Path

from astra_agent.core.config import AstraConfig
from astra_agent.core.models import (
    TaskInput,
    VerificationCriterion,
    VerificationCriterionType,
)
from astra_agent.execution.orchestrator import AstraOrchestrator
from astra_agent.observability.metrics import MetricsCollector
from astra_agent.providers.deterministic import DeterministicProvider


@pytest.mark.asyncio
async def test_benchmark_suite_metrics(tmp_path):
    ws = str(tmp_path)
    cfg = AstraConfig(
        workspace_dir=ws,
        database_url=f"sqlite+aiosqlite:///{tmp_path}/bench.db",
        enable_persistence=True,
    )
    orch = AstraOrchestrator(
        provider=DeterministicProvider(),
        workspace_dir=ws,
        config=cfg,
    )
    await orch.initialize()

    collector = MetricsCollector()

    benchmark_tasks = [
        # Task 1: Calculation & Verification
        TaskInput(
            objective="Calculate '50 * 2' and verify math",
            criteria=[
                VerificationCriterion(
                    name="Math check 100",
                    criterion_type=VerificationCriterionType.NUMERIC_EQUALITY,
                    parameters={"variable_name": "result", "expected_value": 100.0},
                )
            ]
        ),
        # Task 2: File Write & Verification
        TaskInput(
            objective="Write destination file and verify",
            criteria=[
                VerificationCriterion(
                    name="Output file check",
                    criterion_type=VerificationCriterionType.FILE_EXISTS,
                    parameters={"path": "output.txt"},
                )
            ]
        ),
        # Task 3: Python execution
        TaskInput(
            objective="Execute Python script in sandbox",
            criteria=[]
        ),
    ]

    for task_in in benchmark_tasks:
        out = await orch.execute_task(task_in)
        collector.record_task_run(
            task_id=out.task_id,
            success=out.success,
            duration_seconds=out.duration_seconds,
            verification_results=out.verification_results,
            tool_results=out.evidence,
            retry_count=0,
            tokens=out.total_tokens,
            cost_usd=out.estimated_cost_usd,
        )

    summary = collector.compute_summary()
    
    # Assert benchmark criteria
    assert summary.total_tasks == 3
    assert summary.passed_tasks == 3
    assert summary.task_success_rate == 100.0
    assert summary.verification_pass_rate == 100.0
    assert summary.average_duration_seconds < 5.0
