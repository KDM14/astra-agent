"""Task-state and memory inspection tool."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional
from pydantic import BaseModel, Field

from astra_agent.core.models import PermissionLevel, SideEffectType
from astra_agent.tools.base import BaseTool


class StateInspectInput(BaseModel):
    """Input parameters for task state inspection."""
    include_memory: bool = Field(True, description="Whether to include current working memory keys.")
    include_steps: bool = Field(True, description="Whether to include history of completed plan steps.")
    step_id: Optional[str] = Field(None, description="Optional specific step ID to inspect.")


class StateInspectTool(BaseTool):
    """Allows the agent to inspect current task state, plan progress, and memory."""

    name = "state_inspect"
    description = "Inspects current task execution progress, step outputs, and working memory state."
    permission_level = PermissionLevel.READ_ONLY
    side_effect_type = SideEffectType.NONE
    idempotent = True
    input_schema = StateInspectInput

    def __init__(self, workspace_dir: Optional[str] = None, state_provider: Optional[Callable[[], Dict[str, Any]]] = None):
        super().__init__(workspace_dir=workspace_dir)
        self.state_provider = state_provider

    def _run(self, inputs: StateInspectInput) -> Dict[str, Any]:
        if not self.state_provider:
            return {
                "message": "Task state inspection context is not connected.",
                "available": False,
            }

        full_state = self.state_provider()
        output: Dict[str, Any] = {
            "task_id": full_state.get("task_id"),
            "current_state": full_state.get("current_state"),
        }

        if inputs.include_memory:
            output["working_memory"] = full_state.get("working_memory", {})

        if inputs.include_steps:
            steps = full_state.get("steps", [])
            if inputs.step_id:
                output["step"] = next((s for s in steps if s.get("step_id") == inputs.step_id), None)
            else:
                output["steps_summary"] = [
                    {"step_id": s.get("step_id"), "title": s.get("title"), "status": s.get("status")}
                    for s in steps
                ]

        return output
