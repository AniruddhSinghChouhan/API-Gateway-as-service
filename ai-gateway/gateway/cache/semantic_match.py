import json
import math
import hashlib
import time
import logging
from typing import Optional, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import SemanticCacheEntry
from adapters.base import LLMRequest, LLMResponse
from config import settings

logger = logging.getLogger("gateway.cache.semantic")

VECTOR_DIM = 128

def compute_lightweight_embedding(text: str) -> List[float]:
    """
    Computes a deterministic normalized n-gram hashed feature vector.
    Enables semantic similarity matching without external heavy dependencies.
    """
    cleaned = text.lower().strip()
    words = cleaned.split()
    # 2-grams and 3-grams
    ngrams = words + [f"{words[i]}_{words[i+1]}" for i in range(len(words)-1)]
    
    vec = [0.0] * VECTOR_DIM
    if not ngrams:
        return vec

    for ng in ngrams:
        # Hashing trick into VECTOR_DIM buckets
        h = int(hashlib.md5(ng.encode()).hexdigest(), 16)
        bucket = h % VECTOR_DIM
        weight = 1.0 if "_" not in ng else 1.8 # Give higher weight to bigrams
        vec[bucket] += weight

    # Normalize L2 norm
    magnitude = math.sqrt(sum(x * x for x in vec))
    if magnitude > 0:
        vec = [x / magnitude for x in vec]

    return vec

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if len(v1) != len(v2) or not v1:
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    return dot_product

class SemanticCache:
    async def get(self, request: LLMRequest, db: AsyncSession) -> Optional[Tuple[LLMResponse, float]]:
        if not settings.SEMANTIC_CACHE_ENABLED:
            return None

        # Extract last user message as prompt
        user_prompt = ""
        for m in reversed(request.messages):
            if m.role == "user":
                user_prompt = m.content
                break

        if not user_prompt or len(user_prompt) < 10:
            return None

        query_vec = compute_lightweight_embedding(user_prompt)

        # Retrieve recent semantic cache entries
        result = await db.execute(
            select(SemanticCacheEntry)
            .order_by(SemanticCacheEntry.created_at.desc())
            .limit(100)
        )
        entries = result.scalars().all()

        best_entry = None
        best_sim = 0.0

        for entry in entries:
            try:
                cached_vec = json.loads(entry.embedding)
                sim = cosine_similarity(query_vec, cached_vec)
                if sim > best_sim:
                    best_sim = sim
                    best_entry = entry
            except Exception:
                continue

        if best_entry and best_sim >= settings.SEMANTIC_CACHE_THRESHOLD:
            logger.info(f"Semantic cache HIT (similarity={best_sim:.3f}) for: '{user_prompt[:50]}'")
            best_entry.hit_count += 1
            await db.commit()

            data = json.loads(best_entry.response_json)
            response = LLMResponse(**data)
            return response, best_sim

        return None

    async def set(self, request: LLMRequest, response: LLMResponse, db: AsyncSession):
        if not settings.SEMANTIC_CACHE_ENABLED:
            return

        user_prompt = ""
        for m in reversed(request.messages):
            if m.role == "user":
                user_prompt = m.content
                break

        if not user_prompt or len(user_prompt) < 10:
            return

        query_vec = compute_lightweight_embedding(user_prompt)
        prompt_hash = hashlib.sha256(user_prompt.encode()).hexdigest()

        entry = SemanticCacheEntry(
            prompt_hash=prompt_hash,
            prompt=user_prompt[:1000],
            embedding=json.dumps(query_vec),
            response_json=json.dumps(response.model_dump()),
            model=response.model
        )
        db.add(entry)
        await db.commit()

semantic_cache = SemanticCache()
