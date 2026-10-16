"""Tool registry for discovery, permission checking, and dispatch."""

from __future__ import annotations

from typing import Dict, List, Optional
from astra_agent.core.models import PermissionLevel
from astra_agent.tools.base import BaseTool


class ToolRegistry:
    """Central registry of executable tools with permission metadata."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool with name '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def get_tool_names(self) -> List[str]:
        return list(self._tools.keys())

    def is_sensitive(self, tool_name: str) -> bool:
        tool = self.get(tool_name)
        if not tool:
            return False
        return tool.permission_level in (PermissionLevel.SENSITIVE, PermissionLevel.EXTERNAL_NETWORK)

    def describe_all(self) -> List[Dict]:
        """Returns JSON schema definitions of all registered tools."""
        descriptors = []
        for tool in self._tools.values():
            descriptors.append({
                "name": tool.name,
                "description": tool.description,
                "permission_level": tool.permission_level.value,
                "side_effect_type": tool.side_effect_type.value,
                "idempotent": tool.idempotent,
                "timeout_seconds": tool.default_timeout,
                "parameters": tool.input_schema.model_json_schema(),
            })
        return descriptors
