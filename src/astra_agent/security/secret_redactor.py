"""Secret redaction and data sanitization for Astra Agent."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Union

# Common high-entropy and API key patterns
SECRET_PATTERNS = [
    re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|auth[_-]?token|bearer|secret)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{16,})['\"]?"),
    re.compile(r"sk-(?:proj-)?[a-zA-Z0-9_\-]{20,}"),              # OpenAI
    re.compile(r"sk-ant-[a-zA-Z0-9_\-]{20,}"),                   # Anthropic
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),                          # GitHub Personal Token
    re.compile(r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}"),   # GitHub Fine-grained PAT
    re.compile(r"AKIA[0-9A-Z]{16}"),                             # AWS Access Key
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----"), # Private keys
]

REDACTION_PLACEHOLDER = "[REDACTED_SECRET]"
SENSITIVE_KEY_REGEX = re.compile(r"(?i)^(api[_-]?key|auth[_-]?token|secret|password|access[_-]?token)$")


class SecretRedactor:
    """Scans text and nested data structures to mask credentials."""

    @classmethod
    def redact_text(cls, text: str) -> str:
        if not text or not isinstance(text, str):
            return text
        
        redacted = text
        for pattern in SECRET_PATTERNS:
            redacted = pattern.sub(REDACTION_PLACEHOLDER, redacted)
        return redacted

    @classmethod
    def redact_data(cls, data: Any) -> Any:
        """Recursively redacts secrets in dicts, lists, strings, and primitives."""
        if isinstance(data, str):
            return cls.redact_text(data)
        elif isinstance(data, dict):
            new_dict = {}
            for k, v in data.items():
                if SENSITIVE_KEY_REGEX.match(k):
                    new_dict[k] = REDACTION_PLACEHOLDER
                else:
                    new_dict[k] = cls.redact_data(v)
            return new_dict
        elif isinstance(data, list):
            return [cls.redact_data(item) for item in data]
        elif isinstance(data, tuple):
            return tuple(cls.redact_data(item) for item in data)
        return data
