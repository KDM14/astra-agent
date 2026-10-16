"""Integration tests for async database persistence and checkpoints."""

import pytest
from astra_agent.core.models import ExecutionCheckpoint, PlanStep, TaskInput, TaskPlan
from astra_agent.core.state import TaskState
from astra_agent.persistence.database import DatabaseManager
from astra_agent.persistence.repository import TaskRepository


@pytest.mark.asyncio
async def test_persistence_lifecycle(tmp_path):
    db_file = tmp_path / "test_astra.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    db_mgr = DatabaseManager(database_url=db_url)

    await db_mgr.init_db()

    async for session in db_mgr.get_session():
        repo = TaskRepository(session)

        # 1. Create task
        task_input = TaskInput(objective="Integration test task", parameters={"key": "val"})
        task_record = await repo.create_task("tsk_persist_1", task_input)
        assert task_record.task_id == "tsk_persist_1"
        assert task_record.state == TaskState.PENDING.value

        # 2. Update state to PLANNED
        await repo.update_task_state("tsk_persist_1", TaskState.PLANNED)
        t = await repo.get_task("tsk_persist_1")
        assert t.state == TaskState.PLANNED.value

        # 3. Save plan
        plan = TaskPlan(
            objective="Integration test plan",
            steps=[
                PlanStep(step_id="stp_1", order=1, title="Step 1", description="", tool_name="calculator"),
            ]
        )
        await repo.save_plan("tsk_persist_1", plan)

        # 4. Save checkpoint
        chk = ExecutionCheckpoint(
            task_id="tsk_persist_1",
            state=TaskState.RUNNING,
            step_index=1,
            plan_snapshot=plan.model_dump(mode="json"),
            memory_snapshot={"result": 42},
        )
        await repo.save_checkpoint(chk)

        latest_chk = await repo.get_latest_checkpoint("tsk_persist_1")
        assert latest_chk is not None
        assert latest_chk.step_index == 1
        assert latest_chk.state == TaskState.RUNNING.value

    await db_mgr.drop_db()
