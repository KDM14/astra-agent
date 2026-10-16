"""Base tool abstractions and execution contracts."""

from __future__ import annotations

import abc
import time
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, ValidationError

from astra_agent.core.models import PermissionLevel, SideEffectType, ToolResult
from astra_agent.security.secret_redactor import SecretRedactor


class BaseTool(abc.ABC):
    """Abstract base class for all typed Astra Agent tools."""

    name: str
    description: str
    permission_level: PermissionLevel = PermissionLevel.READ_ONLY
    side_effect_type: SideEffectType = SideEffectType.NONE
    idempotent: bool = True
    default_timeout: float = 30.0
    input_schema: Type[BaseModel]
    output_schema: Optional[Type[BaseModel]] = None

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = workspace_dir

    def validate_inputs(self, arguments: Dict[str, Any]) -> BaseModel:
        """Validates arguments against the tool's input schema."""
        try:
            return self.input_schema.model_validate(arguments)
        except ValidationError as e:
            raise ValueError(f"Invalid arguments for tool '{self.name}': {e.errors()}")

    @abc.abstractmethod
    def _run(self, inputs: BaseModel) -> Any:
        """Core tool implementation to be overridden by subclasses."""
        pass

    def run(self, arguments: Dict[str, Any], call_id: Optional[str] = None) -> ToolResult:
        """Executes the tool with parameter validation, timing, and error handling."""
        actual_call_id = call_id or f"call_{int(time.time()*1000)}"
        start_time = time.perf_counter()

        try:
            validated_inputs = self.validate_inputs(arguments)
            raw_output = self._run(validated_inputs)
            
            # Redact any secrets from tool output
            sanitized_output = SecretRedactor.redact_data(raw_output)

            duration = (time.perf_counter() - start_time) * 1000.0
            return ToolResult(
                call_id=actual_call_id,
                tool_name=self.name,
                success=True,
                output=sanitized_output,
                duration_ms=round(duration, 2),
                side_effects=[self.side_effect_type.value] if self.side_effect_type != SideEffectType.NONE else [],
            )

        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000.0
            return ToolResult(
                call_id=actual_call_id,
                tool_name=self.name,
                success=False,
                output=None,
                error=f"{type(e).__name__}: {str(e)}",
                duration_ms=round(duration, 2),
                side_effects=[],
            )
