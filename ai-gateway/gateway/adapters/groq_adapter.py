import json
import time
import httpx
from typing import AsyncGenerator
from fastapi import HTTPException
from adapters.base import BaseProviderAdapter, LLMRequest, LLMResponse, Usage

DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"

# Map common generic model aliases to fast Groq models
GROQ_MODEL_ALIASES = {
    "default": "openai/gpt-oss-20b",
    "gpt-3.5-turbo": "openai/gpt-oss-20b",
    "gpt-4o-mini": "openai/gpt-oss-20b",
    "gpt-4": "openai/gpt-oss-120b",
    "qwen": "qwen/qwen3.8-27b",
    "fast": "openai/gpt-oss-20b",
    "smart": "openai/gpt-oss-120b"
}

class GroqAdapter(BaseProviderAdapter):
    def __init__(self, api_key: str, base_url: str = "https://api.groq.com/openai/v1"):
        super().__init__(api_key, base_url)
        self.endpoint = f"{self.base_url.rstrip('/')}/chat/completions"

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _resolve_model(self, model: str) -> str:
        if model in GROQ_MODEL_ALIASES:
            return GROQ_MODEL_ALIASES[model]
        return model

    async def complete(self, request: LLMRequest) -> LLMResponse:
        resolved_model = self._resolve_model(request.model)
        payload = {
            "model": resolved_model,
            "messages": [m.model_dump(exclude_none=True) for m in request.messages],
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": False
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(self.endpoint, headers=self._headers(), json=payload)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"Groq API error: {resp.text}"
                )
            data = resp.json()
            choice = data["choices"][0]
            usage_data = data.get("usage", {})

            return LLMResponse(
                id=data.get("id", f"chatcmpl-groq-{int(time.time())}"),
                created=data.get("created", int(time.time())),
                model=resolved_model,
                content=choice["message"].get("content", ""),
                finish_reason=choice.get("finish_reason", "stop"),
                usage=Usage(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0)
                ),
                provider="groq"
            )

    async def stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        resolved_model = self._resolve_model(request.model)
        payload = {
            "model": resolved_model,
            "messages": [m.model_dump(exclude_none=True) for m in request.messages],
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": True
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", self.endpoint, headers=self._headers(), json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    raise HTTPException(status_code=response.status_code, detail=f"Groq error: {err_body.decode()}")

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        yield f"{line}\n\n"
                    elif line == "data: [DONE]":
                        yield "data: [DONE]\n\n"
