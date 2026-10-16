"""Google Gemini API provider implementation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx

from astra_agent.providers.base import BaseLLMProvider, LLMResponse, Message, TokenUsage


class GeminiProvider(BaseLLMProvider):
    """Integrates with Google Gemini API (gemini-1.5-pro, gemini-2.0-flash, etc.)."""

    name = "gemini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-1.5-pro",
        timeout: float = 60.0,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout

    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        if not self.api_key:
            raise ValueError("Gemini API key is missing. Set ASTRA_GEMINI_API_KEY or configure provider.")

        contents = []
        for m in messages:
            role = "model" if m.role == "assistant" else "user"
            contents.append({
                "role": role,
                "parts": [{"text": m.content}],
            })

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return LLMResponse(content="", tool_calls=[])

        first_cand = candidates[0]
        parts = first_cand.get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)

        usage_meta = data.get("usageMetadata", {})
        prompt_tokens = usage_meta.get("promptTokenCount", 0)
        completion_tokens = usage_meta.get("candidatesTokenCount", 0)
        total_tokens = usage_meta.get("totalTokenCount", prompt_tokens + completion_tokens)

        # Estimate cost
        cost_usd = (prompt_tokens * 0.00000125) + (completion_tokens * 0.000005)

        return LLMResponse(
            content=text,
            tool_calls=[],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=round(cost_usd, 6),
            ),
            raw_response=data,
        )
