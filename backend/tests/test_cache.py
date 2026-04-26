import pytest
from backend.services.cache import InMemoryCache, cache_key_for_ai_analysis, cache_key_for_exchange_rate


def test_cache_set_get():
    cache = InMemoryCache()
    cache.set("test_key", {"data": "value"}, ttl_seconds=60)

    result = cache.get("test_key")
    assert result == {"data": "value"}


def test_cache_miss():
    cache = InMemoryCache()
    result = cache.get("nonexistent_key")
    assert result is None


def test_cache_expiration():
    cache = InMemoryCache()
    cache.set("test_key", "value", ttl_seconds=0)

    # Should be expired immediately
    result = cache.get("test_key")
    assert result is None


def test_cache_stats():
    cache = InMemoryCache()

    # Initial stats
    stats = cache.stats()
    assert stats["size"] == 0
    assert stats["hits"] == 0
    assert stats["misses"] == 0

    # Add item and hit
    cache.set("key1", "value1", ttl_seconds=60)
    cache.get("key1")

    stats = cache.stats()
    assert stats["size"] == 1
    assert stats["hits"] == 1
    assert stats["misses"] == 0

    # Miss
    cache.get("nonexistent")
    stats = cache.stats()
    assert stats["misses"] == 1


def test_cache_cleanup_expired():
    cache = InMemoryCache()

    # Add expired and valid items
    cache.set("expired", "value", ttl_seconds=0)
    cache.set("valid", "value", ttl_seconds=3600)

    cache.cleanup_expired()

    assert cache.get("expired") is None
    assert cache.get("valid") == "value"


def test_cache_key_for_ai_analysis():
    data = {"vin": "1HGBH41JXMN109186", "photos": ["url1", "url2"]}
    key1 = cache_key_for_ai_analysis(data)
    key2 = cache_key_for_ai_analysis(data)

    # Same data should produce same key
    assert key1 == key2

    # Different data should produce different key
    data2 = {"vin": "DIFFERENT_VIN", "photos": ["url1", "url2"]}
    key3 = cache_key_for_ai_analysis(data2)
    assert key1 != key3


def test_cache_key_for_exchange_rate():
    key1 = cache_key_for_exchange_rate("USD", "PLN")
    key2 = cache_key_for_exchange_rate("USD", "PLN")

    assert key1 == key2
    assert key1 == "exchange_rate:USD:PLN"
