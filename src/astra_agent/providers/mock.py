"""Mock LLM provider for offline deterministic unit and integration testing."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from astra_agent.providers.base import BaseLLMProvider, LLMResponse, Message, TokenUsage


class MockProvider(BaseLLMProvider):
    """Returns predetermined responses or queues of responses for offline tests."""

    name = "mock"

    def __init__(self, responses: Optional[List[LLMResponse]] = None):
        self._responses: List[LLMResponse] = list(responses or [])
        self._history: List[List[Message]] = []

    def queue_response(self, response: LLMResponse) -> None:
        self._responses.append(response)

    def queue_text(self, text: str, total_tokens: int = 50) -> None:
        self._responses.append(LLMResponse(
            content=text,
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=total_tokens//2, completion_tokens=total_tokens//2, total_tokens=total_tokens),
        ))

    def queue_tool_call(self, tool_name: str, arguments: Dict[str, Any], thought: str = "Calling tool") -> None:
        self._responses.append(LLMResponse(
            content=thought,
            tool_calls=[{
                "id": f"call_{len(self._responses)}",
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": arguments,
                }
            }],
            usage=TokenUsage(prompt_tokens=40, completion_tokens=30, total_tokens=70),
        ))

    @property
    def call_history(self) -> List[List[Message]]:
        return self._history

    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        self._history.append(messages)

        if self._responses:
            return self._responses.pop(0)

        # Default fallback response if queue is empty
        return LLMResponse(
            content="Task completed successfully.",
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=30, completion_tokens=10, total_tokens=40),
            finish_reason="stop",
        )
