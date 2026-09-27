import hashlib
import time
from typing import Optional, Tuple
from fastapi import Request, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.models import VirtualKey
from config import settings

security = HTTPBearer(auto_error=False)

def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

# Fast in-memory cache for validated keys: hash -> (VirtualKey dict, expire_timestamp)
_KEY_CACHE = {}

async def authenticate_request(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: AsyncSession = Depends(get_db)
) -> VirtualKey:
    """
    Validates virtual key, checks token/cost caps and active status.
    Returns the VirtualKey DB model.
    """
    if not credentials or not credentials.credentials:
        # Check if query parameter or header exists
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization Header. Please provide a valid Bearer Virtual Key."
        )

    token = credentials.credentials.strip()

    # Admin Key bypass (if configured)
    if settings.GATEWAY_ADMIN_KEY and token == settings.GATEWAY_ADMIN_KEY:
        # Return a mock VirtualKey with unlimited access for admin
        return VirtualKey(
            id="admin-master",
            organization_id="admin-org",
            name="System Admin Master Key",
            key_hash=hash_key(token),
            key_prefix="admin",
            masked_key="admin-****-master",
            token_cap=None,
            cost_cap=None,
            current_tokens=0,
            current_cost=0.0,
            rate_limit_rpm=10000,
            rate_limit_tpm=10000000,
            allowed_models='["*"]',
            is_active=True
        )

    key_hashed = hash_key(token)

    # Check database for key
    result = await db.execute(select(VirtualKey).where(VirtualKey.key_hash == key_hashed))
    vkey = result.scalars().first()

    if not vkey:
        raise HTTPException(
            status_code=401,
            detail="Invalid Virtual Key. Key not recognized by AI Gateway."
        )

    if not vkey.is_active:
        raise HTTPException(
            status_code=403,
            detail="This Virtual Key has been revoked or deactivated."
        )

    # Check budget caps
    if vkey.token_cap is not None and vkey.current_tokens >= vkey.token_cap:
        raise HTTPException(
            status_code=402,
            detail=f"Token budget cap reached ({vkey.current_tokens:,} / {vkey.token_cap:,} tokens). Please increase your cap in the dashboard."
        )

    if vkey.cost_cap is not None and vkey.current_cost >= vkey.cost_cap:
        raise HTTPException(
            status_code=402,
            detail=f"Cost budget cap reached (${vkey.current_cost:.2f} / ${vkey.cost_cap:.2f}). Please increase your budget in the dashboard."
        )

    return vkey
