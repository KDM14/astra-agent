"""Anthropic Claude API provider implementation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx

from astra_agent.providers.base import BaseLLMProvider, LLMResponse, Message, TokenUsage


class AnthropicProvider(BaseLLMProvider):
    """Integrates with Anthropic Messages API (Claude 3.5 Sonnet, Claude 3 Opus, etc.)."""

    name = "anthropic"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "claude-3-5-sonnet-20241022",
        base_url: str = "https://api.anthropic.com/v1",
        timeout: float = 60.0,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        if not self.api_key:
            raise ValueError("Anthropic API key is missing. Set ASTRA_ANTHROPIC_API_KEY or configure provider.")

        system_prompt = ""
        user_messages = []
        for m in messages:
            if m.role == "system":
                system_prompt += m.content + "\n"
            else:
                user_messages.append({"role": m.role, "content": m.content})

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": user_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt.strip()

        if tools:
            # Map tools to Anthropic format
            anthropic_tools = []
            for t in tools:
                anthropic_tools.append({
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {"type": "object"}),
                })
            payload["tools"] = anthropic_tools

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/messages", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        content_blocks = data.get("content", [])
        text_content = ""
        tool_calls = []

        for block in content_blocks:
            if block.get("type") == "text":
                text_content += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block.get("id"),
                    "type": "function",
                    "function": {
                        "name": block.get("name"),
                        "arguments": block.get("input", {}),
                    }
                })

        raw_usage = data.get("usage", {})
        prompt_tokens = raw_usage.get("input_tokens", 0)
        completion_tokens = raw_usage.get("output_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens

        # Claude 3.5 Sonnet estimated pricing ($3/M in, $15/M out)
        cost_usd = (prompt_tokens * 0.000003) + (completion_tokens * 0.000015)

        return LLMResponse(
            content=text_content,
            tool_calls=tool_calls,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=round(cost_usd, 6),
            ),
            finish_reason=data.get("stop_reason", "end_turn"),
            raw_response=data,
        )
