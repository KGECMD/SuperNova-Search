"""
Cache manager for Atomic Search.

Provides in-memory and Redis caching support.
"""

import hashlib
import json
import pickle
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional


@dataclass
class CacheEntry:
    """Cache entry with TTL."""
    key: str
    value: Any
    expires_at: float


class LRUCache:
    """Thread-safe LRU cache."""

    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self._cache = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]

                # Check TTL
                if entry.expires_at > time.time():
                    # Move to end (most recently used)
                    self._cache.move_to_end(key)
                    self._stats["hits"] += 1
                    return entry.value
                else:
                    # Expired, remove
                    del self._cache[key]

            self._stats["misses"] += 1
            return None

    def set(self, key: str, value: Any, ttl: int = None):
        """Set value in cache."""
        with self._lock:
            expires_at = time.time() + (ttl or self.ttl)

            # Remove if exists
            if key in self._cache:
                del self._cache[key]

            # Add new entry
            self._cache[key] = CacheEntry(key, value, expires_at)

            # Evict if over max size
            while len(self._cache) > self.max_size:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
                self._stats["evictions"] += 1

    def delete(self, key: str):
        """Delete value from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()

    def cleanup(self):
        """Remove expired entries."""
        with self._lock:
            now = time.time()
            expired = [k for k, v in self._cache.items() if v.expires_at <= now]

            for key in expired:
                del self._cache[key]

            return len(expired)

    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0

            return {
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "evictions": self._stats["evictions"],
                "size": len(self._cache),
                "max_size": self.max_size,
                "hit_rate": round(hit_rate * 100, 2),
            }


class RedisCache:
    """Redis cache wrapper."""

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._enabled = redis_client is not None

    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        if not self._enabled:
            return None

        try:
            value = self.redis.get(key)
            if value:
                return pickle.loads(value)
        except Exception:
            pass

        return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        """Set value in Redis."""
        if not self._enabled:
            return

        try:
            self.redis.setex(key, ttl, pickle.dumps(value))
        except Exception:
            pass

    def delete(self, key: str):
        """Delete value from Redis."""
        if not self._enabled:
            return

        try:
            self.redis.delete(key)
        except Exception:
            pass

    def clear(self):
        """Clear all cache."""
        if not self._enabled:
            return

        try:
            self.redis.flushdb()
        except Exception:
            pass

    def get_stats(self) -> dict:
        """Get Redis stats."""
        if not self._enabled:
            return {"enabled": False}

        try:
            info = self.redis.info("stats")
            return {
                "enabled": True,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
            }
        except Exception:
            return {"enabled": True, "error": "Could not get stats"}


class CacheManager:
    """Multi-layer cache manager."""

    def __init__(self, redis_client=None):
        self.l1_cache = LRUCache(max_size=500, ttl=300)  # 5 min memory
        self.l2_cache = RedisCache(redis_client)  # Redis
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache layers."""
        # Try L1 first
        value = self.l1_cache.get(key)
        if value is not None:
            return value

        # Try L2 (Redis)
        value = self.l2_cache.get(key)
        if value is not None:
            # Promote to L1
            self.l1_cache.set(key, value)
            return value

        return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        """Set value in both cache layers."""
        with self._lock:
            self.l1_cache.set(key, value, min(ttl, 300))
            self.l2_cache.set(key, value, ttl)

    def delete(self, key: str):
        """Delete from both cache layers."""
        self.l1_cache.delete(key)
        self.l2_cache.delete(key)

    def invalidate_pattern(self, pattern: str):
        """Invalidate cache entries matching pattern."""
        # L1 doesn't support pattern matching, clear all
        self.l1_cache.clear()
        # Redis can use KEYS pattern (not recommended in production)
        if self.l2_cache._enabled:
            try:
                keys = self.l2_cache.redis.keys(pattern)
                if keys:
                    self.l2_cache.redis.delete(*keys)
            except Exception:
                pass

    def get_stats(self) -> dict:
        """Get stats from all cache layers."""
        return {
            "l1_memory": self.l1_cache.get_stats(),
            "l2_redis": self.l2_cache.get_stats(),
        }

    def cleanup(self):
        """Cleanup expired entries."""
        return self.l1_cache.cleanup()


def generate_cache_key(*args, **kwargs) -> str:
    """Generate a cache key from arguments."""
    data = "-".join(str(arg) for arg in args)
    data += "-".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return hashlib.md5(data.encode()).hexdigest()


# Global cache manager
cache_manager = CacheManager()
