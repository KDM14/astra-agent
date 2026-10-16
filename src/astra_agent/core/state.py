"""State machine and core state enumerations for Astra Agent."""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Callable, List, Optional
from pydantic import BaseModel, Field


class TaskState(str, Enum):
    """Explicit lifecycle states for tasks."""
    PENDING = "PENDING"
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    RETRYING = "RETRYING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED)

    @property
    def is_active(self) -> bool:
        return not self.is_terminal


class StateTransition(BaseModel):
    """Record of a transition between states."""
    from_state: TaskState
    to_state: TaskState
    reason: Optional[str] = None
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class AstraError(Exception):
    """Base exception for all Astra Agent errors."""
    pass


class InvalidStateTransitionError(AstraError):
    """Raised when an illegal state transition is attempted."""
    def __init__(self, from_state: TaskState, to_state: TaskState, reason: Optional[str] = None):
        self.from_state = from_state
        self.to_state = to_state
        msg = f"Illegal state transition from {from_state.value} to {to_state.value}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class ExecutionTimeoutError(AstraError):
    """Raised when an operation exceeds its configured timeout."""
    pass


class ApprovalRequiredError(AstraError):
    """Raised when a sensitive tool requires human approval before proceeding."""
    pass


class SecurityViolationError(AstraError):
    """Raised when a security constraint or sandbox boundary is violated."""
    pass


class PathSecurityViolationError(SecurityViolationError):
    """Raised when a path escapes the designated workspace directory."""
    pass


class VerificationFailedError(AstraError):
    """Raised when verification criteria are not satisfied."""
    def __init__(self, criterion_name: str, message: str, details: Optional[dict] = None):
        self.criterion_name = criterion_name
        self.details = details or {}
        super().__init__(f"Verification failed for criterion '{criterion_name}': {message}")


class MaxRetriesExceededError(AstraError):
    """Raised when a task exceeds maximum permitted self-correction retries."""
    pass


# Strict legal transition map
LEGAL_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.PENDING: {TaskState.PLANNED, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.PLANNED: {TaskState.RUNNING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.RUNNING: {
        TaskState.WAITING_FOR_APPROVAL,
        TaskState.RETRYING,
        TaskState.VERIFYING,
        TaskState.COMPLETED,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.WAITING_FOR_APPROVAL: {
        TaskState.RUNNING,      # Approved
        TaskState.FAILED,       # Rejected
        TaskState.CANCELLED,
    },
    TaskState.RETRYING: {
        TaskState.RUNNING,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.VERIFYING: {
        TaskState.COMPLETED,    # Verification passed
        TaskState.RETRYING,     # Verification failed, attempt self-correction
        TaskState.FAILED,       # Verification failed, retries exhausted
        TaskState.CANCELLED,
    },
    TaskState.COMPLETED: set(),
    TaskState.FAILED: set(),
    TaskState.CANCELLED: set(),
}


class StateMachine:
    """Enforces legal state transitions and tracks lifecycle history."""

    def __init__(self, initial_state: TaskState = TaskState.PENDING):
        self._current_state = initial_state
        self._history: List[StateTransition] = []
        self._listeners: List[Callable[[StateTransition], None]] = []

    @property
    def current_state(self) -> TaskState:
        return self._current_state

    @property
    def history(self) -> List[StateTransition]:
        return list(self._history)

    def add_listener(self, listener: Callable[[StateTransition], None]) -> None:
        self._listeners.append(listener)

    def can_transition_to(self, target_state: TaskState) -> bool:
        allowed = LEGAL_TRANSITIONS.get(self._current_state, set())
        return target_state in allowed

    def transition_to(self, target_state: TaskState, reason: Optional[str] = None) -> StateTransition:
        """Transitions to the target state or raises InvalidStateTransitionError."""
        if not self.can_transition_to(target_state):
            raise InvalidStateTransitionError(self._current_state, target_state, reason)

        transition = StateTransition(
            from_state=self._current_state,
            to_state=target_state,
            reason=reason,
        )
        self._current_state = target_state
        self._history.append(transition)

        for listener in self._listeners:
            try:
                listener(transition)
            except Exception:
                # Listeners should not abort state change
                pass

        return transition
