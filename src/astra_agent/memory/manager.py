"""Unified memory manager combining working, task, and semantic memory."""

from __future__ import annotations

from typing import Any, Dict, Optional
from astra_agent.memory.models import MemoryCategory, MemoryEntry
from astra_agent.memory.working_memory import WorkingMemory
from astra_agent.memory.task_memory import PersistentTaskMemory
from astra_agent.memory.semantic_memory import SemanticMemory


class MemoryManager:
    """Orchestrates all memory tiers for a task."""

    def __init__(self, task_id: str, semantic_memory: Optional[SemanticMemory] = None):
        self.task_id = task_id
        self.working = WorkingMemory(task_id=task_id)
        self.task = PersistentTaskMemory(task_id=task_id)
        self.semantic = semantic_memory or SemanticMemory()

    def snapshot(self) -> Dict[str, Any]:
        """Provides a complete serializable snapshot of memory state."""
        return {
            "task_id": self.task_id,
            "working_memory": self.working.snapshot(),
            "events_count": len(self.task.get_events()),
            "evidence_count": len(self.task.get_evidence()),
        }
