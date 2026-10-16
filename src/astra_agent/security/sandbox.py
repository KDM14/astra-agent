"""Isolated subprocess execution sandbox with strict resource limits."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from astra_agent.core.state import ExecutionTimeoutError, SecurityViolationError
from astra_agent.security.path_validator import PathValidator


class SandboxExecutionResult(BaseModel):
    """Output from a sandboxed command execution."""
    command: List[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False


class SubprocessSandbox:
    """Executes safe commands within a restricted workspace boundary."""

    # Default dangerous environment variables stripped from child process
    STRIP_ENV_VARS = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "GITHUB_TOKEN",
        "SLACK_BOT_TOKEN",
    ]

    def __init__(
        self,
        workspace_dir: str | Path,
        allowed_executables: Optional[List[str]] = None,
        default_timeout: float = 30.0,
        max_output_bytes: int = 100 * 1024,  # 100 KB
    ):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.allowed_executables = set(allowed_executables or [
            "python", "python3", "pytest", "cat", "ls", "grep", "echo", "diff"
        ])
        self.default_timeout = default_timeout
        self.max_output_bytes = max_output_bytes

    def _sanitize_env(self, custom_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Creates a sanitized environment copy stripped of sensitive credentials."""
        clean_env = dict(os.environ)
        for var in self.STRIP_ENV_VARS:
            clean_env.pop(var, None)

        if custom_env:
            clean_env.update(custom_env)

        # Force unbuffered python output
        clean_env["PYTHONUNBUFFERED"] = "1"
        return clean_env

    def run(
        self,
        command: List[str],
        timeout: Optional[float] = None,
        env: Optional[Dict[str, str]] = None,
        stdin_input: Optional[str] = None,
    ) -> SandboxExecutionResult:
        """Executes a command safely inside the workspace.

        Args:
            command: Command tokens list (e.g. ["python3", "script.py"]).
            timeout: Maximum allowed execution time in seconds.
            env: Optional additional environment variables.
            stdin_input: Optional standard input data.

        Returns:
            SandboxExecutionResult containing outputs and exit status.

        Raises:
            SecurityViolationError: If command executable is not permitted.
            ExecutionTimeoutError: If execution exceeds timeout limit.
        """
        if not command:
            raise ValueError("Command cannot be empty.")

        executable = Path(command[0]).name
        if executable not in self.allowed_executables:
            raise SecurityViolationError(
                f"Executable '{executable}' is not in the sandbox whitelist: {sorted(self.allowed_executables)}"
            )

        actual_timeout = timeout if timeout is not None else self.default_timeout
        clean_env = self._sanitize_env(env)

        start_time = time.perf_counter()
        try:
            process = subprocess.run(
                command,
                cwd=str(self.workspace_dir),
                capture_output=True,
                text=True,
                timeout=actual_timeout,
                env=clean_env,
                input=stdin_input,
                shell=False,  # strictly prevent shell injection
            )
            duration = (time.perf_counter() - start_time) * 1000.0

            # Cap outputs to max_output_bytes
            stdout = process.stdout[:self.max_output_bytes]
            stderr = process.stderr[:self.max_output_bytes]

            return SandboxExecutionResult(
                command=command,
                exit_code=process.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_ms=round(duration, 2),
                timed_out=False,
            )

        except subprocess.TimeoutExpired as exc:
            duration = (time.perf_counter() - start_time) * 1000.0
            stdout_str = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr_str = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            return SandboxExecutionResult(
                command=command,
                exit_code=-1,
                stdout=stdout_str[:self.max_output_bytes],
                stderr=f"Process timed out after {actual_timeout}s\n" + stderr_str[:self.max_output_bytes],
                duration_ms=round(duration, 2),
                timed_out=True,
            )
