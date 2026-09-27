import time
import uuid
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Depends, HTTPException, Header, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.database import get_db, engine, AsyncSessionLocal
from db.models import Base, Organization, VirtualKey, RequestLog, SemanticCacheEntry
from db.init_db import init_database, hash_key
from adapters.base import LLMRequest, LLMResponse, ChatMessage, Usage
from adapters import get_adapter
from router.load_balancer import load_balancer, RouteTarget, MODEL_REGISTRY
from router.fallback_engine import fallback_engine
from middleware.auth import authenticate_request
from middleware.rate_limit import rate_limiter
from middleware.guardrails import guardrails
from cache.exact_match import exact_match_cache
from cache.semantic_match import semantic_cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gateway.main")

def validate_startup_security():
    """
    Lightweight startup security audit.
    Checks environment bindings without logging sensitive secrets.
    """
    logger.info("Performing startup security & credentials audit...")
    active_providers = []
    missing_providers = []

    provider_checks = [
        ("GROQ_API_KEY", settings.GROQ_API_KEY),
        ("OPENAI_API_KEY", settings.OPENAI_API_KEY),
        ("ANTHROPIC_API_KEY", settings.ANTHROPIC_API_KEY),
        ("GEMINI_API_KEY", settings.GEMINI_API_KEY),
    ]

    for name, key in provider_checks:
        if key and len(key.strip()) > 0:
            active_providers.append(name)
            logger.info(f"✓ Security: [{name}] loaded securely from environment (len={len(key)}).")
        else:
            missing_providers.append(name)

    if not active_providers:
        logger.warning(
            "⚠️ SECURITY / CONFIG WARNING: No LLM provider API keys found in environment! "
            "Please configure at least one in your .env file (GROQ_API_KEY, GEMINI_API_KEY, etc.)."
        )
    else:
        logger.info(f"✓ Security: Active Provider Keys configured: {', '.join(active_providers)}")
        if missing_providers:
            logger.info(f"ℹ Security: Optional unconfigured keys: {', '.join(missing_providers)} (routes will bypass these)")

    if not settings.GATEWAY_ADMIN_KEY:
        logger.warning("ℹ Security: GATEWAY_ADMIN_KEY is not set. Master admin bypass is disabled.")
    else:
        logger.info("✓ Security: [GATEWAY_ADMIN_KEY] loaded securely from environment.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: security audit, initialize database tables and seed initial organization & keys
    validate_startup_security()
    logger.info("Initializing AI Gateway database and services...")
    await init_database()
    logger.info("AI Gateway is ready and accepting requests.")
    yield
    # Shutdown
    logger.info("Shutting down AI Gateway...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Enterprise-grade AI Gateway-as-a-Service (LLM Router, Multi-Provider Proxy, Budget Management)",
    lifespan=lifespan
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Health Check Endpoint
# ---------------------------------------------------------
@app.get("/health", tags=["System"])
async def health_check():
    db_status = "connected"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(select(1))
    except Exception as e:
        db_status = f"unhealthy ({str(e)})"

    active_providers = ["groq"]
    if settings.OPENAI_API_KEY:
        active_providers.append("openai")
    if settings.ANTHROPIC_API_KEY:
        active_providers.append("anthropic")
    if settings.GEMINI_API_KEY:
        active_providers.append("gemini")

    return {
        "status": "healthy",
        "service": "ai-gateway",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "caching": {
            "exact_match": settings.EXACT_CACHE_ENABLED,
            "semantic_match": settings.SEMANTIC_CACHE_ENABLED
        },
        "guardrails": settings.GUARDRAILS_ENABLED,
        "rate_limiting": settings.RATE_LIMIT_ENABLED,
        "active_providers": active_providers,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# ---------------------------------------------------------
# OpenAI Compatible: Models List Endpoint
# ---------------------------------------------------------
@app.get("/v1/models", tags=["OpenAI Compatible"])
async def list_models():
    data = []
    for r in MODEL_REGISTRY:
        data.append({
            "id": r.model,
            "object": "model",
            "created": 1700000000,
            "owned_by": r.provider,
            "permission": [],
            "root": r.model,
            "parent": None,
            "pricing": {
                "input_per_1k": r.cost_per_1k_input,
                "output_per_1k": r.cost_per_1k_output
            },
            "avg_latency_ms": round(r.avg_latency_ms, 1)
        })
    # Add virtual router aliases
    for alias in ["cost-optimized", "latency-optimized", "auto-router"]:
        data.append({
            "id": alias,
            "object": "model",
            "created": 1700000000,
            "owned_by": "ai-gateway-router"
        })
    return {"object": "list", "data": data}

# ---------------------------------------------------------
# OpenAI Compatible: Chat Completions Endpoint
# ---------------------------------------------------------
@app.post("/v1/chat/completions", tags=["OpenAI Compatible"])
async def chat_completions(
    request: LLMRequest,
    raw_request: Request,
    vkey: VirtualKey = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db)
):
    start_time = time.time()
    strategy = raw_request.headers.get("x-routing-strategy", settings.DEFAULT_ROUTING_STRATEGY)

    # 1. Rate Limit Enforcement
    await rate_limiter.check_rate_limit(vkey)

    # 2. Guardrails (Prompt Injection + PII Redaction)
    sanitized_messages, pii_redacted = guardrails.process_messages(request.messages)
    processed_request = request.model_copy(update={"messages": sanitized_messages})

    # 3. Exact Match Cache Check (Non-streaming only)
    if not request.stream:
        cached_resp = await exact_match_cache.get(processed_request)
        if cached_resp:
            latency_ms = (time.time() - start_time) * 1000.0
            # Record cache hit log
            log = RequestLog(
                id=str(uuid.uuid4()),
                key_id=vkey.id,
                key_name=vkey.name,
                provider=cached_resp.provider,
                model=cached_resp.model,
                prompt_tokens=cached_resp.usage.prompt_tokens,
                completion_tokens=cached_resp.usage.completion_tokens,
                total_tokens=cached_resp.usage.total_tokens,
                latency_ms=round(latency_ms, 2),
                cost_usd=0.0,
                status_code=200,
                cache_hit="EXACT",
                routing_strategy="cache-hit"
            )
            db.add(log)
            await db.commit()

            return {
                "id": cached_resp.id,
                "object": "chat.completion",
                "created": cached_resp.created,
                "model": cached_resp.model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": cached_resp.role,
                        "content": cached_resp.content
                    },
                    "finish_reason": cached_resp.finish_reason
                }],
                "usage": cached_resp.usage.model_dump(),
                "gateway": {
                    "cache_hit": "EXACT",
                    "latency_ms": round(latency_ms, 2),
                    "pii_redacted": pii_redacted,
                    "provider": cached_resp.provider
                }
            }

        # 4. Semantic Match Cache Check
        sem_match = await semantic_cache.get(processed_request, db)
        if sem_match:
            cached_resp, similarity = sem_match
            latency_ms = (time.time() - start_time) * 1000.0
            log = RequestLog(
                id=str(uuid.uuid4()),
                key_id=vkey.id,
                key_name=vkey.name,
                provider=cached_resp.provider,
                model=cached_resp.model,
                prompt_tokens=cached_resp.usage.prompt_tokens,
                completion_tokens=cached_resp.usage.completion_tokens,
                total_tokens=cached_resp.usage.total_tokens,
                latency_ms=round(latency_ms, 2),
                cost_usd=0.0,
                status_code=200,
                cache_hit="SEMANTIC",
                routing_strategy="semantic-cache-hit"
            )
            db.add(log)
            await db.commit()

            return {
                "id": cached_resp.id,
                "object": "chat.completion",
                "created": cached_resp.created,
                "model": cached_resp.model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": cached_resp.role,
                        "content": cached_resp.content
                    },
                    "finish_reason": cached_resp.finish_reason
                }],
                "usage": cached_resp.usage.model_dump(),
                "gateway": {
                    "cache_hit": "SEMANTIC",
                    "similarity": round(similarity, 3),
                    "latency_ms": round(latency_ms, 2),
                    "pii_redacted": pii_redacted,
                    "provider": cached_resp.provider
                }
            }

    # 5. Routing & Execution
    if request.stream:
        # Determine route target
        target = load_balancer.get_route_for_model(request.model, strategy)
        adapter = get_adapter(target.provider)
        target_request = processed_request.model_copy(update={"model": target.model})

        async def stream_wrapper():
            try:
                async for chunk in adapter.stream(target_request):
                    yield chunk
            except Exception as e:
                logger.error(f"Streaming error on provider {target.provider}: {e}")
                err_chunk = {
                    "error": {
                        "message": str(e),
                        "type": "gateway_stream_error"
                    }
                }
                yield f"data: {json.dumps(err_chunk)}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(stream_wrapper(), media_type="text/event-stream")

    # Non-streaming execution with automatic Fallback failover
    llm_resp, latency_ms, prov_used, model_used, was_fallback = await fallback_engine.execute_complete(
        processed_request,
        strategy=strategy
    )

    # Calculate token cost
    cost_usd = 0.0
    for r in MODEL_REGISTRY:
        if r.provider == prov_used and r.model == model_used:
            cost_usd = ((llm_resp.usage.prompt_tokens / 1000.0) * r.cost_per_1k_input) + \
                       ((llm_resp.usage.completion_tokens / 1000.0) * r.cost_per_1k_output)
            break

    # 6. Save in Exact and Semantic Caches
    await exact_match_cache.set(processed_request, llm_resp)
    await semantic_cache.set(processed_request, llm_resp, db)

    # 7. Update Virtual Key Usage Counters
    if vkey.id != "admin-master":
        vkey_in_db = await db.get(VirtualKey, vkey.id)
        if vkey_in_db:
            vkey_in_db.current_tokens += llm_resp.usage.total_tokens
            vkey_in_db.current_cost += cost_usd

    # 8. Log Request Telemetry
    req_log = RequestLog(
        id=str(uuid.uuid4()),
        key_id=vkey.id,
        key_name=vkey.name,
        provider=prov_used,
        model=model_used,
        prompt_tokens=llm_resp.usage.prompt_tokens,
        completion_tokens=llm_resp.usage.completion_tokens,
        total_tokens=llm_resp.usage.total_tokens,
        latency_ms=round(latency_ms, 2),
        cost_usd=round(cost_usd, 6),
        status_code=200,
        cache_hit="NONE",
        routing_strategy=strategy,
        error_message="Fallback Activated" if was_fallback else None
    )
    db.add(req_log)
    await db.commit()

    return {
        "id": llm_resp.id,
        "object": "chat.completion",
        "created": llm_resp.created,
        "model": model_used,
        "choices": [{
            "index": 0,
            "message": {
                "role": llm_resp.role,
                "content": llm_resp.content
            },
            "finish_reason": llm_resp.finish_reason
        }],
        "usage": llm_resp.usage.model_dump(),
        "gateway": {
            "provider": prov_used,
            "latency_ms": round(latency_ms, 2),
            "cost_usd": round(cost_usd, 6),
            "cache_hit": "NONE",
            "fallback_used": was_fallback,
            "pii_redacted": pii_redacted,
            "strategy": strategy
        }
    }

