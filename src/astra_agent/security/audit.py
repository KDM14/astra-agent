"""Security audit logging subsystem."""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from astra_agent.core.models import AuditEvent

logger = logging.getLogger("astra_agent.audit")


class AuditLogger:
    """Records security and compliance events."""

    def __init__(self, log_file: Optional[Path | str] = None):
        self.log_file = Path(log_file) if log_file else None
        self._events: List[AuditEvent] = []

    def record(
        self,
        task_id: str,
        event_type: str,
        actor: str = "astra_system",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            task_id=task_id,
            event_type=event_type,
            actor=actor,
            details=details or {},
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        self._events.append(event)

        logger.info(
            f"[AUDIT] task={task_id} event={event_type} actor={actor} details={event.details}"
        )

        if self.log_file:
            try:
                self.log_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(event.model_dump_json() + "\n")
            except Exception as e:
                logger.error(f"Failed to write audit event to file: {e}")

        return event

    def get_events_for_task(self, task_id: str) -> List[AuditEvent]:
        return [e for e in self._events if e.task_id == task_id]

    def all_events(self) -> List[AuditEvent]:
        return list(self._events)
