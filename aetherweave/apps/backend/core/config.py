"""
AetherWeave Backend — Application Configuration
================================================

All settings are read from environment variables (with .env file support via
python-dotenv). Pydantic Settings v2 handles validation and type coercion.

Environment variables map directly to field names. Example .env file:

    DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/aetherweave
    NEO4J_URI=bolt://localhost:7687
    NEO4J_USERNAME=neo4j
    NEO4J_PASSWORD=secret
    REDIS_URL=redis://localhost:6379/0
    DEBUG=true
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application-wide settings loaded from environment variables.

    All fields have sensible defaults for local development. In production,
    override via environment variables or a .env file at the project root.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars (e.g., CI injected vars)
    )

    # ── Core ──────────────────────────────────────────────────────────────

    VERSION: str = Field(default="0.1.0", description="Application semantic version")
    ENVIRONMENT: str = Field(
        default="development",
        description="Runtime environment: development | staging | production",
    )
    DEBUG: bool = Field(
        default=True, description="Enable debug mode (verbose logs, OpenAPI docs)"
    )
    SECRET_KEY: str = Field(
        default="change-me-in-production",
        description="Secret key for token signing — MUST be overridden in production",
    )

    # ── CORS ──────────────────────────────────────────────────────────────

    ALLOWED_ORIGINS: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://*.aetherweave.app",
        ],
        description="List of allowed CORS origins",
    )

    # ── PostgreSQL ────────────────────────────────────────────────────────

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/aetherweave",
        description="Async SQLAlchemy connection URL (must use asyncpg driver)",
    )
    DB_POOL_SIZE: int = Field(
        default=10, ge=1, le=100,
        description="SQLAlchemy connection pool size",
    )
    DB_MAX_OVERFLOW: int = Field(
        default=20, ge=0, le=100,
        description="SQLAlchemy pool max overflow",
    )
    DB_ECHO: bool = Field(
        default=False, description="Enable SQLAlchemy query echo logging"
    )

    # ── Neo4j ─────────────────────────────────────────────────────────────

    NEO4J_URI: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j Bolt protocol URI",
    )
    NEO4J_USERNAME: str = Field(default="neo4j", description="Neo4j username")
    NEO4J_PASSWORD: str = Field(default="password", description="Neo4j password")
    NEO4J_DATABASE: str = Field(default="neo4j", description="Neo4j database name")

    # ── Redis ─────────────────────────────────────────────────────────────

    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    REDIS_MAX_CONNECTIONS: int = Field(
        default=50, ge=1, description="Redis connection pool maximum"
    )
    CACHE_TTL_SECONDS: int = Field(
        default=300, ge=0, description="Default cache TTL in seconds (5 minutes)"
    )

    # ── Celery ────────────────────────────────────────────────────────────

    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/1",
        description="Celery broker URL (uses a separate Redis DB from the cache)",
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/2",
        description="Celery result store URL",
    )

    # ── Evolution engine ──────────────────────────────────────────────────

    MAX_EVOLUTION_GENERATIONS: int = Field(
        default=500, ge=1,
        description="Hard cap on the number of generations per evolution run",
    )
    DEFAULT_POPULATION_SIZE: int = Field(
        default=20, ge=10,
        description="Default DEAP population size",
    )
    EVOLUTION_TIMEOUT_SECONDS: int = Field(
        default=300, ge=10,
        description="Maximum wall-clock time for an evolution run (seconds)",
    )

    # ── LLM / LangGraph ───────────────────────────────────────────────────

    OPENAI_API_KEY: str = Field(
        default="",
        description="OpenAI API key for LangGraph agent LLMs (leave empty to use mocks)",
    )
    LLM_MODEL: str = Field(
        default="gpt-4o-mini",
        description="LLM model name used by all LangGraph agents",
    )

    # ── Validators ────────────────────────────────────────────────────────

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_db_url(cls, v: str) -> str:
        """Ensure the DATABASE_URL uses the asyncpg driver."""
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must start with 'postgresql+asyncpg://' "
                "(SQLAlchemy async requires the asyncpg driver)."
            )
        return v

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Normalise and validate the environment value."""
        allowed = {"development", "staging", "production"}
        v = v.lower()
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}, got '{v}'")
        return v


# ── Module-level singleton ────────────────────────────────────────────────────

settings: Settings = Settings()
