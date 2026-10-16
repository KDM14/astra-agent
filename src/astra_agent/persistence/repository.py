"""Task and execution persistence repository."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from astra_agent.core.models import (
    AuditEvent,
    ExecutionCheckpoint,
    PlanStep,
    StepStatus,
    TaskInput,
    TaskPlan,
)
from astra_agent.core.state import TaskState
from astra_agent.persistence.models import (
    AuditRecord,
    CheckpointRecord,
    StepRecord,
    TaskRecord,
)


class TaskRepository:
    """Provides async persistence operations for Astra Agent entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_task(self, task_id: str, task_input: TaskInput) -> TaskRecord:
        record = TaskRecord(
            task_id=task_id,
            objective=task_input.objective,
            state=TaskState.PENDING.value,
            parameters_json=json.dumps(task_input.parameters),
            workspace_dir=task_input.workspace_dir,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_task(self, task_id: str) -> Optional[TaskRecord]:
        stmt = select(TaskRecord).where(TaskRecord.task_id == task_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_task_state(self, task_id: str, state: TaskState, error: Optional[str] = None) -> None:
        stmt = (
            update(TaskRecord)
            .where(TaskRecord.task_id == task_id)
            .values(state=state.value, error=error)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def save_plan(self, task_id: str, plan: TaskPlan) -> None:
        stmt = (
            update(TaskRecord)
            .where(TaskRecord.task_id == task_id)
            .values(plan_json=plan.model_dump_json())
        )
        await self.session.execute(stmt)

        # Save individual step records
        for step in plan.steps:
            step_record = StepRecord(
                step_id=step.step_id,
                task_id=task_id,
                order=step.order,
                title=step.title,
                tool_name=step.tool_name,
                arguments_json=json.dumps(step.tool_arguments),
                status=step.status.value,
            )
            self.session.add(step_record)
        await self.session.flush()

    async def update_step_status(
        self,
        step_id: str,
        status: StepStatus,
        output: Any = None,
        error: Optional[str] = None,
        duration_ms: float = 0.0,
        retry_count: int = 0,
    ) -> None:
        stmt = (
            update(StepRecord)
            .where(StepRecord.step_id == step_id)
            .values(
                status=status.value,
                output_json=json.dumps(output) if output is not None else None,
                error=error,
                duration_ms=duration_ms,
                retry_count=retry_count,
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def save_checkpoint(self, checkpoint: ExecutionCheckpoint) -> None:
        record = CheckpointRecord(
            checkpoint_id=checkpoint.checkpoint_id,
            task_id=checkpoint.task_id,
            state=checkpoint.state.value,
            step_index=checkpoint.step_index,
            plan_snapshot_json=json.dumps(checkpoint.plan_snapshot, default=str),
            memory_snapshot_json=json.dumps(checkpoint.memory_snapshot, default=str),
        )
        self.session.add(record)
        await self.session.flush()

    async def get_latest_checkpoint(self, task_id: str) -> Optional[CheckpointRecord]:
        stmt = (
            select(CheckpointRecord)
            .where(CheckpointRecord.task_id == task_id)
            .order_by(CheckpointRecord.created_at.desc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def save_audit_event(self, event: AuditEvent) -> None:
        record = AuditRecord(
            event_id=event.event_id,
            task_id=event.task_id,
            event_type=event.event_type,
            actor=event.actor,
            details_json=json.dumps(event.details),
        )
        self.session.add(record)
        await self.session.flush()
