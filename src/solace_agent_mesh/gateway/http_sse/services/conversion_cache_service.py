"""
Redis-based caching service for document conversions.
Provides shared cache across Kubernetes pods for converted PDFs.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

log = logging.getLogger(__name__)

# Default TTL for cached conversions (1 hour)
DEFAULT_CACHE_TTL_SECONDS = 3600

# Maximum size for cached PDFs (10MB) - larger files skip cache
DEFAULT_MAX_CACHE_SIZE_BYTES = 10 * 1024 * 1024

# Cache key prefix
CACHE_KEY_PREFIX = "sam:doc_conv:"


class ConversionCacheService:
    """
    Redis-based cache for document conversion results.
    
    Provides shared caching across Kubernetes pods to avoid redundant
    LibreOffice conversions for the same document.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        max_cache_size_bytes: int = DEFAULT_MAX_CACHE_SIZE_BYTES,
        enabled: bool = True,
    ):
        """
        Initialize the conversion cache service.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
            ttl_seconds: Time-to-live for cached conversions (default: 1 hour)
            max_cache_size_bytes: Maximum size for cached PDFs (default: 10MB)
            enabled: Whether caching is enabled (default: True)
        """
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self.max_cache_size_bytes = max_cache_size_bytes
        self.enabled = enabled and redis_url is not None
        self._redis: Optional["Redis"] = None
        self._available = False

        if not self.enabled:
            log.info(
                "ConversionCacheService disabled: %s",
                "no Redis URL configured" if not redis_url else "explicitly disabled",
            )
        else:
            log.info(
                "ConversionCacheService configured with Redis URL: %s (TTL: %ds)",
                self._mask_redis_url(redis_url),
                ttl_seconds,
            )

    @staticmethod
    def _mask_redis_url(url: str) -> str:
        """Mask password in Redis URL for logging."""
        if "@" in url:
            # Format: redis://user:password@host:port/db
            parts = url.split("@")
            prefix = parts[0].rsplit(":", 1)[0]  # Remove password
            return f"{prefix}:***@{parts[1]}"
        return url

    async def connect(self) -> bool:
        """
        Connect to Redis.
        
        Returns:
            True if connection successful, False otherwise.
        """
        if not self.enabled:
            return False

        try:
            import redis.asyncio as redis
            
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,  # We store binary data
                socket_connect_timeout=5,
                socket_timeout=10,
            )
            
            # Test connection
            await self._redis.ping()
            self._available = True
            log.info("ConversionCacheService connected to Redis successfully")
            return True
            
        except ImportError:
            log.warning(
                "ConversionCacheService: redis package not installed. "
                "Install with: pip install redis[hiredis]"
            )
            self._available = False
            return False
        except Exception as e:
            log.warning(
                "ConversionCacheService: Failed to connect to Redis: %s",
                e,
            )
            self._available = False
            return False

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self._available = False

    @property
    def is_available(self) -> bool:
        """Check if cache is available."""
        return self._available

    @staticmethod
    def _compute_cache_key(input_data: bytes, input_filename: str) -> str:
        """
        Compute cache key from document content and filename.
        
        Uses SHA-256 hash of content + filename extension for uniqueness.
        Different filenames with same content will share cache if same extension.
        """
        # Include file extension in hash to handle different output formats
        ext = input_filename.rsplit(".", 1)[-1].lower() if "." in input_filename else ""
        
        # Hash the content
        content_hash = hashlib.sha256(input_data).hexdigest()
        
        return f"{CACHE_KEY_PREFIX}{ext}:{content_hash}"

    async def get(
        self,
        input_data: bytes,
        input_filename: str,
    ) -> Optional[bytes]:
        """
        Get cached PDF conversion result.

        Args:
            input_data: Original document content
            input_filename: Original filename

        Returns:
            Cached PDF bytes, or None if not cached
        """
        if not self._available:
            return None

        try:
            cache_key = self._compute_cache_key(input_data, input_filename)
            cached_pdf = await self._redis.get(cache_key)
            
            if cached_pdf:
                log.debug(
                    "Cache HIT for %s (key: %s, size: %d bytes)",
                    input_filename,
                    cache_key[:50],
                    len(cached_pdf),
                )
                # Refresh TTL on cache hit (LRU-like behavior)
                await self._redis.expire(cache_key, self.ttl_seconds)
                return cached_pdf
            else:
                log.debug("Cache MISS for %s (key: %s)", input_filename, cache_key[:50])
                return None

        except Exception as e:
            log.warning("Cache get error for %s: %s", input_filename, e)
            return None

    async def set(
        self,
        input_data: bytes,
        input_filename: str,
        pdf_data: bytes,
    ) -> bool:
        """
        Cache a PDF conversion result.

        Args:
            input_data: Original document content
            input_filename: Original filename
            pdf_data: Converted PDF content

        Returns:
            True if cached successfully, False otherwise
        """
        if not self._available:
            return False

        # Skip caching for large PDFs
        if len(pdf_data) > self.max_cache_size_bytes:
            log.debug(
                "Skipping cache for %s: PDF too large (%d bytes > %d max)",
                input_filename,
                len(pdf_data),
                self.max_cache_size_bytes,
            )
            return False

        try:
            cache_key = self._compute_cache_key(input_data, input_filename)
            
            await self._redis.setex(
                cache_key,
                self.ttl_seconds,
                pdf_data,
            )
            
            log.debug(
                "Cache SET for %s (key: %s, size: %d bytes, TTL: %ds)",
                input_filename,
                cache_key[:50],
                len(pdf_data),
                self.ttl_seconds,
            )
            return True

        except Exception as e:
            log.warning("Cache set error for %s: %s", input_filename, e)
            return False

    async def delete(
        self,
        input_data: bytes,
        input_filename: str,
    ) -> bool:
        """
        Delete a cached conversion.

        Args:
            input_data: Original document content
            input_filename: Original filename

        Returns:
            True if deleted, False otherwise
        """
        if not self._available:
            return False

        try:
            cache_key = self._compute_cache_key(input_data, input_filename)
            deleted = await self._redis.delete(cache_key)
            return deleted > 0
        except Exception as e:
            log.warning("Cache delete error for %s: %s", input_filename, e)
            return False

    async def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats (keys_count, memory_used, etc.)
        """
        if not self._available:
            return {"available": False}

        try:
            # Count keys with our prefix
            cursor = 0
            key_count = 0
            total_size = 0
            
            while True:
                cursor, keys = await self._redis.scan(
                    cursor,
                    match=f"{CACHE_KEY_PREFIX}*",
                    count=100,
                )
                key_count += len(keys)
                
                # Get sizes of keys (batch to avoid N+1)
                if keys:
                    for key in keys:
                        try:
                            size = await self._redis.strlen(key)
                            total_size += size
                        except Exception:
                            pass
                
                if cursor == 0:
                    break

            return {
                "available": True,
                "cached_conversions": key_count,
                "total_cached_bytes": total_size,
                "ttl_seconds": self.ttl_seconds,
                "max_cache_size_bytes": self.max_cache_size_bytes,
            }

        except Exception as e:
            log.warning("Cache stats error: %s", e)
            return {"available": True, "error": str(e)}


# Singleton instance
_cache_service: Optional[ConversionCacheService] = None


def get_conversion_cache_service(
    redis_url: Optional[str] = None,
    ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    max_cache_size_bytes: int = DEFAULT_MAX_CACHE_SIZE_BYTES,
    enabled: bool = True,
) -> ConversionCacheService:
    """
    Get or create the conversion cache service singleton.

    Args:
        redis_url: Redis connection URL
        ttl_seconds: Cache TTL in seconds (default: 1 hour)
        max_cache_size_bytes: Maximum cached PDF size (default: 10MB)
        enabled: Whether caching is enabled

    Returns:
        ConversionCacheService instance
    """
    global _cache_service
    if _cache_service is None:
        _cache_service = ConversionCacheService(
            redis_url=redis_url,
            ttl_seconds=ttl_seconds,
            max_cache_size_bytes=max_cache_size_bytes,
            enabled=enabled,
        )
    return _cache_service


async def initialize_cache_service(
    redis_url: Optional[str] = None,
    ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    max_cache_size_bytes: int = DEFAULT_MAX_CACHE_SIZE_BYTES,
    enabled: bool = True,
) -> ConversionCacheService:
    """
    Initialize and connect the conversion cache service.

    Args:
        redis_url: Redis connection URL
        ttl_seconds: Cache TTL in seconds
        max_cache_size_bytes: Maximum cached PDF size
        enabled: Whether caching is enabled

    Returns:
        Connected ConversionCacheService instance
    """
    service = get_conversion_cache_service(
        redis_url=redis_url,
        ttl_seconds=ttl_seconds,
        max_cache_size_bytes=max_cache_size_bytes,
        enabled=enabled,
    )
    await service.connect()
    return service
