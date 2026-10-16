"""Workspace-restricted test runner tool."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from astra_agent.core.models import PermissionLevel, SideEffectType
from astra_agent.security.path_validator import PathValidator
from astra_agent.security.sandbox import SubprocessSandbox
from astra_agent.tools.base import BaseTool


class TestRunnerInput(BaseModel):
    """Input parameters for running workspace tests."""
    test_path: Optional[str] = Field("tests", description="Test directory or file path relative to workspace.")
    filter_expression: Optional[str] = Field(None, description="Pytest -k expression to filter tests by name.")
    timeout_seconds: float = Field(45.0, ge=5.0, le=180.0, description="Maximum test run duration.")


class TestRunnerTool(BaseTool):
    """Runs automated tests strictly within the designated workspace boundary."""

    __test__ = False
    name = "test_runner"
    description = "Executes pytest automated test suites within the workspace sandbox and returns structured results."
    permission_level = PermissionLevel.SUBPROCESS_EXEC
    side_effect_type = SideEffectType.PROCESS
    idempotent = True
    default_timeout = 45.0
    input_schema = TestRunnerInput

    def _parse_pytest_summary(self, stdout: str) -> Dict[str, Any]:
        """Extracts passed, failed, and skipped counts from pytest output."""
        summary: Dict[str, Any] = {
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "total": 0,
        }

        # Match e.g. "5 passed, 2 failed in 0.12s"
        last_line_match = re.search(r"=+\s*(.*?)\s+in\s+[\d\.]+s\s*=+", stdout)
        if last_line_match:
            parts = last_line_match.group(1).split(",")
            for part in parts:
                part = part.strip()
                if "passed" in part:
                    summary["passed"] = int(re.search(r"(\d+)\s+passed", part).group(1))
                elif "failed" in part:
                    summary["failed"] = int(re.search(r"(\d+)\s+failed", part).group(1))
                elif "error" in part:
                    summary["errors"] = int(re.search(r"(\d+)\s+error", part).group(1))
                elif "skipped" in part:
                    summary["skipped"] = int(re.search(r"(\d+)\s+skipped", part).group(1))

            summary["total"] = summary["passed"] + summary["failed"] + summary["errors"] + summary["skipped"]

        return summary

    def _run(self, inputs: TestRunnerInput) -> Dict[str, Any]:
        if not self.workspace_dir:
            raise ValueError("Workspace directory is not configured for test_runner.")

        ws = Path(self.workspace_dir).resolve()
        sandbox = SubprocessSandbox(workspace_dir=ws, default_timeout=inputs.timeout_seconds)

        cmd = ["pytest", "-v"]
        if inputs.filter_expression:
            cmd.extend(["-k", inputs.filter_expression])

        if inputs.test_path:
            target_path = PathValidator.resolve_safe_path(ws, inputs.test_path)
            if target_path.exists():
                cmd.append(str(target_path.relative_to(ws)))
            else:
                cmd.append(inputs.test_path)

        res = sandbox.run(cmd, timeout=inputs.timeout_seconds)
        summary = self._parse_pytest_summary(res.stdout)

        all_passed = (res.exit_code == 0) and (summary["failed"] == 0) and (summary["errors"] == 0)

        return {
            "all_passed": all_passed,
            "exit_code": res.exit_code,
            "summary": summary,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "duration_ms": res.duration_ms,
            "timed_out": res.timed_out,
        }