# ---------------------------------------------------------
# Virtual Key Management API
# ---------------------------------------------------------
class CreateKeyRequest(BaseModel):
    name: str
    token_cap: Optional[int] = None
    cost_cap: Optional[float] = None
    rate_limit_rpm: int = 120
    rate_limit_tpm: int = 100000
    allowed_models: List[str] = ["*"]

class UpdateKeyRequest(BaseModel):
    name: Optional[str] = None
    token_cap: Optional[int] = None
    cost_cap: Optional[float] = None
    rate_limit_rpm: Optional[int] = None
    rate_limit_tpm: Optional[int] = None
    is_active: Optional[bool] = None

@app.get("/api/keys", tags=["Key Management"])
async def list_keys(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VirtualKey).order_by(VirtualKey.created_at.desc()))
    keys = result.scalars().all()
    return [
        {
            "id": k.id,
            "name": k.name,
            "key_prefix": k.key_prefix,
            "masked_key": k.masked_key,
            "token_cap": k.token_cap,
            "cost_cap": k.cost_cap,
            "current_tokens": k.current_tokens,
            "current_cost": round(k.current_cost, 4),
            "rate_limit_rpm": k.rate_limit_rpm,
            "rate_limit_tpm": k.rate_limit_tpm,
            "allowed_models": json.loads(k.allowed_models) if k.allowed_models.startswith("[") else [k.allowed_models],
            "is_active": k.is_active,
            "created_at": k.created_at.isoformat() if k.created_at else None
        }
        for k in keys
    ]

