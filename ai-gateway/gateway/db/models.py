import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def get_utc_now():
    return datetime.now(timezone.utc)

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    keys = relationship("VirtualKey", back_populates="organization", cascade="all, delete-orphan")


class VirtualKey(Base):
    __tablename__ = "virtual_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(64), unique=True, index=True, nullable=False)
    key_prefix = Column(String(32), nullable=False)
    masked_key = Column(String(64), nullable=False)
    token_cap = Column(Integer, nullable=True) # Max allowed tokens (None for unlimited)
    cost_cap = Column(Float, nullable=True)     # Max allowed USD cost (None for unlimited)
    current_tokens = Column(Integer, default=0, nullable=False)
    current_cost = Column(Float, default=0.0, nullable=False)
    rate_limit_rpm = Column(Integer, default=120, nullable=False) # Requests Per Minute
    rate_limit_tpm = Column(Integer, default=100000, nullable=False) # Tokens Per Minute
    allowed_models = Column(Text, default='["*"]', nullable=False) # JSON array of allowed model patterns
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)

    organization = relationship("Organization", back_populates="keys")
    logs = relationship("RequestLog", back_populates="virtual_key")


class SemanticCacheEntry(Base):
    __tablename__ = "semantic_cache"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prompt_hash = Column(String(64), index=True, nullable=False)
    prompt = Column(Text, nullable=False)
    embedding = Column(Text, nullable=False) # JSON encoded vector floats
    response_json = Column(Text, nullable=False)
    model = Column(String(128), nullable=False)
    hit_count = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)


class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key_id = Column(String(36), ForeignKey("virtual_keys.id", ondelete="SET NULL"), nullable=True)
    key_name = Column(String(255), nullable=True)
    provider = Column(String(64), nullable=False)
    model = Column(String(128), nullable=False)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Float, default=0.0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    status_code = Column(Integer, default=200, nullable=False)
    cache_hit = Column(String(16), default="NONE", nullable=False) # NONE, EXACT, SEMANTIC
    routing_strategy = Column(String(64), default="direct", nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, index=True)

    virtual_key = relationship("VirtualKey", back_populates="logs")

# Index for fast telemetry queries
Index("idx_request_logs_created_at_desc", RequestLog.created_at.desc())
