"""
Rate limiting for Atomic Search.

Provides request rate limiting and throttling.
"""

import hashlib
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_size: int = 10


class TokenBucket:
    """Token bucket algorithm implementation."""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self._lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens."""
        with self._lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update

        new_tokens = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_update = now


class RateLimiter:
    """Multi-tier rate limiter."""

    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self._buckets: Dict[str, Tuple[TokenBucket, TokenBucket, TokenBucket]] = {}
        self._lock = threading.Lock()

    def _get_buckets(self, key: str) -> Tuple[TokenBucket, TokenBucket, TokenBucket]:
        """Get or create buckets for a key."""
        if key not in self._buckets:
            minute_rate = self.config.requests_per_minute / 60.0
            hour_rate = self.config.requests_per_hour / 3600.0
            day_rate = self.config.requests_per_day / 86400.0

            minute_bucket = TokenBucket(minute_rate, self.config.burst_size)
            hour_bucket = TokenBucket(hour_rate, self.config.requests_per_hour // 10)
            day_bucket = TokenBucket(day_rate, self.config.requests_per_day // 10)

            self._buckets[key] = (minute_bucket, hour_bucket, day_bucket)

        return self._buckets[key]

    def check_rate_limit(self, key: str) -> Tuple[bool, Dict]:
        """Check if request is within rate limits."""
        minute, hour, day = self._get_buckets(key)

        minute_ok = minute.consume()
        hour_ok = hour.consume()
        day_ok = day.consume()

        allowed = minute_ok and hour_ok and day_ok

        return allowed, {
            "minute_remaining": int(minute.tokens),
            "hour_remaining": int(hour.tokens),
            "day_remaining": int(day.tokens),
        }

    def get_remaining(self, key: str) -> Dict:
        """Get remaining requests for a key."""
        if key not in self._buckets:
            return {
                "minute_remaining": self.config.requests_per_minute,
                "hour_remaining": self.config.requests_per_hour,
                "day_remaining": self.config.requests_per_day,
            }

        minute, hour, day = self._buckets[key]

        return {
            "minute_remaining": int(minute.tokens),
            "hour_remaining": int(hour.tokens),
            "day_remaining": int(day.tokens),
        }

    def reset(self, key: str):
        """Reset rate limit for a key."""
        with self._lock:
            if key in self._buckets:
                del self._buckets[key]


class IPRateLimiter(RateLimiter):
    """IP-based rate limiter."""

    def check_ip(self, ip: str) -> Tuple[bool, Dict]:
        """Check rate limit for an IP address."""
        return self.check_rate_limit(f"ip:{ip}")

    def get_ip_remaining(self, ip: str) -> Dict:
        """Get remaining requests for an IP."""
        return self.get_remaining(f"ip:{ip}")

    def reset_ip(self, ip: str):
        """Reset rate limit for an IP."""
        self.reset(f"ip:{ip}")


class UserRateLimiter(RateLimiter):
    """User-based rate limiter."""

    def check_user(self, user_id: str) -> Tuple[bool, Dict]:
        """Check rate limit for a user."""
        return self.check_rate_limit(f"user:{user_id}")

    def get_user_remaining(self, user_id: str) -> Dict:
        """Get remaining requests for a user."""
        return self.get_remaining(f"user:{user_id}")

    def reset_user(self, user_id: str):
        """Reset rate limit for a user."""
        self.reset(f"user:{user_id}")


class APIRateLimiter(RateLimiter):
    """API key-based rate limiter."""

    def check_api_key(self, api_key: str) -> Tuple[bool, Dict]:
        """Check rate limit for an API key."""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        return self.check_rate_limit(f"api:{key_hash}")

    def get_api_key_remaining(self, api_key: str) -> Dict:
        """Get remaining requests for an API key."""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        return self.get_remaining(f"api:{key_hash}")

    def reset_api_key(self, api_key: str):
        """Reset rate limit for an API key."""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        self.reset(f"api:{key_hash}")


# Global limiter instances
ip_limiter = IPRateLimiter()
user_limiter = UserRateLimiter()
api_limiter = APIRateLimiter()
