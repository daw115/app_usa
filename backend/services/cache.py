"""
Simple in-memory cache with TTL support.
For production, consider Redis or similar.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Optional

log = logging.getLogger(__name__)

class CacheEntry:
    def __init__(self, value: Any, ttl_seconds: int):
        self.value = value
        self.expires_at = time.time() + ttl_seconds

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class SimpleCache:
    def __init__(self):
        self._store: dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if exists and not expired."""
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired():
            del self._store[key]
            self._misses += 1
            return None

        self._hits += 1
        log.debug(f"Cache HIT: {key}")
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int = 3600):
        """Set value in cache with TTL."""
        self._store[key] = CacheEntry(value, ttl_seconds)
        log.debug(f"Cache SET: {key} (TTL: {ttl_seconds}s)")

    def delete(self, key: str):
        """Delete key from cache."""
        if key in self._store:
            del self._store[key]
            log.debug(f"Cache DELETE: {key}")

    def clear(self):
        """Clear all cache entries."""
        self._store.clear()
        log.info("Cache cleared")

    def cleanup_expired(self):
        """Remove expired entries."""
        expired = [k for k, v in self._store.items() if v.is_expired()]
        for key in expired:
            del self._store[key]
        if expired:
            log.debug(f"Cache cleanup: removed {len(expired)} expired entries")

    def stats(self) -> dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "size": len(self._store),
        }


# Global cache instance
_cache = SimpleCache()


def get_cache() -> SimpleCache:
    """Get global cache instance."""
    return _cache


def cache_key_for_ai_analysis(listing_data: dict) -> str:
    """Generate cache key for AI analysis based on listing data."""
    # Use VIN + photos hash for cache key
    vin = listing_data.get("vin", "")
    photos = listing_data.get("photos", [])
    photos_hash = hashlib.md5(json.dumps(sorted(photos)).encode()).hexdigest()[:8]
    return f"ai_analysis:{vin}:{photos_hash}"


def cache_key_for_exchange_rate(from_currency: str, to_currency: str) -> str:
    """Generate cache key for exchange rate."""
    return f"exchange_rate:{from_currency}:{to_currency}"
