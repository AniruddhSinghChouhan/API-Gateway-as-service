import json
import hashlib
import time
import logging
from typing import Optional
from adapters.base import LLMRequest, LLMResponse
from config import settings

logger = logging.getLogger("gateway.cache.exact")

# In-memory LRU-style fallback cache: key -> (serialized_json, expire_timestamp)
_IN_MEMORY_EXACT_CACHE = {}

# Try Redis
_redis_client = None
try:
    import redis.asyncio as aioredis
    _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=1.0)
except Exception:
    _redis_client = None

class ExactMatchCache:
    def _compute_key(self, request: LLMRequest) -> str:
        # Build deterministic representation
        normalized = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content.strip()} for m in request.messages],
            "temperature": request.temperature or 0.7
        }
        raw_str = json.dumps(normalized, sort_keys=True)
        return f"cache:exact:{hashlib.sha256(raw_str.encode()).hexdigest()}"

    async def get(self, request: LLMRequest) -> Optional[LLMResponse]:
        if not settings.EXACT_CACHE_ENABLED:
            return None

        cache_key = self._compute_key(request)

        # 1. Try Redis
        if _redis_client:
            try:
                cached_data = await _redis_client.get(cache_key)
                if cached_data:
                    logger.info(f"Exact cache HIT (Redis) for key: {cache_key}")
                    data = json.loads(cached_data)
                    return LLMResponse(**data)
            except Exception as e:
                logger.debug(f"Redis get failed: {e}")

        # 2. Try In-memory fallback
        if cache_key in _IN_MEMORY_EXACT_CACHE:
            cached_data, expires_at = _IN_MEMORY_EXACT_CACHE[cache_key]
            if time.time() < expires_at:
                logger.info(f"Exact cache HIT (Memory) for key: {cache_key}")
                data = json.loads(cached_data)
                return LLMResponse(**data)
            else:
                del _IN_MEMORY_EXACT_CACHE[cache_key]

        return None

    async def set(self, request: LLMRequest, response: LLMResponse, ttl: Optional[int] = None):
        if not settings.EXACT_CACHE_ENABLED:
            return

        cache_key = self._compute_key(request)
        ttl = ttl or settings.EXACT_CACHE_TTL
        data_str = json.dumps(response.model_dump())

        # 1. Try Redis
        if _redis_client:
            try:
                await _redis_client.setex(cache_key, ttl, data_str)
                return
            except Exception as e:
                logger.debug(f"Redis set failed: {e}")

        # 2. Save in In-memory fallback
        _IN_MEMORY_EXACT_CACHE[cache_key] = (data_str, time.time() + ttl)

exact_match_cache = ExactMatchCache()