@app.post("/api/keys", tags=["Key Management"])
async def create_key(req: CreateKeyRequest, db: AsyncSession = Depends(get_db)):
    # Find default organization
    org_res = await db.execute(select(Organization))
    org = org_res.scalars().first()
    org_id = org.id if org else str(uuid.uuid4())

    # Generate cryptographically secure virtual key
    secret_token = f"gw-live-{uuid.uuid4().hex[:12]}-{uuid.uuid4().hex[:12]}"
    hashed = hash_key(secret_token)
    prefix = secret_token[:12]
    masked = f"{prefix}****{secret_token[-4:]}"

    new_key = VirtualKey(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        name=req.name,
        key_hash=hashed,
        key_prefix=prefix,
        masked_key=masked,
        token_cap=req.token_cap,
        cost_cap=req.cost_cap,
        rate_limit_rpm=req.rate_limit_rpm,
        rate_limit_tpm=req.rate_limit_tpm,
        allowed_models=json.dumps(req.allowed_models),
        is_active=True
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)

    return {
        "id": new_key.id,
        "name": new_key.name,
        "api_key": secret_token, # Only returned ONCE upon creation!
        "masked_key": new_key.masked_key,
        "token_cap": new_key.token_cap,
        "cost_cap": new_key.cost_cap,
        "rate_limit_rpm": new_key.rate_limit_rpm,
        "created_at": new_key.created_at.isoformat()
    }

