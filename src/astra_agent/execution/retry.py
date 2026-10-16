"""Exponential backoff with jitter for resilient execution."""

from __future__ import annotations

import random
import time


def calculate_backoff(attempt: int, base: float = 1.0, factor: float = 2.0, max_delay: float = 30.0, jitter: bool = True) -> float:
    """Calculates backoff delay in seconds with optional full jitter."""
    delay = min(base * (factor ** (attempt - 1)), max_delay)
    if jitter:
        delay = random.uniform(0.0, delay)
    return delay
