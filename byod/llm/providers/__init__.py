"""Thin HTTP adapters using fixed provider destinations."""

from collections.abc import Callable

from byod.llm.base import LLMProvider, ProviderError
from byod.llm.providers.anthropic import AnthropicProvider
from byod.llm.providers.ollama import OllamaProvider
from byod.llm.providers.openai import OpenAIProvider

ProviderFactory = Callable[[str, str | None], LLMProvider]


def provider_for(name: str, key: str | None = None) -> LLMProvider:
    if name == "openai":
        return OpenAIProvider(key)
    if name == "anthropic":
        return AnthropicProvider(key)
    if name == "ollama":
        return OllamaProvider()
    raise ProviderError("NO_PROVIDER", name)
