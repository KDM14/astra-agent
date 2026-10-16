"""Ollama local model provider implementation."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
import httpx

from astra_agent.providers.base import BaseLLMProvider, LLMResponse, Message, TokenUsage


class OllamaProvider(BaseLLMProvider):
    """Integrates with local Ollama runtime (Llama 3, Mistral, Qwen, etc.)."""

    name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_name: str = "llama3",
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout

    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        ollama_messages = [{"role": m.role, "content": m.content} for m in messages]

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        msg = data.get("message", {})
        content = msg.get("content", "")

        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        total_tokens = prompt_tokens + completion_tokens

        return LLMResponse(
            content=content,
            tool_calls=[],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=0.0,  # Local execution
            ),
            finish_reason=data.get("done_reason", "stop"),
            raw_response=data,
        )
