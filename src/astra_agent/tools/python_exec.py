"""Approved sandboxed Python execution tool."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from astra_agent.core.models import PermissionLevel, SideEffectType
from astra_agent.security.path_validator import PathValidator
from astra_agent.security.sandbox import SubprocessSandbox
from astra_agent.tools.base import BaseTool


class PythonExecInput(BaseModel):
    """Input parameters for Python execution."""
    code: Optional[str] = Field(None, description="Inline Python code to execute.")
    script_path: Optional[str] = Field(None, description="Path to Python script in workspace to execute.")
    arguments: List[str] = Field(default_factory=list, description="Command line arguments to pass to the script.")
    timeout_seconds: float = Field(30.0, ge=1.0, le=120.0, description="Execution timeout in seconds.")


class PythonExecTool(BaseTool):
    """Executes Python code or scripts safely inside the workspace sandbox."""

    name = "python_exec"
    description = "Executes Python code safely within the workspace sandbox with resource limits."
    permission_level = PermissionLevel.SUBPROCESS_EXEC
    side_effect_type = SideEffectType.PROCESS
    idempotent = False
    default_timeout = 30.0
    input_schema = PythonExecInput

    def _run(self, inputs: PythonExecInput) -> Dict[str, Any]:
        if not self.workspace_dir:
            raise ValueError("Workspace directory is not configured for python_exec.")

        ws = Path(self.workspace_dir).resolve()
        sandbox = SubprocessSandbox(workspace_dir=ws, default_timeout=inputs.timeout_seconds)

        if inputs.code and inputs.script_path:
            raise ValueError("Provide either 'code' or 'script_path', not both.")

        if not inputs.code and not inputs.script_path:
            raise ValueError("Must provide either 'code' or 'script_path'.")

        temp_created = False
        target_script = None

        try:
            if inputs.code:
                # Write inline code to a temporary script within workspace
                with tempfile.NamedTemporaryFile("w", suffix=".py", dir=str(ws), delete=False, encoding="utf-8") as tf:
                    tf.write(inputs.code)
                    target_script = Path(tf.name)
                temp_created = True
            else:
                target_script = PathValidator.resolve_safe_path(ws, inputs.script_path)
                if not target_script.is_file():
                    raise FileNotFoundError(f"Script file not found: {inputs.script_path}")

            cmd = ["python3", str(target_script.relative_to(ws))] + inputs.arguments
            res = sandbox.run(cmd, timeout=inputs.timeout_seconds)

            return {
                "exit_code": res.exit_code,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "duration_ms": res.duration_ms,
                "timed_out": res.timed_out,
                "success": (res.exit_code == 0 and not res.timed_out),
            }

        finally:
            if temp_created and target_script and target_script.exists():
                try:
                    target_script.unlink()
                except Exception:
                    pass
