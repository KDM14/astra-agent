"""Path-restricted local file reader tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from astra_agent.core.models import PermissionLevel, SideEffectType
from astra_agent.security.path_validator import PathValidator
from astra_agent.tools.base import BaseTool


class FileReaderInput(BaseModel):
    """Input parameters for reading a file."""
    path: str = Field(..., description="Path to the file relative to the workspace.")
    start_line: Optional[int] = Field(None, ge=1, description="Optional starting line number (1-based, inclusive).")
    end_line: Optional[int] = Field(None, ge=1, description="Optional ending line number (1-based, inclusive).")
    encoding: str = Field("utf-8", description="Character encoding of the file.")


class FileReaderTool(BaseTool):
    """Reads file content safely from within the workspace jail."""

    name = "file_reader"
    description = "Reads content from a file within the designated workspace boundary."
    permission_level = PermissionLevel.READ_ONLY
    side_effect_type = SideEffectType.NONE
    idempotent = True
    input_schema = FileReaderInput

    MAX_BYTES = 5 * 1024 * 1024  # 5 MB

    def _run(self, inputs: FileReaderInput) -> Dict[str, Any]:
        if not self.workspace_dir:
            raise ValueError("Workspace directory is not configured for file_reader.")

        safe_path = PathValidator.resolve_safe_path(self.workspace_dir, inputs.path)
        if not safe_path.is_file():
            raise FileNotFoundError(f"File not found: {inputs.path}")

        file_size = safe_path.stat().st_size
        if file_size > self.MAX_BYTES:
            raise ValueError(f"File size ({file_size} bytes) exceeds limit of {self.MAX_BYTES} bytes.")

        content = safe_path.read_text(encoding=inputs.encoding)
        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        if inputs.start_line is not None or inputs.end_line is not None:
            start_idx = (inputs.start_line - 1) if inputs.start_line else 0
            end_idx = inputs.end_line if inputs.end_line else total_lines
            selected_lines = lines[start_idx:end_idx]
            returned_content = "".join(selected_lines)
        else:
            returned_content = content

        return {
            "path": str(safe_path.relative_to(Path(self.workspace_dir).resolve())),
            "total_lines": total_lines,
            "size_bytes": file_size,
            "content": returned_content,
        }
