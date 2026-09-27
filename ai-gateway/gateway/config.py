import os
import logging
from pathlib import Path
from typing import Optional, List, Dict
from pydantic import BaseModel
from dotenv import load_dotenv

logger = logging.getLogger("gateway.config")

# Locate .env file dynamically: look in current dir, parent dir, or project root
current_dir = Path(__file__).resolve().parent
search_paths = [
    current_dir / ".env",
    current_dir.parent / ".env",
    Path.cwd() / ".env",
]

env_loaded = False
for p in search_paths:
    if p.exists():
        load_dotenv(dotenv_path=p, override=True)
        env_loaded = True
        break

if not env_loaded:
    load_dotenv()

class Settings(BaseModel):
    # App
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Enterprise AI Gateway")
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Security & Administration
    GATEWAY_ADMIN_KEY: Optional[str] = os.getenv("GATEWAY_ADMIN_KEY", None)
    DEFAULT_MASTER_KEY: str = os.getenv("DEFAULT_MASTER_KEY", "gw-live-master-enterprise-key-2026")

    # LLM Providers (Loaded strictly from environment)
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY", None)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY", None)
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", None)

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./gateway.db")

    # Redis Cache & Rate Limit
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Caching
    EXACT_CACHE_ENABLED: bool = os.getenv("EXACT_CACHE_ENABLED", "true").lower() in ("true", "1")
    EXACT_CACHE_TTL: int = int(os.getenv("EXACT_CACHE_TTL", "3600"))
    SEMANTIC_CACHE_ENABLED: bool = os.getenv("SEMANTIC_CACHE_ENABLED", "true").lower() in ("true", "1")
    SEMANTIC_CACHE_THRESHOLD: float = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.88"))

    # Guardrails & Rate Limits
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("true", "1")
    GUARDRAILS_ENABLED: bool = os.getenv("GUARDRAILS_ENABLED", "true").lower() in ("true", "1")

    # Routing
    DEFAULT_ROUTING_STRATEGY: str = os.getenv("DEFAULT_ROUTING_STRATEGY", "cost-optimized")
    HTTP_TIMEOUT_SECONDS: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "45.0"))

settings = Settings()
