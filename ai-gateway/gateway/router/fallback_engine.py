import time
import logging
from typing import List, Tuple, Optional, AsyncGenerator
from fastapi import HTTPException
from adapters.base import LLMRequest, LLMResponse
from adapters import get_adapter
from router.load_balancer import load_balancer, RouteTarget, MODEL_REGISTRY

logger = logging.getLogger("gateway.router.fallback")

class FallbackEngine:
    def get_fallback_chain(self, primary_target: RouteTarget) -> List[RouteTarget]:
        # Formulate ordered chain: primary target first, then alternative providers
        chain = [primary_target]
        for r in MODEL_REGISTRY:
            if r.provider != primary_target.provider and r not in chain:
                chain.append(r)
        return chain

    async def execute_complete(
        self,
        request: LLMRequest,
        strategy: str = "cost-optimized"
    ) -> Tuple[LLMResponse, float, str, str, bool]:
        """
        Executes request through load balancer and fallback engine.
        Returns: (LLMResponse, latency_ms, provider_used, model_used, was_fallback)
        """
        primary_target = load_balancer.get_route_for_model(request.model, strategy)
        chain = self.get_fallback_chain(primary_target)
        
        last_error = None
        was_fallback = False

        for i, target in enumerate(chain):
            start_time = time.time()
            adapter = get_adapter(target.provider)
            # Create a localized copy of request with target's model
            target_request = request.model_copy(update={"model": target.model})

            try:
                logger.info(f"Routing request to provider={target.provider} model={target.model} (attempt {i+1})")
                response = await adapter.complete(target_request)
                latency_ms = (time.time() - start_time) * 1000.0

                # Record success metrics for EWMA
                load_balancer.record_execution(
                    provider=target.provider,
                    model=target.model,
                    latency_ms=latency_ms,
                    success=True,
                    status_code=200
                )

                return response, latency_ms, target.provider, target.model, was_fallback

            except HTTPException as http_exc:
                latency_ms = (time.time() - start_time) * 1000.0
                last_error = http_exc
                logger.warning(
                    f"Provider {target.provider} failed with {http_exc.status_code}: {http_exc.detail}. Engaging fallback..."
                )
                load_balancer.record_execution(
                    provider=target.provider,
                    model=target.model,
                    latency_ms=latency_ms,
                    success=False,
                    status_code=http_exc.status_code
                )
                was_fallback = True
                continue

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000.0
                last_error = e
                logger.warning(f"Provider {target.provider} encountered unexpected error: {e}. Engaging fallback...")
                load_balancer.record_execution(
                    provider=target.provider,
                    model=target.model,
                    latency_ms=latency_ms,
                    success=False,
                    status_code=500
                )
                was_fallback = True
                continue

        # If all candidates fail, raise the last error
        if isinstance(last_error, HTTPException):
            raise last_error
        raise HTTPException(
            status_code=502,
            detail=f"All upstream providers in fallback chain failed. Last error: {str(last_error)}"
        )

fallback_engine = FallbackEngine()
