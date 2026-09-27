import logging
from typing import Optional, Dict
from adapters.base import BaseProviderAdapter, LLMRequest, LLMResponse, ChatMessage, Usage
from adapters.openai_adapter import OpenAIAdapter
from adapters.anthropic_adapter import AnthropicAdapter
from adapters.gemini_adapter import GeminiAdapter
from adapters.groq_adapter import GroqAdapter
from config import settings

logger = logging.getLogger("gateway.adapters")

_ADAPTER_CACHE: Dict[str, BaseProviderAdapter] = {}

def get_adapter(provider: str) -> BaseProviderAdapter:
    provider = provider.lower()
    if provider in _ADAPTER_CACHE:
        return _ADAPTER_CACHE[provider]

    if provider == "groq":
        adapter = GroqAdapter(api_key=settings.GROQ_API_KEY)
    elif provider == "openai":
        adapter = OpenAIAdapter(api_key=settings.OPENAI_API_KEY)
    elif provider == "anthropic":
        adapter = AnthropicAdapter(api_key=settings.ANTHROPIC_API_KEY)
    elif provider == "gemini":
        adapter = GeminiAdapter(api_key=settings.GEMINI_API_KEY)
    else:
        # Default to Groq if available
        adapter = GroqAdapter(api_key=settings.GROQ_API_KEY)

    _ADAPTER_CACHE[provider] = adapter
    return adapter

__all__ = [
    "BaseProviderAdapter",
    "LLMRequest",
    "LLMResponse",
    "ChatMessage",
    "Usage",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "GeminiAdapter",
    "GroqAdapter",
    "get_adapter"
]
