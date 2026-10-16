"""OpenAI API provider implementation."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
import httpx

from astra_agent.providers.base import BaseLLMProvider, LLMResponse, Message, TokenUsage


class OpenAIProvider(BaseLLMProvider):
    """Integrates with OpenAI Chat Completions API (GPT-4o, GPT-4-turbo, etc.)."""

    name = "openai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
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
            raise ValueError("OpenAI API key is missing. Set ASTRA_OPENAI_API_KEY or configure provider.")

        formatted_messages = []
        for m in messages:
            msg_dict: Dict[str, Any] = {"role": m.role, "content": m.content}
            if m.tool_calls:
                msg_dict["tool_calls"] = m.tool_calls
            if m.tool_call_id:
                msg_dict["tool_call_id"] = m.tool_call_id
            formatted_messages.append(msg_dict)

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        msg = choice["message"]
        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls") or []

        # Parse stringified json arguments in tool calls if needed
        parsed_tool_calls = []
        for tc in tool_calls:
            f = tc.get("function", {})
            args = f.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"raw": args}
            parsed_tool_calls.append({
                "id": tc.get("id"),
                "type": "function",
                "function": {
                    "name": f.get("name"),
                    "arguments": args,
                }
            })

        raw_usage = data.get("usage", {})
        prompt_tokens = raw_usage.get("prompt_tokens", 0)
        completion_tokens = raw_usage.get("completion_tokens", 0)
        total_tokens = raw_usage.get("total_tokens", prompt_tokens + completion_tokens)

        # Standard pricing estimate ($5/M prompt, $15/M completion for gpt-4o)
        cost_usd = (prompt_tokens * 0.000005) + (completion_tokens * 0.000015)

        return LLMResponse(
            content=content,
            tool_calls=parsed_tool_calls,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=round(cost_usd, 6),
            ),
            finish_reason=choice.get("finish_reason", "stop"),
            raw_response=data,
        )
