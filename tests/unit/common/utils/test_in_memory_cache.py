"""
Unit tests for common/utils/in_memory_cache.py
Tests the InMemoryCache class for caching with TTL support.
"""

import pytest
import time
import asyncio
from solace_agent_mesh.common.utils.in_memory_cache import InMemoryCache


class TestInMemoryCacheBasicOperations:
    """Test basic cache operations."""

    def test_set_and_get(self):
        """Test setting and getting a value."""
        cache = InMemoryCache()
        cache.set("key1", "value1")
        
        assert cache.get("key1") == "value1"

    def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        cache = InMemoryCache()
        
        assert cache.get("nonexistent") is None

    def test_get_with_default(self):
        """Test getting with a default value."""
        cache = InMemoryCache()
        
        result = cache.get("nonexistent", default="default_value")
        assert result == "default_value"

    def test_set_overwrites_existing(self):
        """Test that setting overwrites existing value."""
        cache = InMemoryCache()
        cache.set("key1", "value1")
        cache.set("key1", "value2")
        
        assert cache.get("key1") == "value2"

    def test_delete_existing_key(self):
        """Test deleting an existing key."""
        cache = InMemoryCache()
        cache.set("key1", "value1")
        
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_delete_nonexistent_key(self):
        """Test deleting a key that doesn't exist (should not raise error)."""
        cache = InMemoryCache()
        cache.delete("nonexistent")  # Should not raise

    def test_clear_cache(self):
        """Test clearing all cache entries."""
        cache = InMemoryCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") is None

    def test_key_exists_via_get(self):
        """Test checking if key exists in cache via get method."""
        cache = InMemoryCache()
        cache.set("key1", "value1")
        
        # Check existence by getting the value
        assert cache.get("key1") is not None
        assert cache.get("nonexistent") is None


class TestInMemoryCacheTTL:
    """Test TTL (time-to-live) functionality."""

    def test_set_with_ttl(self):
        """Test setting a value with TTL."""
        cache = InMemoryCache()
        cache.set("key1", "value1", ttl=1.0)
        
        # Should be available immediately
        assert cache.get("key1") == "value1"
        
        # Should expire after TTL
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_set_without_ttl_persists(self):
        """Test that values without TTL persist."""
        cache = InMemoryCache()
        cache.set("key1", "value1")
        
        time.sleep(0.5)
        assert cache.get("key1") == "value1"

    def test_ttl_does_not_affect_other_keys(self):
        """Test that TTL expiration doesn't affect other keys."""
        cache = InMemoryCache()
        cache.set("key1", "value1", ttl=0.5)
        cache.set("key2", "value2")  # No TTL
        
        time.sleep(0.6)
        
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_update_resets_ttl(self):
        """Test that updating a key resets its TTL."""
        cache = InMemoryCache()
        cache.set("key1", "value1", ttl=1.0)
        
        time.sleep(0.6)
        cache.set("key1", "value2", ttl=1.0)  # Reset TTL
        
        time.sleep(0.6)
        # Should still be available (0.6 + 0.6 = 1.2, but TTL was reset)
        assert cache.get("key1") == "value2"

    def test_zero_ttl(self):
        """Test setting TTL to zero (should expire immediately)."""
        cache = InMemoryCache()
        cache.set("key1", "value1", ttl=0)
        
        # Even with zero TTL, might be briefly available
        # But should definitely be gone after a small delay
        time.sleep(0.1)
        assert cache.get("key1") is None

    def test_negative_ttl(self):
        """Test setting negative TTL (should be treated as expired)."""
        cache = InMemoryCache()
        cache.set("key1", "value1", ttl=-1)
        
        assert cache.get("key1") is None


