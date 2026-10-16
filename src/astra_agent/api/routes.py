"""FastAPI route handlers for Astra Agent."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from astra_agent.api.auth import verify_api_key
from astra_agent.api.schemas import (
    ApprovalPayload,
    CreateTaskRequest,
    HealthResponse,
    TaskStatusResponse,
)
from astra_agent.core.config import settings
from astra_agent.core.models import TaskInput, TaskOutput
from astra_agent.core.state import TaskState
from astra_agent.execution.orchestrator import AstraOrchestrator
from astra_agent.providers.factory import get_provider

router = APIRouter(prefix="/api/v1")

# Global orchestrator instance for API service
_orchestrator: Optional[AstraOrchestrator] = None


def get_orchestrator() -> AstraOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        provider = get_provider()
        _orchestrator = AstraOrchestrator(provider=provider)
    return _orchestrator


def set_orchestrator(orchestrator: AstraOrchestrator) -> None:
    global _orchestrator
    _orchestrator = orchestrator


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    orch = get_orchestrator()
    return HealthResponse(
        status="ok",
        version="0.1.0",
        provider=orch.provider.name,
        workspace_dir=orch.workspace_dir,
    )


@router.post("/tasks", response_model=TaskOutput, dependencies=[Depends(verify_api_key)])
async def create_and_execute_task(req: CreateTaskRequest) -> TaskOutput:
    orch = get_orchestrator()
    task_input = TaskInput(
        objective=req.objective,
        parameters=req.parameters,
        workspace_dir=req.workspace_dir or orch.workspace_dir,
        criteria=req.criteria,
        timeout_seconds=req.timeout_seconds,
        max_steps=req.max_steps,
        max_retries=req.max_retries,
    )

    result = await orch.execute_task(task_input)
    return result


@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse, dependencies=[Depends(verify_api_key)])
async def get_task_status(task_id: str) -> TaskStatusResponse:
    orch = get_orchestrator()
    ctx = orch.get_task_context(task_id)
    if not ctx:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    sm = ctx["state_machine"]
    return TaskStatusResponse(
        task_id=task_id,
        state=sm.current_state,
        objective=ctx["input"].objective,
        created_at=ctx["created_at"],
    )


@router.get("/tasks/{task_id}", dependencies=[Depends(verify_api_key)])
async def get_task_details(task_id: str) -> Dict[str, Any]:
    orch = get_orchestrator()
    ctx = orch.get_task_context(task_id)
    if not ctx:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    sm = ctx["state_machine"]
    plan = ctx.get("plan")
    memory = ctx["memory"]

    return {
        "task_id": task_id,
        "objective": ctx["input"].objective,
        "state": sm.current_state.value,
        "plan": plan.model_dump() if plan else None,
        "working_memory": memory.working.snapshot(),
        "created_at": ctx["created_at"].isoformat(),
        "retry_count": ctx.get("retry_count", 0),
    }


@router.get("/tasks/{task_id}/history", dependencies=[Depends(verify_api_key)])
async def get_task_history(task_id: str) -> Dict[str, Any]:
    orch = get_orchestrator()
    ctx = orch.get_task_context(task_id)
    if not ctx:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    memory = ctx["memory"]
    events = [e.model_dump() for e in memory.task.get_events()]
    evidence = memory.task.get_evidence()

    return {
        "task_id": task_id,
        "events_count": len(events),
        "events": events,
        "evidence": evidence,
    }


@router.post("/tasks/{task_id}/approve", response_model=TaskOutput, dependencies=[Depends(verify_api_key)])
async def approve_task_action(task_id: str, payload: ApprovalPayload) -> TaskOutput:
    orch = get_orchestrator()
    try:
        output = await orch.approve_and_resume(
            task_id=task_id,
            approval_id=payload.approval_id,
            approved=payload.approved,
            reviewer=payload.reviewer,
        )
        return output
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/cancel", dependencies=[Depends(verify_api_key)])
async def cancel_task(task_id: str, reason: str = "User cancelled") -> Dict[str, Any]:
    orch = get_orchestrator()
    success = await orch.cancel_task(task_id, reason=reason)
    if not success:
        raise HTTPException(status_code=400, detail=f"Cannot cancel task '{task_id}' (already terminal or not found).")
    return {"task_id": task_id, "status": "CANCELLED", "reason": reason}


@router.get("/tasks/{task_id}/result", response_model=TaskOutput, dependencies=[Depends(verify_api_key)])
async def get_task_result(task_id: str) -> TaskOutput:
    orch = get_orchestrator()
    ctx = orch.get_task_context(task_id)
    if not ctx:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    sm = ctx["state_machine"]
    if sm.current_state.is_active:
        raise HTTPException(status_code=400, detail=f"Task '{task_id}' is still in progress (state: {sm.current_state.value}).")

    # Output is reconstructed or fetched
    return orch._build_output(
        context=ctx,
        success=(sm.current_state == TaskState.COMPLETED),
        summary=f"Task finished with state: {sm.current_state.value}",
        start_time_perf=0.0,
    )
