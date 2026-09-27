import hashlib
import uuid
from datetime import datetime, timezone, timedelta
import random
from sqlalchemy import select, text
from db.database import engine, AsyncSessionLocal
from db.models import Base, Organization, VirtualKey, RequestLog

from config import settings

def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

async def init_database():
    async with engine.begin() as conn:
        # If PostgreSQL, try creating pgvector extension
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        except Exception:
            pass
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Check if organization exists
        result = await session.execute(select(Organization))
        org = result.scalars().first()
        if not org:
            org = Organization(
                id=str(uuid.uuid4()),
                name="Acme Enterprise AI Core"
            )
            session.add(org)
            await session.commit()
            await session.refresh(org)

        # Check if Master Virtual Key exists
        master_key_secret = settings.DEFAULT_MASTER_KEY
        master_hash = hash_key(master_key_secret)
        key_result = await session.execute(select(VirtualKey).where(VirtualKey.key_hash == master_hash))
        master_key = key_result.scalars().first()

        if not master_key:
            master_key = VirtualKey(
                id=str(uuid.uuid4()),
                organization_id=org.id,
                name="Production Master Key",
                key_hash=master_hash,
                key_prefix="gw-live-master",
                masked_key="gw-live-****-2026",
                token_cap=10000000,
                cost_cap=1000.0,
                current_tokens=48210,
                current_cost=0.48,
                rate_limit_rpm=300,
                rate_limit_tpm=300000,
                allowed_models='["*"]',
                is_active=True
            )
            session.add(master_key)

            # Add sandbox key
            sandbox_key_secret = "gw-live-developer-sandbox-key-789"
            sandbox_hash = hash_key(sandbox_key_secret)
            sandbox_key = VirtualKey(
                id=str(uuid.uuid4()),
                organization_id=org.id,
                name="Sandbox Dev Key",
                key_hash=sandbox_hash,
                key_prefix="gw-live-dev",
                masked_key="gw-live-****-sbox",
                token_cap=500000,
                cost_cap=25.0,
                current_tokens=12400,
                current_cost=0.12,
                rate_limit_rpm=60,
                rate_limit_tpm=50000,
                allowed_models='["*"]',
                is_active=True
            )
            session.add(sandbox_key)
            await session.commit()

            # Seed sample request logs for realistic initial dashboard analytics
            models_sample = [
                ("groq", "openai/gpt-oss-20b", 45.2, 0.00015),
                ("groq", "qwen/qwen3.8-27b", 62.1, 0.0002),
                ("openai", "gpt-4o-mini", 310.5, 0.0006),
                ("anthropic", "claude-3-5-sonnet", 480.0, 0.003),
                ("gemini", "gemini-1.5-flash", 280.0, 0.0004),
            ]
            now = datetime.now(timezone.utc)
            for i in range(35):
                m = random.choice(models_sample)
                p_tokens = random.randint(80, 500)
                c_tokens = random.randint(50, 400)
                tot = p_tokens + c_tokens
                cache_status = "EXACT" if i % 5 == 0 else ("SEMANTIC" if i % 9 == 0 else "NONE")
                lat = 4.2 if cache_status != "NONE" else m[2] + random.uniform(-15.0, 35.0)
                cost = 0.0 if cache_status != "NONE" else round((tot / 1000.0) * m[3], 6)

                log = RequestLog(
                    id=str(uuid.uuid4()),
                    key_id=master_key.id if i % 2 == 0 else sandbox_key.id,
                    key_name=master_key.name if i % 2 == 0 else sandbox_key.name,
                    provider=m[0],
                    model=m[1],
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                    total_tokens=tot,
                    latency_ms=round(lat, 1),
                    cost_usd=cost,
                    status_code=200,
                    cache_hit=cache_status,
                    routing_strategy="cost-optimized" if i % 2 == 0 else "latency-optimized",
                    created_at=now - timedelta(minutes=i * 12 + random.randint(1, 10))
                )
                session.add(log)
            await session.commit()

    return True

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_database())
    print("Database initialized successfully.")
