import time
import random
from typing import Dict, List, Optional
from pydantic import BaseModel
from config import settings

class RouteTarget(BaseModel):
    provider: str
    model: str
    cost_per_1k_input: float
    cost_per_1k_output: float
    weight: int = 1
    avg_latency_ms: float = 100.0
    error_count: int = 0
    success_count: int = 0
    cooldown_until: float = 0.0

# Registry of supported model routes and pricing (USD per 1K tokens)
MODEL_REGISTRY: List[RouteTarget] = [
    # Groq (Super fast & free/ultra-low cost)
    RouteTarget(
        provider="groq",
        model="openai/gpt-oss-20b",
        cost_per_1k_input=0.0001,
        cost_per_1k_output=0.0002,
        weight=10,
        avg_latency_ms=60.0
    ),
    RouteTarget(
        provider="groq",
        model="qwen/qwen3.8-27b",
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0003,
        weight=8,
        avg_latency_ms=80.0
    ),
    RouteTarget(
        provider="groq",
        model="openai/gpt-oss-120b",
        cost_per_1k_input=0.0004,
        cost_per_1k_output=0.0008,
        weight=6,
        avg_latency_ms=110.0
    ),
    # OpenAI
    RouteTarget(
        provider="openai",
        model="gpt-4o-mini",
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
        weight=5,
        avg_latency_ms=320.0
    ),
    RouteTarget(
        provider="openai",
        model="gpt-4o",
        cost_per_1k_input=0.0025,
        cost_per_1k_output=0.010,
        weight=2,
        avg_latency_ms=650.0
    ),
    # Anthropic
    RouteTarget(
        provider="anthropic",
        model="claude-3-haiku-20240307",
        cost_per_1k_input=0.00025,
        cost_per_1k_output=0.00125,
        weight=4,
        avg_latency_ms=390.0
    ),
    RouteTarget(
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        weight=2,
        avg_latency_ms=750.0
    ),
    # Gemini
    RouteTarget(
        provider="gemini",
        model="gemini-1.5-flash",
        cost_per_1k_input=0.000075,
        cost_per_1k_output=0.0003,
        weight=6,
        avg_latency_ms=290.0
    ),
]

_ROUND_ROBIN_INDEX = 0

class LoadBalancer:
    def __init__(self, routes: Optional[List[RouteTarget]] = None):
        self.routes = routes or MODEL_REGISTRY

    def _filter_healthy(self, candidates: List[RouteTarget]) -> List[RouteTarget]:
        now = time.time()
        healthy = [r for r in candidates if r.cooldown_until <= now]
        return healthy if healthy else candidates

    def get_route_for_model(self, requested_model: str, strategy: str = "cost-optimized") -> RouteTarget:
        global _ROUND_ROBIN_INDEX
        now = time.time()

        # Check if direct match requested
        direct_matches = [r for r in self.routes if r.model == requested_model]
        if direct_matches:
            target = direct_matches[0]
            # If directly requested target is on cooldown, we still return it or fallback engine handles it
            return target

        # Check if provider explicitly prefixed (e.g., "groq/...", "openai/...")
        if "/" in requested_model:
            prov_prefix = requested_model.split("/")[0].lower()
            prov_matches = [r for r in self.routes if r.provider == prov_prefix]
            if prov_matches:
                return prov_matches[0]

        # Available candidates (filter providers that have API keys configured)
        candidates = []
        for r in self.routes:
            if r.provider == "groq" and settings.GROQ_API_KEY:
                candidates.append(r)
            elif r.provider == "openai" and settings.OPENAI_API_KEY:
                candidates.append(r)
            elif r.provider == "anthropic" and settings.ANTHROPIC_API_KEY:
                candidates.append(r)
            elif r.provider == "gemini" and settings.GEMINI_API_KEY:
                candidates.append(r)
        
        # If no key matching candidate, fallback to all routes
        if not candidates:
            candidates = self.routes

        healthy_candidates = self._filter_healthy(candidates)

        strat = strategy.lower()
        if "cost" in strat:
            # Sort by total estimated token cost
            sorted_candidates = sorted(healthy_candidates, key=lambda x: (x.cost_per_1k_input + x.cost_per_1k_output))
            return sorted_candidates[0]

        elif "latency" in strat:
            # Sort by observed EWMA latency
            sorted_candidates = sorted(healthy_candidates, key=lambda x: x.avg_latency_ms)
            return sorted_candidates[0]

        elif "round-robin" in strat or "rr" in strat:
            target = healthy_candidates[_ROUND_ROBIN_INDEX % len(healthy_candidates)]
            _ROUND_ROBIN_INDEX += 1
            return target

        elif "weighted" in strat:
            weights = [max(1, r.weight) for r in healthy_candidates]
            return random.choices(healthy_candidates, weights=weights, k=1)[0]

        # Default fallback
        return healthy_candidates[0]

    def record_execution(self, provider: str, model: str, latency_ms: float, success: bool, status_code: int = 200):
        for r in self.routes:
            if r.provider == provider and r.model == model:
                if success:
                    r.success_count += 1
                    # Exponential moving average for latency
                    r.avg_latency_ms = (r.avg_latency_ms * 0.8) + (latency_ms * 0.2)
                else:
                    r.error_count += 1
                    # If 429 (Rate Limit) or 5xx (Server Error), put on 30s cooldown
                    if status_code in (429, 500, 502, 503, 504):
                        r.cooldown_until = time.time() + 30.0
                break

load_balancer = LoadBalancer()
