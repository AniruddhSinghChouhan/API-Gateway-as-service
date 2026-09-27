import time
import logging
from collections import defaultdict, deque
from typing import Optional
from fastapi import HTTPException
from db.models import VirtualKey
from config import settings

logger = logging.getLogger("gateway.middleware.rate_limit")

# Try to connect to Redis
_redis_client = None
try:
    import redis.asyncio as aioredis
    _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=1.0)
except Exception:
    _redis_client = None

# In-memory sliding window storage: key_id -> deque of timestamps
_MEMORY_RPM = defaultdict(deque)
_MEMORY_TPM = defaultdict(deque) # deque of (timestamp, token_count)

class RateLimiter:
    async def check_rate_limit(self, vkey: VirtualKey, estimated_tokens: int = 100):
        if not settings.RATE_LIMIT_ENABLED or vkey.id == "admin-master":
            return

        now = time.time()
        window_start = now - 60.0

        # Try Redis first if available
        if _redis_client:
            try:
                # RPM check via Redis sorted set
                rpm_key = f"ratelimit:rpm:{vkey.id}"
                tpm_key = f"ratelimit:tpm:{vkey.id}"

                pipe = _redis_client.pipeline()
                pipe.zremrangebyscore(rpm_key, 0, window_start)
                pipe.zcard(rpm_key)
                pipe.zadd(rpm_key, {str(now): now})
                pipe.expire(rpm_key, 65)

                results = await pipe.execute()
                current_rpm = results[1]

                if current_rpm > vkey.rate_limit_rpm:
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limit exceeded: {current_rpm} requests/min exceeds limit of {vkey.rate_limit_rpm} RPM.",
                        headers={"Retry-After": "60"}
                    )
                return
            except HTTPException:
                raise
            except Exception as e:
                # Log redis error and fallback to memory
                logger.debug(f"Redis rate limit check failed ({e}), using in-memory rate limiter")

        # In-memory fallback
        rpm_queue = _MEMORY_RPM[vkey.id]
        while rpm_queue and rpm_queue[0] < window_start:
            rpm_queue.popleft()

        if len(rpm_queue) >= vkey.rate_limit_rpm:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {len(rpm_queue)} requests/min exceeds limit of {vkey.rate_limit_rpm} RPM.",
                headers={"Retry-After": "60"}
            )

        rpm_queue.append(now)

rate_limiter = RateLimiter()