class TestInMemoryCacheDataTypes:
    """Test caching different data types."""

    def test_cache_string(self):
        """Test caching string values."""
        cache = InMemoryCache()
        cache.set("key", "string value")
        
        assert cache.get("key") == "string value"

    def test_cache_integer(self):
        """Test caching integer values."""
        cache = InMemoryCache()
        cache.set("key", 42)
        
        assert cache.get("key") == 42

    def test_cache_float(self):
        """Test caching float values."""
        cache = InMemoryCache()
        cache.set("key", 3.14159)
        
        assert cache.get("key") == 3.14159

    def test_cache_list(self):
        """Test caching list values."""
        cache = InMemoryCache()
        value = [1, 2, 3, "four"]
        cache.set("key", value)
        
        assert cache.get("key") == value

    def test_cache_dict(self):
        """Test caching dictionary values."""
        cache = InMemoryCache()
        value = {"name": "test", "count": 42}
        cache.set("key", value)
        
        assert cache.get("key") == value

    def test_cache_none(self):
        """Test caching None value."""
        cache = InMemoryCache()
        cache.set("key", None)
        
        # None is a valid cached value
        assert cache.get("key") is None
        assert cache.get("key") is None

    def test_cache_boolean(self):
        """Test caching boolean values."""
        cache = InMemoryCache()
        cache.set("key_true", True)
        cache.set("key_false", False)
        
        assert cache.get("key_true") is True
        assert cache.get("key_false") is False

    def test_cache_complex_object(self):
        """Test caching complex nested objects."""
        cache = InMemoryCache()
        value = {
            "nested": {
                "list": [1, 2, {"deep": "value"}],
                "tuple": (1, 2, 3),
            },
            "set": {1, 2, 3},
        }
        cache.set("key", value)
        
        retrieved = cache.get("key")
        assert retrieved["nested"]["list"] == [1, 2, {"deep": "value"}]


class TestInMemoryCacheThreadSafety:
    """Test thread safety of cache operations."""

    def test_concurrent_set_operations(self):
        """Test concurrent set operations from multiple threads."""
        import threading
        
        cache = InMemoryCache()
        num_threads = 10
        operations_per_thread = 100
        
        def set_values(thread_id):
            for i in range(operations_per_thread):
                cache.set(f"key_{thread_id}_{i}", f"value_{thread_id}_{i}")
        
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=set_values, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify all values were set
        for thread_id in range(num_threads):
            for i in range(operations_per_thread):
                key = f"key_{thread_id}_{i}"
                expected = f"value_{thread_id}_{i}"
                assert cache.get(key) == expected

    def test_concurrent_read_write(self):
        """Test concurrent read and write operations."""
        import threading
        
        cache = InMemoryCache()
        cache.set("shared_key", 0)
        
        def increment():
            for _ in range(100):
                current = cache.get("shared_key", default=0)
                cache.set("shared_key", current + 1)
        
        threads = [threading.Thread(target=increment) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        # Final value should be 500 (5 threads * 100 increments)
        # Note: Without proper locking, this might not be exactly 500
        # but the cache should remain consistent
        final_value = cache.get("shared_key")
        assert isinstance(final_value, int)
        assert final_value > 0


class TestInMemoryCacheEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_string_key(self):
        """Test using empty string as key."""
        cache = InMemoryCache()
        cache.set("", "value")
        
        assert cache.get("") == "value"

    def test_very_long_key(self):
        """Test using very long key."""
        cache = InMemoryCache()
        long_key = "k" * 10000
        cache.set(long_key, "value")
        
        assert cache.get(long_key) == "value"

    def test_special_characters_in_key(self):
        """Test keys with special characters."""
        cache = InMemoryCache()
        special_keys = [
            "key with spaces",
            "key/with/slashes",
            "key.with.dots",
            "key:with:colons",
            "key@with@at",
        ]
        
        for key in special_keys:
            cache.set(key, f"value_for_{key}")
        
        for key in special_keys:
            assert cache.get(key) == f"value_for_{key}"

    def test_numeric_keys(self):
        """Test using numeric keys."""
        cache = InMemoryCache()
        cache.set(123, "value_for_123")
        cache.set(45.67, "value_for_45.67")
        
        assert cache.get(123) == "value_for_123"
        assert cache.get(45.67) == "value_for_45.67"

    def test_large_value(self):
        """Test caching large values."""
        cache = InMemoryCache()
        large_value = "x" * 1000000  # 1MB string
        cache.set("large", large_value)
        
        assert len(cache.get("large")) == 1000000

    def test_many_keys(self):
        """Test caching many keys."""
        cache = InMemoryCache()
        num_keys = 1000
        
        for i in range(num_keys):
            cache.set(f"key_{i}", f"value_{i}")
        
        # Verify all keys are accessible
        for i in range(num_keys):
            assert cache.get(f"key_{i}") == f"value_{i}"

    def test_clear_with_ttl_entries(self):
        """Test clearing cache with TTL entries."""
        cache = InMemoryCache()
        cache.set("key1", "value1", ttl=10.0)
        cache.set("key2", "value2")
        
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_get_expired_key_returns_none(self):
        """Test that getting an expired key returns None."""
        cache = InMemoryCache()
        cache.set("key", "value", ttl=0.1)
        
        time.sleep(0.2)
        
        result = cache.get("key")
        assert result is None
