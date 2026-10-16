"""API request and response schemas."""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from astra_agent.core.models import TaskInput, TaskOutput, VerificationCriterion
from astra_agent.core.state import TaskState


class CreateTaskRequest(BaseModel):
    """Payload to submit a task."""
    objective: str = Field(..., min_length=3, description="High-level goal or task prompt.")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    workspace_dir: Optional[str] = None
    criteria: List[VerificationCriterion] = Field(default_factory=list)
    timeout_seconds: float = Field(120.0, ge=5.0, le=600.0)
    max_steps: int = Field(20, ge=1, le=50)
    max_retries: int = Field(3, ge=0, le=10)


class TaskStatusResponse(BaseModel):
    """Lightweight task status response."""
    task_id: str
    state: TaskState
    objective: str
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime] = None


class ApprovalPayload(BaseModel):
    """Payload to approve or reject a pending action."""
    approval_id: str
    approved: bool
    reviewer: str = "operator"
    notes: Optional[str] = None


class HealthResponse(BaseModel):
    """Service health response."""
    status: str = "ok"
    version: str = "0.1.0"
    provider: str
    workspace_dir: str
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
