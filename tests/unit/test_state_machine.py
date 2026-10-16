"""Unit tests for the Finite State Machine and state transitions."""

import pytest
from astra_agent.core.state import (
    InvalidStateTransitionError,
    StateMachine,
    TaskState,
)


def test_initial_state():
    sm = StateMachine()
    assert sm.current_state == TaskState.PENDING
    assert len(sm.history) == 0


def test_legal_transitions_lifecycle():
    sm = StateMachine(TaskState.PENDING)
    
    # PENDING -> PLANNED
    t1 = sm.transition_to(TaskState.PLANNED, reason="Planning started")
    assert sm.current_state == TaskState.PLANNED
    assert t1.from_state == TaskState.PENDING
    assert t1.to_state == TaskState.PLANNED

    # PLANNED -> RUNNING
    sm.transition_to(TaskState.RUNNING, reason="Executing steps")
    assert sm.current_state == TaskState.RUNNING

    # RUNNING -> WAITING_FOR_APPROVAL
    sm.transition_to(TaskState.WAITING_FOR_APPROVAL, reason="Sensitive tool reached")
    assert sm.current_state == TaskState.WAITING_FOR_APPROVAL

    # WAITING_FOR_APPROVAL -> RUNNING
    sm.transition_to(TaskState.RUNNING, reason="Human approved")
    assert sm.current_state == TaskState.RUNNING

    # RUNNING -> RETRYING
    sm.transition_to(TaskState.RETRYING, reason="Step error, backing off")
    assert sm.current_state == TaskState.RETRYING

    # RETRYING -> RUNNING
    sm.transition_to(TaskState.RUNNING, reason="Retry attempt")
    assert sm.current_state == TaskState.RUNNING

    # RUNNING -> VERIFYING
    sm.transition_to(TaskState.VERIFYING, reason="All steps done")
    assert sm.current_state == TaskState.VERIFYING

    # VERIFYING -> COMPLETED
    sm.transition_to(TaskState.COMPLETED, reason="Verification criteria met")
    assert sm.current_state == TaskState.COMPLETED
    assert sm.current_state.is_terminal is True


def test_illegal_transition_raises():
    sm = StateMachine(TaskState.PENDING)
    
    # Cannot jump directly from PENDING to COMPLETED or VERIFYING
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(TaskState.COMPLETED)

    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(TaskState.VERIFYING)


def test_terminal_state_cannot_transition():
    sm = StateMachine(TaskState.COMPLETED)
    assert sm.current_state.is_terminal is True

    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(TaskState.RUNNING)

    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(TaskState.FAILED)


def test_cancellation_from_active_state():
    sm = StateMachine(TaskState.RUNNING)
    sm.transition_to(TaskState.CANCELLED, reason="User cancelled")
    assert sm.current_state == TaskState.CANCELLED
    assert sm.current_state.is_terminal is True


def test_listener_notification():
    sm = StateMachine(TaskState.PENDING)
    events = []

    def on_transition(t):
        events.append((t.from_state, t.to_state))

    sm.add_listener(on_transition)
    sm.transition_to(TaskState.PLANNED)
    sm.transition_to(TaskState.RUNNING)

    assert len(events) == 2
    assert events[0] == (TaskState.PENDING, TaskState.PLANNED)
    assert events[1] == (TaskState.PLANNED, TaskState.RUNNING)
