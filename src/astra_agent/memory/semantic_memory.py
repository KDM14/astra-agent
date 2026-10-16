"""Long-term semantic memory with provenance and relevance retrieval."""

from __future__ import annotations

import datetime
import math
import re
from typing import Any, Dict, List, Optional
from astra_agent.memory.models import MemoryCategory, MemoryEntry
from astra_agent.security.secret_redactor import SecretRedactor


class SemanticMemory:
    """Stores cross-task verified knowledge and searchable facts."""

    def __init__(self, max_entries: int = 1000):
        self._entries: Dict[str, MemoryEntry] = {}
        self.max_entries = max_entries

    def store(
        self,
        task_id: str,
        category: MemoryCategory,
        key: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
    ) -> MemoryEntry:
        # Enforce confidence policy: hypotheses default to 0.5, facts to 1.0
        if confidence is None:
            confidence = 0.5 if category == MemoryCategory.MODEL_HYPOTHESIS else 1.0

        clean_content = SecretRedactor.redact_text(content)
        clean_metadata = SecretRedactor.redact_data(metadata or {})

        # Check if entry with this key exists; if so, update
        existing = next((e for e in self._entries.values() if e.key == key and e.task_id == task_id), None)
        if existing:
            existing.content = clean_content
            existing.metadata = clean_metadata
            existing.confidence = confidence
            existing.updated_at = datetime.datetime.now(datetime.timezone.utc)
            return existing

        # Prune oldest if at capacity
        if len(self._entries) >= self.max_entries:
            oldest_id = min(self._entries.keys(), key=lambda k: self._entries[k].created_at)
            del self._entries[oldest_id]

        entry = MemoryEntry(
            task_id=task_id,
            category=category,
            key=key,
            content=clean_content,
            metadata=clean_metadata,
            confidence=confidence,
        )
        self._entries[entry.entry_id] = entry
        return entry

    def retrieve(self, query: str, top_k: int = 5, min_confidence: float = 0.0) -> List[MemoryEntry]:
        """Retrieves entries matching query tokens scored by lexical overlap and confidence."""
        query_tokens = set(re.findall(r"\w+", query.lower()))
        if not query_tokens:
            return []

        scored_entries = []
        for entry in self._entries.values():
            if entry.confidence < min_confidence:
                continue

            content_tokens = re.findall(r"\w+", (entry.key + " " + entry.content).lower())
            if not content_tokens:
                continue

            overlap = [t for t in content_tokens if t in query_tokens]
            if not overlap:
                continue

            score = (len(set(overlap)) / len(query_tokens)) * (1.0 + math.log(1 + len(overlap))) * entry.confidence
            scored_entries.append((score, entry))

        scored_entries.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored_entries[:top_k]]

    def delete(self, entry_id: str) -> bool:
        if entry_id in self._entries:
            del self._entries[entry_id]
            return True
        return False

    def clear(self) -> None:
        self._entries.clear()

    def count(self) -> int:
        return len(self._entries)
