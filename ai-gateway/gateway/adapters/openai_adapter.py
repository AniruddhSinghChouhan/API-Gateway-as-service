import json
import time
from typing import Optional, AsyncGenerator
import httpx
from fastapi import HTTPException
from adapters.base import BaseProviderAdapter, LLMRequest, LLMResponse, Usage

class OpenAIAdapter(BaseProviderAdapter):
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.openai.com/v1"):
        super().__init__(api_key or "", base_url)
        self.endpoint = f"{self.base_url.rstrip('/')}/chat/completions"

    def _headers(self):
        key = self.api_key or ""
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }

    async def complete(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise HTTPException(
                status_code=401,
                detail="OpenAI API key is missing or not configured in environment variables."
            )

        payload = {
            "model": request.model,
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
                    detail=f"OpenAI error: {resp.text}"
                )
            data = resp.json()
            choice = data["choices"][0]
            usage_data = data.get("usage", {})

            return LLMResponse(
                id=data.get("id", f"chatcmpl-{int(time.time())}"),
                created=data.get("created", int(time.time())),
                model=data.get("model", request.model),
                content=choice["message"].get("content", ""),
                finish_reason=choice.get("finish_reason", "stop"),
                usage=Usage(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0)
                ),
                provider="openai"
            )

    async def stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        if not self.api_key:
            raise HTTPException(
                status_code=401,
                detail="OpenAI API key is missing or not configured in environment variables."
            )

        payload = {
            "model": request.model,
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
                    raise HTTPException(status_code=response.status_code, detail=f"OpenAI error: {err_body.decode()}")

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        yield f"{line}\n\n"
