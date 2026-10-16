"""Example: Data pipeline file generation and JSON schema verification."""

import asyncio
import pathlib
import sys
import tempfile

repo_root = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from astra_agent.core.models import TaskInput, VerificationCriterion, VerificationCriterionType
from astra_agent.execution.orchestrator import AstraOrchestrator
from astra_agent.providers.deterministic import DeterministicProvider


async def run_data_pipeline_example():
    with tempfile.TemporaryDirectory() as ws:
        orch = AstraOrchestrator(provider=DeterministicProvider(), workspace_dir=ws)
        await orch.initialize()

        task_in = TaskInput(
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

        print("Executing data pipeline task...")
        out = await orch.execute_task(task_in)
        print(f"Task Success: {out.success}")
        print(f"Summary: {out.summary}")
        print(f"Evidence captured: {len(out.evidence)}")


if __name__ == "__main__":
    asyncio.run(run_data_pipeline_example())