@app.patch("/api/keys/{key_id}", tags=["Key Management"])
async def update_key(key_id: str, req: UpdateKeyRequest, db: AsyncSession = Depends(get_db)):
    vkey = await db.get(VirtualKey, key_id)
    if not vkey:
        raise HTTPException(status_code=404, detail="Virtual key not found")

    if req.name is not None:
        vkey.name = req.name
    if req.token_cap is not None:
        vkey.token_cap = req.token_cap
    if req.cost_cap is not None:
        vkey.cost_cap = req.cost_cap
    if req.rate_limit_rpm is not None:
        vkey.rate_limit_rpm = req.rate_limit_rpm
    if req.rate_limit_tpm is not None:
        vkey.rate_limit_tpm = req.rate_limit_tpm
    if req.is_active is not None:
        vkey.is_active = req.is_active

    await db.commit()
    await db.refresh(vkey)
    return {"status": "success", "key_id": vkey.id, "is_active": vkey.is_active}

@app.delete("/api/keys/{key_id}", tags=["Key Management"])
async def revoke_key(key_id: str, db: AsyncSession = Depends(get_db)):
    vkey = await db.get(VirtualKey, key_id)
    if not vkey:
        raise HTTPException(status_code=404, detail="Virtual key not found")
    vkey.is_active = False
    await db.commit()
    return {"status": "revoked", "key_id": key_id}

