from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, AsyncGenerator
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None

class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class LLMRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    max_tokens: Optional[int] = None
    stream: bool = False
    stop: Optional[List[str]] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    user: Optional[str] = None
    extra_body: Optional[Dict[str, Any]] = None

class LLMResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    role: str = "assistant"
    content: str
    finish_reason: Optional[str] = "stop"
    usage: Usage
    provider: str

class BaseProviderAdapter(ABC):
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Execute non-streaming completion"""
        pass

    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """Execute streaming completion yielding SSE data lines"""
        pass
