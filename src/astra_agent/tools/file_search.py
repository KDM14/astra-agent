"""Workspace file search and discovery tool."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from astra_agent.core.models import PermissionLevel, SideEffectType
from astra_agent.tools.base import BaseTool


class FileSearchInput(BaseModel):
    """Input parameters for searching files."""
    pattern: str = Field("*", description="Glob pattern to match file names (e.g. '*.py', 'test_*.py').")
    content_regex: Optional[str] = Field(None, description="Optional regex pattern to search inside file contents.")
    max_results: int = Field(50, ge=1, le=200, description="Maximum number of matches to return.")


class FileSearchTool(BaseTool):
    """Discovers files and content matches within the workspace."""

    name = "file_search"
    description = "Searches for files matching a name pattern or containing text within the workspace."
    permission_level = PermissionLevel.READ_ONLY
    side_effect_type = SideEffectType.NONE
    idempotent = True
    input_schema = FileSearchInput

    def _run(self, inputs: FileSearchInput) -> Dict[str, Any]:
        if not self.workspace_dir:
            raise ValueError("Workspace directory is not configured for file_search.")

        ws = Path(self.workspace_dir).resolve()
        matches: List[Dict[str, Any]] = []

        compiled_regex = re.compile(inputs.content_regex) if inputs.content_regex else None

        for path in ws.rglob("*"):
            if not path.is_file():
                continue
            
            # Check pattern match
            rel_path = path.relative_to(ws)
            if not fnmatch.fnmatch(path.name, inputs.pattern) and not fnmatch.fnmatch(str(rel_path), inputs.pattern):
                continue

            match_info: Dict[str, Any] = {
                "path": str(rel_path),
                "size_bytes": path.stat().st_size,
            }

            if compiled_regex:
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                    regex_matches = [m.start() for m in compiled_regex.finditer(text)]
                    if not regex_matches:
                        continue
                    match_info["content_matches"] = len(regex_matches)
                except Exception:
                    continue

            matches.append(match_info)
            if len(matches) >= inputs.max_results:
                break

        return {
            "query_pattern": inputs.pattern,
            "content_regex": inputs.content_regex,
            "count": len(matches),
            "results": matches,
        }
