"""End-to-end task execution lifecycle tests."""

import pytest
from pathlib import Path

from astra_agent.core.config import AstraConfig
from astra_agent.core.models import (
    TaskInput,
    VerificationCriterion,
    VerificationCriterionType,
)
from astra_agent.execution.orchestrator import AstraOrchestrator
from astra_agent.providers.deterministic import DeterministicProvider


@pytest.mark.asyncio
async def test_e2e_successful_calculation_task(tmp_path):
    ws = str(tmp_path)
    cfg = AstraConfig(
        workspace_dir=ws,
        database_url=f"sqlite+aiosqlite:///{tmp_path}/e2e_calc.db",
        enable_persistence=True,
    )
    orch = AstraOrchestrator(
        provider=DeterministicProvider(),
        workspace_dir=ws,
        config=cfg,
    )
    await orch.initialize()

    task_in = TaskInput(
        objective="Calculate '25 * 4' and verify math",
        criteria=[
            VerificationCriterion(
                name="Check math result equals 100",
                criterion_type=VerificationCriterionType.NUMERIC_EQUALITY,
                parameters={"variable_name": "result", "expected_value": 100.0},
            )
        ]
    )

    output = await orch.execute_task(task_in)
    assert output.success is True
    assert output.state.value == "COMPLETED"
    assert len(output.evidence) >= 1
    assert len(output.verification_results) == 1
    assert output.verification_results[0].passed is True


@pytest.mark.asyncio
async def test_e2e_successful_file_pipeline_task(tmp_path):
    ws = str(tmp_path)
    cfg = AstraConfig(
        workspace_dir=ws,
        database_url=f"sqlite+aiosqlite:///{tmp_path}/e2e_file.db",
        enable_persistence=True,
    )
    orch = AstraOrchestrator(
        provider=DeterministicProvider(),
        workspace_dir=ws,
        config=cfg,
    )
    await orch.initialize()

    task_in = TaskInput(
        objective="Write destination file and verify content",
        criteria=[
            VerificationCriterion(
                name="Check output.txt exists",
                criterion_type=VerificationCriterionType.FILE_EXISTS,
                parameters={"path": "output.txt"},
            ),
            VerificationCriterion(
                name="Check output.txt content",
                criterion_type=VerificationCriterionType.FILE_CONTAINS,
                parameters={"path": "output.txt", "text": "verified output"},
            ),
        ]
    )

    output = await orch.execute_task(task_in)
    assert output.success is True
    assert output.state.value == "COMPLETED"
    assert len(output.verification_results) == 2
    assert all(vr.passed for vr in output.verification_results)


@pytest.mark.asyncio
async def test_e2e_verification_failure_detected(tmp_path):
    ws = str(tmp_path)
    cfg = AstraConfig(
        workspace_dir=ws,
        database_url=f"sqlite+aiosqlite:///{tmp_path}/e2e_fail.db",
        enable_persistence=True,
    )
    orch = AstraOrchestrator(
        provider=DeterministicProvider(),
        workspace_dir=ws,
        config=cfg,
    )
    await orch.initialize()

    task_in = TaskInput(
        objective="Calculate '10 + 5'",
        criteria=[
            VerificationCriterion(
                name="Expect impossible value",
                criterion_type=VerificationCriterionType.NUMERIC_EQUALITY,
                parameters={"variable_name": "result", "expected_value": 9999.0},
            )
        ],
        max_retries=1,
    )

    output = await orch.execute_task(task_in)
    # The agent must NOT claim success when verification fails!
    assert output.success is False
    assert output.state.value == "FAILED"
    assert output.error == "ERR_VERIFICATION_FAILED"
    assert output.verification_results[0].passed is False
