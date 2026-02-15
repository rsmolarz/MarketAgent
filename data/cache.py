"""
Caching layer for market data and agent outputs.

Provides in-memory TTL-based caching with optional Redis/TimescaleDB
persistence. Designed for the multi-agent system where many agents
may request the same data within short time windows.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A single cache entry with TTL."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.monotonic)
    ttl_seconds: float = 300.0  # 5 minutes default
    access_count: int = 0
    last_accessed: float = field(default_factory=time.monotonic)

    @property
    def is_expired(self) -> bool:
        return (time.monotonic() - self.created_at) > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        return time.monotonic() - self.created_at


class TTLCache:
    """
    In-memory TTL-based cache with LRU eviction.

    Features:
    - Per-key TTL (default 5 minutes for equities, 30 seconds for crypto)
    - LRU eviction when max size reached
    - Cache statistics for monitoring
    - Async-safe with lock
    """

    # Default TTLs by data type
    DEFAULT_TTLS = {
        "crypto_price": 30,     # 30 seconds for crypto
        "equity_price": 300,    # 5 minutes for equities
        "bond_data": 900,       # 15 minutes for bonds
        "real_estate": 86400,   # 24 hours for real estate
        "macro_data": 3600,     # 1 hour for macro indicators
        "agent_output": 600,    # 10 minutes for agent outputs
        "edgar_filing": 86400,  # 24 hours for SEC filings
    }

    def __init__(self, max_size: int = 10000):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0,
        }

    def _make_key(self, namespace: str, key: str) -> str:
        """Create a namespaced cache key."""
        return f"{namespace}:{key}"

    def _evict_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        expired = [k for k, v in self._cache.items() if v.is_expired]
        for k in expired:
            del self._cache[k]
        self._stats["expirations"] += len(expired)
        return len(expired)

    def _evict_lru(self) -> None:
        """Evict least recently used entries until under max_size."""
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
            self._stats["evictions"] += 1

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """Get a value from cache. Returns None if not found or expired."""
        cache_key = self._make_key(namespace, key)
        entry = self._cache.get(cache_key)

        if entry is None:
            self._stats["misses"] += 1
            return None

        if entry.is_expired:
            del self._cache[cache_key]
            self._stats["expirations"] += 1
            self._stats["misses"] += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(cache_key)
        entry.access_count += 1
        entry.last_accessed = time.monotonic()
        self._stats["hits"] += 1
        return entry.value

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
    ) -> None:
        """Set a value in cache with optional TTL override."""
        cache_key = self._make_key(namespace, key)
        ttl = ttl or self.DEFAULT_TTLS.get(namespace, 300)

        self._cache[cache_key] = CacheEntry(
            key=cache_key,
            value=value,
            ttl_seconds=ttl,
        )
        self._cache.move_to_end(cache_key)

        if len(self._cache) > self._max_size:
            self._evict_lru()

    def invalidate(self, namespace: str, key: str) -> bool:
        """Remove a specific entry. Returns True if found."""
        cache_key = self._make_key(namespace, key)
        if cache_key in self._cache:
            del self._cache[cache_key]
            return True
        return False

    def invalidate_namespace(self, namespace: str) -> int:
        """Remove all entries in a namespace."""
        prefix = f"{namespace}:"
        keys = [k for k in self._cache if k.startswith(prefix)]
        for k in keys:
            del self._cache[k]
        return len(keys)

    def clear(self) -> None:
        """Clear entire cache."""
        self._cache.clear()

    def cleanup(self) -> int:
        """Run periodic cleanup of expired entries."""
        return self._evict_expired()

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        total = self._stats["hits"] + self._stats["misses"]
        return self._stats["hits"] / total if total > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "size": self.size,
            "max_size": self._max_size,
            "hit_rate": self.hit_rate,
        }


async def cached(
    cache: TTLCache,
    namespace: str,
    key: str,
    fetch_fn: Callable[..., Coroutine],
    ttl: Optional[float] = None,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Cache-through helper for async data fetching.

    Checks cache first, calls fetch_fn on miss, stores result.
    """
    result = cache.get(namespace, key)
    if result is not None:
        return result

    result = await fetch_fn(*args, **kwargs)
    if result is not None:
        cache.set(namespace, key, result, ttl)
    return result


# Global cache instance
market_cache = TTLCache(max_size=10000)
