import logging
from typing import Optional, Dict
from fastapi import HTTPException
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
        if not settings.GROQ_API_KEY:
            raise HTTPException(
                status_code=503,
                detail="Provider 'groq' is not configured. Please set GROQ_API_KEY in your .env file."
            )
        adapter = GroqAdapter(api_key=settings.GROQ_API_KEY)

    elif provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise HTTPException(
                status_code=503,
                detail="Provider 'openai' is not configured. Please set OPENAI_API_KEY in your .env file."
            )
        adapter = OpenAIAdapter(api_key=settings.OPENAI_API_KEY)

    elif provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise HTTPException(
                status_code=503,
                detail="Provider 'anthropic' is not configured. Please set ANTHROPIC_API_KEY in your .env file."
            )
        adapter = AnthropicAdapter(api_key=settings.ANTHROPIC_API_KEY)

    elif provider == "gemini":
        if not settings.GEMINI_API_KEY:
            raise HTTPException(
                status_code=503,
                detail="Provider 'gemini' is not configured. Please set GEMINI_API_KEY in your .env file."
            )
        adapter = GeminiAdapter(api_key=settings.GEMINI_API_KEY)

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown or unsupported provider '{provider}'."
        )

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