# ---------------------------------------------------------
# Telemetry, Analytics & Metrics API
# ---------------------------------------------------------
@app.get("/api/metrics", tags=["Telemetry"])
async def get_metrics(db: AsyncSession = Depends(get_db)):
    # 1. Total Requests
    total_req_res = await db.execute(select(func.count(RequestLog.id)))
    total_requests = total_req_res.scalar() or 0

    # 2. Total Tokens & Cost
    totals_res = await db.execute(
        select(
            func.sum(RequestLog.total_tokens),
            func.sum(RequestLog.cost_usd),
            func.avg(RequestLog.latency_ms)
        )
    )
    tot_tokens, tot_cost, avg_lat = totals_res.first()
    tot_tokens = tot_tokens or 0
    tot_cost = round(tot_cost or 0.0, 4)
    avg_lat = round(avg_lat or 0.0, 1)

    # 3. Cache Hits
    cache_hits_res = await db.execute(
        select(func.count(RequestLog.id)).where(RequestLog.cache_hit != "NONE")
    )
    cache_hits = cache_hits_res.scalar() or 0
    hit_rate = round((cache_hits / total_requests * 100.0), 1) if total_requests > 0 else 0.0

    # Estimate cost saved by cache (~$0.0003 per cached req)
    cost_saved = round(cache_hits * 0.00035, 4)

    # 4. Breakdown by Provider
    prov_res = await db.execute(
        select(
            RequestLog.provider,
            func.count(RequestLog.id),
            func.avg(RequestLog.latency_ms),
            func.sum(RequestLog.cost_usd)
        ).group_by(RequestLog.provider)
    )
    provider_breakdown = [
        {
            "provider": row[0],
            "requests": row[1],
            "avg_latency": round(row[2] or 0.0, 1),
            "total_cost": round(row[3] or 0.0, 4)
        }
        for row in prov_res.all()
    ]

    # 5. Breakdown by Model
    model_res = await db.execute(
        select(
            RequestLog.model,
            func.count(RequestLog.id),
            func.avg(RequestLog.latency_ms)
        ).group_by(RequestLog.model).order_by(desc(func.count(RequestLog.id))).limit(6)
    )
    model_breakdown = [
        {"model": row[0], "requests": row[1], "avg_latency": round(row[2] or 0.0, 1)}
        for row in model_res.all()
    ]

    return {
        "total_requests": total_requests,
        "total_tokens": tot_tokens,
        "total_cost_usd": tot_cost,
        "avg_latency_ms": avg_lat,
        "cache_hits": cache_hits,
        "cache_hit_rate": hit_rate,
        "cost_saved_usd": cost_saved,
        "provider_breakdown": provider_breakdown,
        "model_breakdown": model_breakdown
    }

@app.get("/api/logs", tags=["Telemetry"])
async def get_logs(
    limit: int = 50,
    provider: Optional[str] = None,
    cache_hit: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(RequestLog).order_by(RequestLog.created_at.desc())
    if provider:
        query = query.where(RequestLog.provider == provider)
    if cache_hit:
        query = query.where(RequestLog.cache_hit == cache_hit)
    query = query.limit(limit)

    res = await db.execute(query)
    logs = res.scalars().all()
    return [
        {
            "id": l.id,
            "key_name": l.key_name or "Master Key",
            "provider": l.provider,
            "model": l.model,
            "prompt_tokens": l.prompt_tokens,
            "completion_tokens": l.completion_tokens,
            "total_tokens": l.total_tokens,
            "latency_ms": l.latency_ms,
            "cost_usd": l.cost_usd,
            "status_code": l.status_code,
            "cache_hit": l.cache_hit,
            "routing_strategy": l.routing_strategy,
            "error_message": l.error_message,
            "created_at": l.created_at.isoformat() if l.created_at else None
        }
        for l in logs
    ]

@app.get("/api/router/status", tags=["Router"])
async def router_status():
    routes_status = []
    now = time.time()
    for r in MODEL_REGISTRY:
        routes_status.append({
            "provider": r.provider,
            "model": r.model,
            "cost_per_1k_input": r.cost_per_1k_input,
            "cost_per_1k_output": r.cost_per_1k_output,
            "avg_latency_ms": round(r.avg_latency_ms, 1),
            "success_count": r.success_count,
            "error_count": r.error_count,
            "status": "healthy" if r.cooldown_until <= now else "cooldown",
            "cooldown_remaining_sec": max(0, int(r.cooldown_until - now))
        })
    return {"strategies": ["cost-optimized", "latency-optimized", "round-robin", "weighted"], "routes": routes_status}
