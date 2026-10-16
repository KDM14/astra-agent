"""Base LLM provider interfaces and message schemas."""

from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single conversational message."""
    role: str = Field(..., description="'system', 'user', 'assistant', or 'tool'")
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class TokenUsage(BaseModel):
    """Token consumption and cost tracking."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class LLMResponse(BaseModel):
    """Standardized response from an LLM provider."""
    content: str
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    finish_reason: str = "stop"
    raw_response: Optional[Dict[str, Any]] = None


class BaseLLMProvider(abc.ABC):
    """Abstract interface for all model providers."""

    name: str

    @abc.abstractmethod
    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Asynchronously generates a response from the model."""
        pass
