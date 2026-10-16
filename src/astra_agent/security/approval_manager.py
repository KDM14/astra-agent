"""Approval manager for human-in-the-loop governance."""

from __future__ import annotations

import datetime
from typing import Dict, List, Optional
from astra_agent.core.models import ApprovalDecision, ApprovalRequest


class ApprovalManager:
    """Tracks and evaluates human approval requests."""

    def __init__(self):
        self._requests: Dict[str, ApprovalRequest] = {}
        self._decisions: Dict[str, ApprovalDecision] = {}

    def create_request(
        self,
        task_id: str,
        step_id: str,
        tool_name: str,
        action_summary: str,
        proposed_arguments: Dict,
        risk_level: str = "HIGH",
    ) -> ApprovalRequest:
        req = ApprovalRequest(
            task_id=task_id,
            step_id=step_id,
            tool_name=tool_name,
            action_summary=action_summary,
            proposed_arguments=proposed_arguments,
            risk_level=risk_level,
        )
        self._requests[req.approval_id] = req
        return req

    def get_request(self, approval_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(approval_id)

    def get_requests_for_step(self, task_id: str, step_id: str) -> List[ApprovalRequest]:
        return [
            req for req in self._requests.values()
            if req.task_id == task_id and req.step_id == step_id
        ]

    def get_pending_requests_for_task(self, task_id: str) -> List[ApprovalRequest]:
        return [
            req for req in self._requests.values()
            if req.task_id == task_id and req.approval_id not in self._decisions
        ]

    def record_decision(
        self,
        approval_id: str,
        approved: bool,
        reviewer: str = "human_operator",
        notes: Optional[str] = None,
    ) -> ApprovalDecision:
        if approval_id not in self._requests:
            raise ValueError(f"Approval request '{approval_id}' does not exist.")

        decision = ApprovalDecision(
            approval_id=approval_id,
            approved=approved,
            reviewer=reviewer,
            notes=notes,
        )
        self._decisions[approval_id] = decision
        return decision

    def is_approved(self, approval_id: str) -> bool:
        decision = self._decisions.get(approval_id)
        return decision.approved if decision else False

    def is_rejected(self, approval_id: str) -> bool:
        decision = self._decisions.get(approval_id)
        return (not decision.approved) if decision else False
