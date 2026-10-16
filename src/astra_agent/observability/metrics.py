"""Metrics collection and aggregation for evaluation and monitoring."""

from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel, Field


class EvaluationMetrics(BaseModel):
    """Aggregate benchmark metrics."""
    total_tasks: int = 0
    passed_tasks: int = 0
    failed_tasks: int = 0
    task_success_rate: float = 0.0
    total_verification_checks: int = 0
    passed_verification_checks: int = 0
    verification_pass_rate: float = 0.0
    total_tool_calls: int = 0
    successful_tool_calls: int = 0
    tool_call_accuracy: float = 0.0
    total_retries: int = 0
    average_duration_seconds: float = 0.0
    total_tokens: int = 0
    total_estimated_cost_usd: float = 0.0
    failure_breakdown: Dict[str, int] = Field(default_factory=dict)


class MetricsCollector:
    """Collects individual task run data and produces benchmark metrics."""

    def __init__(self):
        self._records: List[Dict[str, Any]] = []

    def record_task_run(
        self,
        task_id: str,
        success: bool,
        duration_seconds: float,
        verification_results: List[Any],
        tool_results: List[Any],
        retry_count: int,
        tokens: int = 0,
        cost_usd: float = 0.0,
        failure_category: str = "NONE",
    ) -> None:
        self._records.append({
            "task_id": task_id,
            "success": success,
            "duration_seconds": duration_seconds,
            "verification_results": verification_results,
            "tool_results": tool_results,
            "retry_count": retry_count,
            "tokens": tokens,
            "cost_usd": cost_usd,
            "failure_category": failure_category,
        })

    def compute_summary(self) -> EvaluationMetrics:
        total = len(self._records)
        if total == 0:
            return EvaluationMetrics()

        passed = sum(1 for r in self._records if r["success"])
        failed = total - passed

        all_verifs = [v for r in self._records for v in r["verification_results"]]
        passed_verifs = sum(1 for v in all_verifs if getattr(v, "passed", False) or (isinstance(v, dict) and v.get("passed")))

        all_tools = [t for r in self._records for t in r["tool_results"]]
        success_tools = sum(
            1 for t in all_tools
            if getattr(t, "success", False) or (isinstance(t, dict) and (t.get("success") is True or t.get("type") in ("TOOL_OUTPUT", "VERIFICATION_RESULT")))
        )

        total_retries = sum(r["retry_count"] for r in self._records)
        avg_dur = sum(r["duration_seconds"] for r in self._records) / total
        total_tokens = sum(r["tokens"] for r in self._records)
        total_cost = sum(r["cost_usd"] for r in self._records)

        fail_breakdown: Dict[str, int] = {}
        for r in self._records:
            if not r["success"]:
                cat = r.get("failure_category", "UNKNOWN")
                fail_breakdown[cat] = fail_breakdown.get(cat, 0) + 1

        return EvaluationMetrics(
            total_tasks=total,
            passed_tasks=passed,
            failed_tasks=failed,
            task_success_rate=round((passed / total) * 100, 2),
            total_verification_checks=len(all_verifs),
            passed_verification_checks=passed_verifs,
            verification_pass_rate=round((passed_verifs / max(1, len(all_verifs))) * 100, 2),
            total_tool_calls=len(all_tools),
            successful_tool_calls=success_tools,
            tool_call_accuracy=round((success_tools / max(1, len(all_tools))) * 100, 2),
            total_retries=total_retries,
            average_duration_seconds=round(avg_dur, 3),
            total_tokens=total_tokens,
            total_estimated_cost_usd=round(total_cost, 6),
            failure_breakdown=fail_breakdown,
        )
