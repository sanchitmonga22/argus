from __future__ import annotations

from .anthropic_provider import AnthropicProvider
from .base import Mode, Provider, ProviderResult, Source
from .exa import ExaProvider
from .gemini import GeminiProvider
from .openai_provider import OpenAIProvider
from .perplexity import PerplexityProvider

REGISTRY: dict[str, type[Provider]] = {
    "exa": ExaProvider,
    "perplexity": PerplexityProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "anthropic": AnthropicProvider,
}

__all__ = [
    "Mode",
    "Provider",
    "ProviderResult",
    "Source",
    "REGISTRY",
    "ExaProvider",
    "PerplexityProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "AnthropicProvider",
]
