import json
import time
import httpx
from typing import AsyncGenerator
from fastapi import HTTPException
from adapters.base import BaseProviderAdapter, LLMRequest, LLMResponse, Usage

class AnthropicAdapter(BaseProviderAdapter):
    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com/v1"):
        super().__init__(api_key, base_url)
        self.endpoint = f"{self.base_url.rstrip('/')}/messages"

    def _headers(self):
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

    def _transform_request(self, request: LLMRequest):
        system_prompt = None
        messages = []
        for m in request.messages:
            if m.role == "system":
                system_prompt = m.content
            else:
                messages.append({
                    "role": "user" if m.role == "user" else "assistant",
                    "content": m.content
                })

        payload = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or 1024,
            "temperature": request.temperature or 0.7,
        }
        if system_prompt:
            payload["system"] = system_prompt
        return payload

    async def complete(self, request: LLMRequest) -> LLMResponse:
        payload = self._transform_request(request)
        payload["stream"] = False

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(self.endpoint, headers=self._headers(), json=payload)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"Anthropic error: {resp.text}"
                )
            data = resp.json()
            # Extract content from text blocks
            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")

            usage_info = data.get("usage", {})
            p_tok = usage_info.get("input_tokens", 0)
            c_tok = usage_info.get("output_tokens", 0)

            return LLMResponse(
                id=data.get("id", f"msg-{int(time.time())}"),
                created=int(time.time()),
                model=data.get("model", request.model),
                content=content,
                finish_reason=data.get("stop_reason", "stop"),
                usage=Usage(
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    total_tokens=p_tok + c_tok
                ),
                provider="anthropic"
            )

    async def stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        payload = self._transform_request(request)
        payload["stream"] = True
        completion_id = f"chatcmpl-anthropic-{int(time.time())}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", self.endpoint, headers=self._headers(), json=payload) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    raise HTTPException(status_code=response.status_code, detail=f"Anthropic error: {error_body.decode()}")

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        try:
                            event_data = json.loads(data_str)
                            event_type = event_data.get("type")
                            if event_type == "content_block_delta":
                                text_delta = event_data.get("delta", {}).get("text", "")
                                chunk = {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": request.model,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {"content": text_delta},
                                        "finish_reason": None
                                    }]
                                }
                                yield f"data: {json.dumps(chunk)}\n\n"
                            elif event_type == "message_stop":
                                chunk = {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": request.model,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {},
                                        "finish_reason": "stop"
                                    }]
                                }
                                yield f"data: {json.dumps(chunk)}\n\n"
                                yield "data: [DONE]\n\n"
                        except Exception:
                            continue
