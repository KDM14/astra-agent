"""Filesystem path validation and chroot containment security."""

from __future__ import annotations

import os
from pathlib import Path
from astra_agent.core.state import PathSecurityViolationError


class PathValidator:
    """Validates and enforces strict workspace jail boundaries."""

    @staticmethod
    def resolve_safe_path(workspace_dir: str | Path, candidate_path: str | Path) -> Path:
        """Resolves a candidate path against a workspace root and ensures no escape.

        Args:
            workspace_dir: The root directory for the sandbox.
            candidate_path: The relative or absolute path to inspect.

        Returns:
            The canonical absolute Path object.

        Raises:
            PathSecurityViolationError: If the resolved path escapes the workspace.
        """
        workspace_real = Path(workspace_dir).resolve()
        
        cand = Path(candidate_path)
        if cand.is_absolute():
            # If absolute, verify it sits inside workspace_real
            try:
                candidate_real = cand.resolve()
            except Exception as e:
                raise PathSecurityViolationError(f"Cannot resolve path '{candidate_path}': {e}")
        else:
            # If relative, resolve relative to workspace_real
            candidate_real = (workspace_real / cand).resolve()

        # Check containment: candidate_real must start with workspace_real
        try:
            candidate_real.relative_to(workspace_real)
        except ValueError:
            raise PathSecurityViolationError(
                f"Path traversal detected: '{candidate_path}' escapes workspace '{workspace_real}'"
            )

        return candidate_real

    @staticmethod
    def is_safe_path(workspace_dir: str | Path, candidate_path: str | Path) -> bool:
        """Convenience method returning True if safe, False otherwise."""
        try:
            PathValidator.resolve_safe_path(workspace_dir, candidate_path)
            return True
        except PathSecurityViolationError:
            return False
