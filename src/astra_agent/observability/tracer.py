"""Execution tracing and span management."""

from __future__ import annotations

import datetime
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Span(BaseModel):
    """An individual execution trace span."""
    span_id: str
    name: str
    task_id: str
    parent_span_id: Optional[str] = None
    started_at: datetime.datetime
    ended_at: Optional[datetime.datetime] = None
    duration_ms: float = 0.0
    attributes: Dict[str, Any] = Field(default_factory=dict)
    status: str = "OK"  # "OK" or "ERROR"


class Tracer:
    """Collects and aggregates performance spans for execution observability."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._spans: List[Span] = []
        self._active_spans: Dict[str, float] = {}

    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None, parent_span_id: Optional[str] = None) -> str:
        span_id = f"spn_{len(self._spans)+1}_{name}"
        self._active_spans[span_id] = time.perf_counter()
        span = Span(
            span_id=span_id,
            name=name,
            task_id=self.task_id,
            parent_span_id=parent_span_id,
            started_at=datetime.datetime.now(datetime.timezone.utc),
            attributes=attributes or {},
        )
        self._spans.append(span)
        return span_id

    def end_span(self, span_id: str, status: str = "OK", error: Optional[str] = None) -> None:
        start_time = self._active_spans.pop(span_id, None)
        duration_ms = (time.perf_counter() - start_time) * 1000.0 if start_time else 0.0

        for s in self._spans:
            if s.span_id == span_id:
                s.ended_at = datetime.datetime.now(datetime.timezone.utc)
                s.duration_ms = round(duration_ms, 2)
                s.status = status
                if error:
                    s.attributes["error"] = error
                break

    def get_spans(self) -> List[Span]:
        return list(self._spans)

    def total_duration_ms(self) -> float:
        return sum(s.duration_ms for s in self._spans)
