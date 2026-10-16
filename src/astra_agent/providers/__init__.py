"""Provider factory and exports."""

from __future__ import annotations

from typing import Optional
from astra_agent.core.config import AstraConfig, settings
from astra_agent.providers.base import BaseLLMProvider, LLMResponse, Message, TokenUsage
from astra_agent.providers.mock import MockProvider
from astra_agent.providers.deterministic import DeterministicProvider
from astra_agent.providers.openai import OpenAIProvider
from astra_agent.providers.anthropic import AnthropicProvider
from astra_agent.providers.gemini import GeminiProvider
from astra_agent.providers.ollama import OllamaProvider


def get_provider(provider_name: Optional[str] = None, cfg: Optional[AstraConfig] = None) -> BaseLLMProvider:
    """Instantiates the configured LLM provider."""
    conf = cfg or settings
    name = (provider_name or conf.provider).lower()

    if name == "mock":
        return MockProvider()
    elif name == "deterministic":
        return DeterministicProvider()
    elif name == "openai":
        return OpenAIProvider(
            api_key=conf.openai_api_key,
            model_name=conf.model_name or "gpt-4o",
        )
    elif name == "anthropic":
        return AnthropicProvider(
            api_key=conf.anthropic_api_key,
            model_name=conf.model_name or "claude-3-5-sonnet-20241022",
        )
    elif name == "gemini":
        return GeminiProvider(
            api_key=conf.gemini_api_key,
            model_name=conf.model_name or "gemini-1.5-pro",
        )
    elif name == "ollama":
        return OllamaProvider(
            base_url=conf.ollama_base_url,
            model_name=conf.model_name or "llama3",
        )
    else:
        raise ValueError(f"Unknown provider: '{name}'. Supported providers: mock, deterministic, openai, anthropic, gemini, ollama")


__all__ = [
    "BaseLLMProvider",
    "LLMResponse",
    "Message",
    "TokenUsage",
    "MockProvider",
    "DeterministicProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "OllamaProvider",
    "get_provider",
]
