"""
Caching layer for AI Cost Optimizer.

NOTE: Redis caching has been deprecated in favor of Supabase semantic caching.
This module provides stub implementations for backward compatibility.
"""

import logging

logger = logging.getLogger(__name__)


class RedisCacheError(Exception):
    """Redis cache error (deprecated)."""

    pass


class RedisCache:
    """
    Stub Redis cache implementation for backward compatibility.

    This class provides no-op implementations to prevent import errors
    while the codebase is being migrated to Supabase semantic caching.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        max_connections: int = 50,
        socket_timeout: float = 5,
    ) -> None:
        """Initialize stub Redis cache."""
        logger.warning("RedisCache is deprecated. Use Supabase semantic caching instead.")
        self._available = False

    def ping(self) -> bool:
        """Check if Redis is available (always returns False)."""
        return False

    def get(self, key: str) -> None:
        """Get value from cache (always returns None)."""
        return None

    def set(self, key: str, value: object, ttl: int = 300) -> None:
        """Set value in cache (no-op)."""
        pass

    def delete(self, key: str) -> None:
        """Delete key from cache (no-op)."""
        pass

    def exists(self, key: str) -> bool:
        """Check if key exists (always returns False)."""
        return False


def create_redis_cache() -> RedisCache:
    """
    Create stub Redis cache instance.

    Returns:
        RedisCache stub instance (non-functional)
    """
    logger.warning("create_redis_cache() is deprecated. Migrate to Supabase semantic caching.")
    return RedisCache()


__all__ = ["RedisCache", "RedisCacheError", "create_redis_cache"]
