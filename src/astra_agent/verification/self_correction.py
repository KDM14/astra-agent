"""Self-correction and failure recovery analysis."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from astra_agent.core.models import PlanStep, VerificationResult


class FailureCategory(str, Enum):
    """Structured categories of execution and verification failure."""
    TRANSIENT_TIMEOUT = "TRANSIENT_TIMEOUT"
    ASSERTION_FAILED = "ASSERTION_FAILED"
    FILE_MISSING = "FILE_MISSING"
    SYNTAX_OR_RUNTIME_ERROR = "SYNTAX_OR_RUNTIME_ERROR"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    SECURITY_BLOCK = "SECURITY_BLOCK"
    PERMANENT_CONFIG_ERROR = "PERMANENT_CONFIG_ERROR"


class RecoveryStrategy(BaseModel):
    """Prescription for self-correction."""
    can_retry: bool
    failure_category: FailureCategory
    diagnostic_message: str
    suggested_correction: str
    new_step: Optional[PlanStep] = None


class SelfCorrectionAnalyzer:
    """Analyzes failed verification outcomes and generates corrective actions."""

    @staticmethod
    def analyze_verification_failure(
        failed_results: List[VerificationResult],
        current_retry_count: int,
        max_retries: int = 3,
    ) -> RecoveryStrategy:
        if current_retry_count >= max_retries:
            return RecoveryStrategy(
                can_retry=False,
                failure_category=FailureCategory.PERMANENT_CONFIG_ERROR,
                diagnostic_message=f"Maximum self-correction retries ({max_retries}) exhausted.",
                suggested_correction="Halt execution and report failure with diagnostics.",
            )

        failed_crit = failed_results[0]
        msg = failed_crit.message

        if "not found" in msg.lower() or "missing" in msg.lower():
            cat = FailureCategory.FILE_MISSING
            correction = f"Generate or restore the missing file: {failed_crit.name}"
        elif "timed out" in msg.lower():
            cat = FailureCategory.TRANSIENT_TIMEOUT
            correction = "Rerun operation with increased timeout or optimized parameters."
        elif "json" in msg.lower() or "schema" in msg.lower():
            cat = FailureCategory.SCHEMA_MISMATCH
            correction = f"Fix formatting to satisfy schema requirements: {msg}"
        elif "test" in msg.lower() or "failed" in msg.lower():
            cat = FailureCategory.SYNTAX_OR_RUNTIME_ERROR
            correction = f"Inspect failing test errors and patch workspace implementation: {msg}"
        else:
            cat = FailureCategory.ASSERTION_FAILED
            correction = f"Re-evaluate step outputs to satisfy assertion: {msg}"

        return RecoveryStrategy(
            can_retry=True,
            failure_category=cat,
            diagnostic_message=f"Criterion '{failed_crit.name}' failed: {msg}",
            suggested_correction=correction,
        )
