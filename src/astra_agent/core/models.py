"""Core domain models and typed schemas for Astra Agent."""

from __future__ import annotations

import datetime
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from astra_agent.core.state import TaskState


class PermissionLevel(str, Enum):
    """Permission classification for tools."""
    READ_ONLY = "READ_ONLY"
    WORKSPACE_WRITE = "WORKSPACE_WRITE"
    SUBPROCESS_EXEC = "SUBPROCESS_EXEC"
    EXTERNAL_NETWORK = "EXTERNAL_NETWORK"
    SENSITIVE = "SENSITIVE"


class SideEffectType(str, Enum):
    """Categorization of side-effects for idempotency handling."""
    NONE = "NONE"
    FILESYSTEM = "FILESYSTEM"
    PROCESS = "PROCESS"
    NETWORK = "NETWORK"
    STATE_CHANGE = "STATE_CHANGE"


class StepStatus(str, Enum):
    """Execution status of an individual step."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    WAITING_APPROVAL = "WAITING_APPROVAL"


class PlanStep(BaseModel):
    """A discrete unit of work within a task plan."""
    step_id: str = Field(default_factory=lambda: f"stp_{uuid.uuid4().hex[:8]}")
    order: int
    title: str
    description: str
    tool_name: str
    tool_arguments: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list, description="IDs of steps that must complete first")
    status: StepStatus = Field(default=StepStatus.PENDING)
    requires_approval: bool = False
    idempotent: bool = True
    max_retries: int = 3
    retry_count: int = 0
    timeout_seconds: float = 30.0
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None


class TaskPlan(BaseModel):
    """Structured plan composed of steps organized as a DAG."""
    plan_id: str = Field(default_factory=lambda: f"pln_{uuid.uuid4().hex[:8]}")
    objective: str
    steps: List[PlanStep] = Field(default_factory=list)
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

    def get_step(self, step_id: str) -> Optional[PlanStep]:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None

    def get_executable_steps(self) -> List[PlanStep]:
        """Returns pending steps whose dependencies are all SUCCESS."""
        completed_ids = {s.step_id for s in self.steps if s.status == StepStatus.SUCCESS}
        ready = []
        for s in self.steps:
            if s.status == StepStatus.PENDING:
                if all(dep in completed_ids for dep in s.dependencies):
                    ready.append(s)
        return ready

    def is_complete(self) -> bool:
        return all(s.status in (StepStatus.SUCCESS, StepStatus.SKIPPED) for s in self.steps)

    def has_failures(self) -> bool:
        return any(s.status == StepStatus.FAILED for s in self.steps)


class VerificationCriterionType(str, Enum):
    """Types of verification criteria."""
    FILE_EXISTS = "FILE_EXISTS"
    FILE_CONTAINS = "FILE_CONTAINS"
    FILE_JSON_SCHEMA = "FILE_JSON_SCHEMA"
    TEST_SUITE_PASS = "TEST_SUITE_PASS"
    EXIT_CODE_ZERO = "EXIT_CODE_ZERO"
    NUMERIC_EQUALITY = "NUMERIC_EQUALITY"
    CUSTOM_CHECK = "CUSTOM_CHECK"


class VerificationCriterion(BaseModel):
    """A programmatic acceptance criterion for the task."""
    criterion_id: str = Field(default_factory=lambda: f"crt_{uuid.uuid4().hex[:8]}")
    name: str
    criterion_type: VerificationCriterionType
    parameters: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None


class VerificationResult(BaseModel):
    """Outcome of an independent verification check."""
    criterion_id: str
    name: str
    passed: bool
    message: str
    actual_value: Optional[Any] = None
    expected_value: Optional[Any] = None
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class ToolCall(BaseModel):
    """Invocation request for a tool."""
    call_id: str = Field(default_factory=lambda: f"call_{uuid.uuid4().hex[:8]}")
    tool_name: str
    arguments: Dict[str, Any]
    step_id: Optional[str] = None


class ToolResult(BaseModel):
    """Output from a tool execution."""
    call_id: str
    tool_name: str
    success: bool
    output: Any
    error: Optional[str] = None
    duration_ms: float = 0.0
    side_effects: List[str] = Field(default_factory=list)
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class ApprovalRequest(BaseModel):
    """Request for human approval before executing sensitive action."""
    approval_id: str = Field(default_factory=lambda: f"app_{uuid.uuid4().hex[:8]}")
    task_id: str
    step_id: str
    tool_name: str
    action_summary: str
    proposed_arguments: Dict[str, Any]
    risk_level: str = "HIGH"
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class ApprovalDecision(BaseModel):
    """Human decision responding to an ApprovalRequest."""
    approval_id: str
    approved: bool
    reviewer: str = "human_operator"
    notes: Optional[str] = None
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class ExecutionCheckpoint(BaseModel):
    """Durable snapshot of task state and memory for recovery."""
    checkpoint_id: str = Field(default_factory=lambda: f"chk_{uuid.uuid4().hex[:8]}")
    task_id: str
    state: TaskState
    step_index: int
    plan_snapshot: Dict[str, Any]
    memory_snapshot: Dict[str, Any]
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class AuditEvent(BaseModel):
    """Structured security and governance audit record."""
    event_id: str = Field(default_factory=lambda: f"aud_{uuid.uuid4().hex[:8]}")
    task_id: str
    event_type: str
    actor: str = "astra_core"
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class TaskInput(BaseModel):
    """Input payload to create a new task."""
    objective: str
    workspace_dir: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    criteria: List[VerificationCriterion] = Field(default_factory=list)
    timeout_seconds: float = 120.0
    max_steps: int = 20
    max_retries: int = 3
    auto_approve_safe: bool = True


class TaskOutput(BaseModel):
    """Evidence-based completion summary returned to caller."""
    task_id: str
    objective: str
    state: TaskState
    success: bool
    summary: str
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    verification_results: List[VerificationResult] = Field(default_factory=list)
    step_count: int
    duration_seconds: float
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    created_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None
    error: Optional[str] = None
