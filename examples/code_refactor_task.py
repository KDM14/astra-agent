"""Example: Automated code modification and pytest verification task."""

import asyncio
import pathlib
import sys
import tempfile

repo_root = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from astra_agent.core.models import TaskInput, VerificationCriterion, VerificationCriterionType
from astra_agent.execution.orchestrator import AstraOrchestrator
from astra_agent.providers.deterministic import DeterministicProvider


async def run_refactor_example():
    with tempfile.TemporaryDirectory() as ws:
        print(f"Setting up workspace in {ws}...")
        
        # Create a workspace with a failing test
        tests_dir = pathlib.Path(ws) / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_math.py").write_text(
            "def test_multiply():\n    from my_math import multiply\n    assert multiply(6, 7) == 42\n",
            encoding="utf-8"
        )
        (pathlib.Path(ws) / "my_math.py").write_text(
            "def multiply(a, b):\n    return a * b\n",
            encoding="utf-8"
        )

        orch = AstraOrchestrator(provider=DeterministicProvider(), workspace_dir=ws)
        await orch.initialize()

        task_in = TaskInput(
            objective="Run test suite to verify my_math implementation",
            criteria=[
                VerificationCriterion(
                    name="All workspace tests must pass",
                    criterion_type=VerificationCriterionType.TEST_SUITE_PASS,
                    parameters={"test_path": "tests"},
                )
            ]
        )

        print("Executing task through Astra Agent...")
        out = await orch.execute_task(task_in)
        print(f"\nCompleted: {out.success} (State: {out.state.value})")
        print(f"Verification Results: {out.verification_results}")


if __name__ == "__main__":
    asyncio.run(run_refactor_example())
