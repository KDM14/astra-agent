"""Working memory for current task execution context."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from astra_agent.security.secret_redactor import REDACTION_PLACEHOLDER, SENSITIVE_KEY_REGEX, SecretRedactor


class WorkingMemory:
    """Manages immediate working variables and context for the active task."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._store: Dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        """Stores a variable in working memory after secret redaction."""
        if SENSITIVE_KEY_REGEX.match(key):
            self._store[key] = REDACTION_PLACEHOLDER
        else:
            self._store[key] = SecretRedactor.redact_data(value)

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        self._store.clear()

    def keys(self) -> List[str]:
        return list(self._store.keys())

    def snapshot(self) -> Dict[str, Any]:
        """Returns a copy of the entire working memory store."""
        return dict(self._store)
