"""Integration tests for approval gates and human-in-the-loop workflows."""

import pytest
from astra_agent.core.models import PermissionLevel, PlanStep, SideEffectType
from astra_agent.core.state import ApprovalRequiredError, SecurityViolationError
from astra_agent.execution.dispatcher import StepDispatcher
from astra_agent.security.approval_manager import ApprovalManager
from astra_agent.security.audit import AuditLogger
from astra_agent.tools.base import BaseTool
from astra_agent.tools.registry import ToolRegistry
from pydantic import BaseModel


class SensitiveToolInput(BaseModel):
    action: str


class SensitiveTool(BaseTool):
    name = "sensitive_operation"
    description = "A sensitive tool requiring human approval"
    permission_level = PermissionLevel.SENSITIVE
    side_effect_type = SideEffectType.STATE_CHANGE
    input_schema = SensitiveToolInput

    def _run(self, inputs: SensitiveToolInput):
        return {"status": "executed", "action": inputs.action}


def test_sensitive_tool_requires_approval():
    registry = ToolRegistry()
    registry.register(SensitiveTool())
    approval_mgr = ApprovalManager()
    audit_logger = AuditLogger()

    dispatcher = StepDispatcher(
        tool_registry=registry,
        approval_manager=approval_mgr,
        audit_logger=audit_logger,
    )

    step = PlanStep(
        step_id="stp_sens_1",
        order=1,
        title="Deploy to production",
        description="",
        tool_name="sensitive_operation",
        tool_arguments={"action": "deploy_prod"},
        requires_approval=True,
    )

    # 1. First execution attempt raises ApprovalRequiredError
    with pytest.raises(ApprovalRequiredError) as exc_info:
        dispatcher.dispatch("tsk_sens_1", step)

    assert "Approval required" in str(exc_info.value)

    # 2. Verify pending approval exists
    pending = approval_mgr.get_pending_requests_for_task("tsk_sens_1")
    assert len(pending) == 1
    req = pending[0]
    assert req.tool_name == "sensitive_operation"

    # 3. Approve action
    approval_mgr.record_decision(req.approval_id, approved=True, reviewer="security_lead")

    # 4. Dispatch again - now it executes successfully!
    res = dispatcher.dispatch("tsk_sens_1", step)
    assert res.success is True
    assert res.output["status"] == "executed"


def test_rejected_action_raises_security_violation():
    registry = ToolRegistry()
    registry.register(SensitiveTool())
    approval_mgr = ApprovalManager()
    audit_logger = AuditLogger()

    dispatcher = StepDispatcher(
        tool_registry=registry,
        approval_manager=approval_mgr,
        audit_logger=audit_logger,
    )

    step = PlanStep(
        step_id="stp_sens_2",
        order=1,
        title="Delete production db",
        description="",
        tool_name="sensitive_operation",
        tool_arguments={"action": "drop_database"},
        requires_approval=True,
    )

    with pytest.raises(ApprovalRequiredError):
        dispatcher.dispatch("tsk_sens_2", step)

    pending = approval_mgr.get_pending_requests_for_task("tsk_sens_2")
    approval_mgr.record_decision(pending[0].approval_id, approved=False, reviewer="security_lead")

    # Dispatch after rejection raises SecurityViolationError
    with pytest.raises(SecurityViolationError, match="rejected"):
        dispatcher.dispatch("tsk_sens_2", step)
