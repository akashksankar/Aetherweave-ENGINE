"""
AetherWeave Backend — Redis Client Setup
=========================================

Redis is used for:
1. Caching architecture fitness scores (avoids recomputing expensive metrics).
2. Pub/Sub for broadcasting WebSocket events between Uvicorn workers.
3. Celery broker (via a separate DB index).

Init sequence:
  await init_redis()  → creates ConnectionPool + pings Redis
  await close_redis() → closes pool gracefully
"""

from __future__ import annotations

import structlog
from redis.asyncio import ConnectionPool, Redis

from apps.backend.core.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── Module-level singletons ───────────────────────────────────────────────────

_redis: Redis | None = None
_pool: ConnectionPool | None = None


async def init_redis() -> None:
    """
    Initialise the async Redis client with a connection pool.

    The pool is shared for all cache operations. A separate pool is used
    by Celery (configured via CELERY_BROKER_URL in settings).

    Raises:
        redis.exceptions.ConnectionError: If Redis is not reachable.
    """
    global _redis, _pool
    _pool = ConnectionPool.from_url(
        settings.REDIS_URL,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        decode_responses=True,  # return str instead of bytes (easier to use)
    )
    _redis = Redis(connection_pool=_pool)
    # Health check — raises if unreachable
    pong = await _redis.ping()
    assert pong, "Redis did not respond to PING"
    logger.info("redis_initialised", url=settings.REDIS_URL)


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _redis, _pool
    if _redis is not None:
        await _redis.aclose()
        logger.info("redis_closed")
        _redis = None
    if _pool is not None:
        await _pool.disconnect()
        _pool = None


def get_redis() -> Redis:
    """
    Return the module-level Redis client.

    Raises:
        RuntimeError: If init_redis() has not been called.

    Returns:
        Configured async Redis client.
    """
    if _redis is None:
        raise RuntimeError("Redis not initialised. Call init_redis() first.")
    return _redis


async def cache_set(key: str, value: str, ttl: int | None = None) -> None:
    """
    Store a string value in Redis.

    Args:
        key:   Cache key string.
        value: String value to cache.
        ttl:   Time-to-live in seconds. Uses settings.CACHE_TTL_SECONDS if None.
    """
    r = get_redis()
    await r.set(key, value, ex=ttl or settings.CACHE_TTL_SECONDS)


async def cache_get(key: str) -> str | None:
    """
    Retrieve a cached value.

    Args:
        key: Cache key string.

    Returns:
        The cached string value, or None if not found / expired.
    """
    r = get_redis()
    return await r.get(key)


async def cache_delete(key: str) -> None:
    """
    Invalidate a cached entry.

    Args:
        key: Cache key to delete.
    """
    r = get_redis()
    await r.delete(key)
