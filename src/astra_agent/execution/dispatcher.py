"""Step execution dispatcher with security and approval enforcement."""

from __future__ import annotations

import datetime
from typing import Any, Dict, Optional
from astra_agent.core.models import (
    ApprovalRequest,
    PermissionLevel,
    PlanStep,
    StepStatus,
    ToolResult,
)
from astra_agent.core.state import ApprovalRequiredError, AstraError, SecurityViolationError
from astra_agent.security.approval_manager import ApprovalManager
from astra_agent.security.audit import AuditLogger
from astra_agent.tools.registry import ToolRegistry


class StepDispatcher:
    """Dispatches plan steps to registered tools with security controls."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        approval_manager: ApprovalManager,
        audit_logger: AuditLogger,
    ):
        self.tool_registry = tool_registry
        self.approval_manager = approval_manager
        self.audit_logger = audit_logger

    def dispatch(
        self,
        task_id: str,
        step: PlanStep,
        auto_approve_safe: bool = True,
    ) -> ToolResult:
        """Executes a single plan step."""
        tool = self.tool_registry.get(step.tool_name)
        if not tool:
            err_msg = f"Tool '{step.tool_name}' not registered."
            self.audit_logger.record(
                task_id=task_id,
                event_type="TOOL_NOT_FOUND",
                details={"tool_name": step.tool_name, "step_id": step.step_id},
            )
            return ToolResult(
                call_id=f"call_err_{step.step_id}",
                tool_name=step.tool_name,
                success=False,
                output=None,
                error=err_msg,
            )

        # Check permissions & approval requirements
        if tool.permission_level in (PermissionLevel.SENSITIVE, PermissionLevel.EXTERNAL_NETWORK):
            # Check if any request exists for this step
            step_requests = self.approval_manager.get_requests_for_step(task_id, step.step_id)

            if not step_requests:
                # Create approval request
                req = self.approval_manager.create_request(
                    task_id=task_id,
                    step_id=step.step_id,
                    tool_name=step.tool_name,
                    action_summary=f"Execute {step.tool_name}: {step.title}",
                    proposed_arguments=step.tool_arguments,
                    risk_level="HIGH" if tool.permission_level == PermissionLevel.SENSITIVE else "MEDIUM",
                )
                self.audit_logger.record(
                    task_id=task_id,
                    event_type="APPROVAL_REQUIRED",
                    details={"approval_id": req.approval_id, "tool_name": step.tool_name, "step_id": step.step_id},
                )
                raise ApprovalRequiredError(f"Approval required for sensitive tool '{step.tool_name}' (approval_id: {req.approval_id})")

            # Check decision on existing request
            existing_req = step_requests[-1]
            if not self.approval_manager.is_approved(existing_req.approval_id):
                if self.approval_manager.is_rejected(existing_req.approval_id):
                    raise SecurityViolationError(f"Action '{step.tool_name}' was rejected by human operator.")
                raise ApprovalRequiredError(f"Approval still pending for '{step.tool_name}' (approval_id: {existing_req.approval_id})")

        # Execute tool
        self.audit_logger.record(
            task_id=task_id,
            event_type="TOOL_DISPATCH",
            details={"tool_name": step.tool_name, "step_id": step.step_id, "arguments": step.tool_arguments},
        )

        res = tool.run(arguments=step.tool_arguments, call_id=f"call_{step.step_id}")
        return res
