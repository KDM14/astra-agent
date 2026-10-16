"""Persistent task memory capturing chronological history and execution evidence."""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from astra_agent.core.models import ToolResult, VerificationResult
from astra_agent.security.secret_redactor import SecretRedactor


class TaskHistoryEvent(BaseModel):
    """An event in the task's execution lifecycle."""
    event_id: str
    event_type: str  # "STEP_START", "TOOL_EXEC", "APPROVAL", "VERIFICATION", "STEP_FINISH"
    step_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class PersistentTaskMemory:
    """Retains full execution history and verifiable evidence for a single task."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._events: List[TaskHistoryEvent] = []
        self._evidence: List[Dict[str, Any]] = []

    def log_event(self, event_type: str, step_id: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> TaskHistoryEvent:
        clean_data = SecretRedactor.redact_data(data or {})
        event = TaskHistoryEvent(
            event_id=f"evt_{len(self._events)+1}",
            event_type=event_type,
            step_id=step_id,
            data=clean_data,
        )
        self._events.append(event)
        return event

    def record_tool_result(self, step_id: str, tool_result: ToolResult) -> None:
        self.log_event(
            event_type="TOOL_EXEC",
            step_id=step_id,
            data={
                "tool_name": tool_result.tool_name,
                "success": tool_result.success,
                "output": tool_result.output,
                "error": tool_result.error,
                "duration_ms": tool_result.duration_ms,
            }
        )
        if tool_result.success:
            self.add_evidence(
                evidence_type="TOOL_OUTPUT",
                source=tool_result.tool_name,
                content=tool_result.output,
                step_id=step_id,
            )

    def add_evidence(self, evidence_type: str, source: str, content: Any, step_id: Optional[str] = None) -> None:
        self._evidence.append({
            "type": evidence_type,
            "source": source,
            "content": SecretRedactor.redact_data(content),
            "step_id": step_id,
            "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

    def record_verification(self, verification_result: VerificationResult) -> None:
        self.log_event(
            event_type="VERIFICATION",
            data={
                "criterion_id": verification_result.criterion_id,
                "name": verification_result.name,
                "passed": verification_result.passed,
                "message": verification_result.message,
            }
        )
        self.add_evidence(
            evidence_type="VERIFICATION_RESULT",
            source=verification_result.name,
            content={
                "passed": verification_result.passed,
                "message": verification_result.message,
                "actual": verification_result.actual_value,
            }
        )

    def get_events(self) -> List[TaskHistoryEvent]:
        return list(self._events)

    def get_evidence(self) -> List[Dict[str, Any]]:
        return list(self._evidence)
