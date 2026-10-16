"""Path-restricted local file writer tool."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict
from pydantic import BaseModel, Field

from astra_agent.core.models import PermissionLevel, SideEffectType
from astra_agent.security.path_validator import PathValidator
from astra_agent.tools.base import BaseTool


class FileWriterInput(BaseModel):
    """Input parameters for writing a file."""
    path: str = Field(..., description="Target file path relative to workspace.")
    content: str = Field(..., description="Text content to write into the file.")
    append: bool = Field(False, description="If True, append to existing file; otherwise overwrite.")
    encoding: str = Field("utf-8", description="Character encoding.")


class FileWriterTool(BaseTool):
    """Writes files safely within the designated workspace boundary."""

    name = "file_writer"
    description = "Writes or appends text content to a file inside the designated workspace boundary."
    permission_level = PermissionLevel.WORKSPACE_WRITE
    side_effect_type = SideEffectType.FILESYSTEM
    idempotent = False  # Appending is not idempotent; overwriting is
    input_schema = FileWriterInput

    def _run(self, inputs: FileWriterInput) -> Dict[str, Any]:
        if not self.workspace_dir:
            raise ValueError("Workspace directory is not configured for file_writer.")

        safe_path = PathValidator.resolve_safe_path(self.workspace_dir, inputs.path)
        safe_path.parent.mkdir(parents=True, exist_ok=True)

        if inputs.append and safe_path.exists():
            with open(safe_path, "a", encoding=inputs.encoding) as f:
                f.write(inputs.content)
            action = "appended"
        else:
            # Atomic overwrite using temporary file
            with tempfile.NamedTemporaryFile("w", dir=str(safe_path.parent), delete=False, encoding=inputs.encoding) as tf:
                tf.write(inputs.content)
                temp_name = tf.name
            Path(temp_name).replace(safe_path)
            action = "written"

        return {
            "path": str(safe_path.relative_to(Path(self.workspace_dir).resolve())),
            "action": action,
            "bytes_written": len(inputs.content.encode(inputs.encoding)),
        }
