import json
import time
import httpx
from typing import AsyncGenerator
from fastapi import HTTPException
from adapters.base import BaseProviderAdapter, LLMRequest, LLMResponse, Usage

class GeminiAdapter(BaseProviderAdapter):
    def __init__(self, api_key: str, base_url: str = "https://generativelanguage.googleapis.com/v1beta"):
        super().__init__(api_key, base_url)

    def _transform_request(self, request: LLMRequest):
        system_instruction = None
        contents = []

        for m in request.messages:
            if m.role == "system":
                system_instruction = {"parts": [{"text": m.content}]}
            else:
                role = "model" if m.role == "assistant" else "user"
                contents.append({
                    "role": role,
                    "parts": [{"text": m.content}]
                })

        generation_config = {
            "temperature": request.temperature or 0.7,
            "topP": request.top_p or 0.95
        }
        if request.max_tokens:
            generation_config["maxOutputTokens"] = request.max_tokens

        payload = {
            "contents": contents,
            "generationConfig": generation_config
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        return payload

    async def complete(self, request: LLMRequest) -> LLMResponse:
        model_name = request.model
        if not model_name.startswith("gemini-"):
            model_name = "gemini-1.5-flash"

        url = f"{self.base_url.rstrip('/')}/models/{model_name}:generateContent?key={self.api_key}"
        payload = self._transform_request(request)

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=f"Gemini error: {resp.text}")

            data = resp.json()
            candidates = data.get("candidates", [])
            content_text = ""
            finish_reason = "stop"
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    content_text = parts[0].get("text", "")
                finish_reason = candidates[0].get("finishReason", "STOP").lower()

            usage_meta = data.get("usageMetadata", {})
            p_tok = usage_meta.get("promptTokenCount", 0)
            c_tok = usage_meta.get("candidatesTokenCount", 0)

            return LLMResponse(
                id=f"gemini-{int(time.time())}",
                created=int(time.time()),
                model=request.model,
                content=content_text,
                finish_reason=finish_reason,
                usage=Usage(
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    total_tokens=p_tok + c_tok
                ),
                provider="gemini"
            )

    async def stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        model_name = request.model
        if not model_name.startswith("gemini-"):
            model_name = "gemini-1.5-flash"

        url = f"{self.base_url.rstrip('/')}/models/{model_name}:streamGenerateContent?alt=sse&key={self.api_key}"
        payload = self._transform_request(request)
        completion_id = f"chatcmpl-gemini-{int(time.time())}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    raise HTTPException(status_code=response.status_code, detail=f"Gemini error: {err_body.decode()}")

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        try:
                            item = json.loads(data_str)
                            candidates = item.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts:
                                    part_text = parts[0].get("text", "")
                                    chunk = {
                                        "id": completion_id,
                                        "object": "chat.completion.chunk",
                                        "created": int(time.time()),
                                        "model": request.model,
                                        "choices": [{
                                            "index": 0,
                                            "delta": {"content": part_text},
                                            "finish_reason": None
                                        }]
                                    }
                                    yield f"data: {json.dumps(chunk)}\n\n"
                        except Exception:
                            continue

                # Final DONE chunk
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
