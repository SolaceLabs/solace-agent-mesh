"""
FastAPI router for document conversion endpoints.
Provides PPTX/DOCX to PDF conversion for preview rendering with database-backed caching.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..dependencies import get_user_id, ValidatedUserConfig, get_db_optional
from ..repository.document_conversion_cache_repository import DocumentConversionCacheRepository
from ..services.document_conversion_service import get_document_conversion_service

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

router = APIRouter()

# Rate limiting configuration
# Maximum concurrent conversions across all users
MAX_GLOBAL_CONCURRENT_CONVERSIONS = 5
# Each user can only have one conversion at a time
_global_conversion_semaphore = asyncio.Semaphore(MAX_GLOBAL_CONCURRENT_CONVERSIONS)
_user_conversion_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

# Maximum document size for conversion (5MB)
MAX_CONVERSION_SIZE_BYTES = 5 * 1024 * 1024

# Maximum PDF size to cache (10MB) - larger PDFs skip caching
MAX_CACHE_PDF_SIZE_BYTES = 10 * 1024 * 1024


def _compute_content_hash(content: bytes) -> str:
    """Compute SHA-256 hash of document content for cache key."""
    return hashlib.sha256(content).hexdigest()


def _get_file_extension(filename: str) -> str:
    """Extract lowercase file extension from filename."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


class ConversionRequest(BaseModel):
    """Request model for document conversion."""

    content: str = Field(..., description="Base64-encoded document content")
    filename: str = Field(..., description="Original filename with extension")


class ConversionResponse(BaseModel):
    """Response model for document conversion."""

    pdf_content: str = Field(..., alias="pdfContent", description="Base64-encoded PDF content")
    success: bool = Field(..., description="Whether conversion was successful")
    error: str | None = Field(None, description="Error message if conversion failed")

    model_config = {"populate_by_name": True}


class ConversionStatusResponse(BaseModel):
    """Response model for conversion service status."""

    available: bool = Field(..., description="Whether document conversion is available")
    supported_formats: list[str] = Field(
        ..., alias="supportedFormats", description="List of supported file extensions"
    )

    model_config = {"populate_by_name": True}


@router.get(
    "/status",
    response_model=ConversionStatusResponse,
    summary="Check Conversion Service Status",
    description="Check if document conversion service is available and what formats are supported.",
)
async def get_conversion_status():
    """
    Returns the status of the document conversion service.
    This endpoint does not require authentication to allow the frontend
    to check availability before attempting conversion.
    """
    service = get_document_conversion_service()
    return ConversionStatusResponse(
        available=service.is_available,
        supported_formats=service.get_supported_extensions(),
    )


@router.post(
    "/to-pdf",
    response_model=ConversionResponse,
    summary="Convert Document to PDF",
    description="Convert a PPTX, DOCX, or other Office document to PDF for preview. Results are cached to improve performance.",
)
async def convert_to_pdf(
    request: ConversionRequest,
    user_id: str = Depends(get_user_id),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:load"])),
    db: Optional[Session] = Depends(get_db_optional),
):
    """
    Converts a document to PDF format with caching support.

    The input document should be base64-encoded. The response will contain
    the converted PDF as a base64-encoded string.

    Caching:
    - Converted PDFs are cached in the database by content hash
    - Cache hits return immediately without invoking LibreOffice
    - Same document content shares cache regardless of filename or user

    Supported formats: PPTX, PPT, DOCX, DOC, XLSX, XLS, ODT, ODP, ODS
    
    Rate limiting:
    - Maximum 5 concurrent conversions globally
    - Each user can only have one conversion at a time
    """
    log_prefix = f"[DocumentConversion] User={user_id} -"
    log.info("%s Conversion request for: %s", log_prefix, request.filename)

    service = get_document_conversion_service()

    if not service.is_available:
        log.warning("%s Conversion service not available", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document conversion service is not available. LibreOffice is not installed on the server.",
        )

    if not service.is_format_supported(request.filename):
        log.warning("%s Unsupported format: %s", log_prefix, request.filename)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format. Supported formats: {', '.join(service.get_supported_extensions())}",
        )

    # Decode base64 content ONCE before any rate limiting
    try:
        binary_data = base64.b64decode(request.content)
    except Exception as e:
        log.warning("%s Invalid base64 content: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64-encoded content",
        )

    # Check size limit
    if len(binary_data) > MAX_CONVERSION_SIZE_BYTES:
        log.warning(
            "%s Document too large: %d bytes (max: %d)",
            log_prefix,
            len(binary_data),
            MAX_CONVERSION_SIZE_BYTES,
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Document too large. Maximum size: {MAX_CONVERSION_SIZE_BYTES / (1024 * 1024):.1f}MB",
        )

    # Compute cache key components
    content_hash = _compute_content_hash(binary_data)
    file_extension = _get_file_extension(request.filename)

    # Check cache BEFORE acquiring rate limiting locks
    # This allows cache hits to bypass the conversion queue entirely
    if db:
        try:
            cache_repo = DocumentConversionCacheRepository()
            cached_pdf = cache_repo.get_cached_pdf(db, content_hash, file_extension)
            
            if cached_pdf:
                log.info(
                    "%s Cache HIT for %s (hash: %s...)",
                    log_prefix,
                    request.filename,
                    content_hash[:16],
                )
                db.commit()  # Commit access stats update
                
                pdf_base64 = base64.b64encode(cached_pdf).decode("utf-8")
                return ConversionResponse(
                    pdf_content=pdf_base64,
                    success=True,
                    error=None,
                )
            
            log.debug(
                "%s Cache MISS for %s (hash: %s...)",
                log_prefix,
                request.filename,
                content_hash[:16],
            )
        except Exception as e:
            # Cache errors should not fail the request - just log and continue
            log.warning("%s Cache lookup error (continuing without cache): %s", log_prefix, e)
            try:
                db.rollback()
            except Exception:
                pass

    # Check rate limits before processing
    # Check if server is at global capacity
    if _global_conversion_semaphore.locked():
        log.warning("%s Server at capacity, rejecting conversion request", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server is currently processing maximum conversions. Please try again in a moment.",
        )

    # Check if user already has a conversion in progress
    user_lock = _user_conversion_locks[user_id]
    if user_lock.locked():
        log.warning("%s User already has conversion in progress", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You already have a conversion in progress. Please wait for it to complete.",
        )

    # Acquire rate limiting locks for actual conversion
    async with _global_conversion_semaphore:
        async with user_lock:
            try:
                # Perform conversion with binary data directly (no re-encoding)
                pdf_bytes, error = await service.convert_binary_to_pdf(
                    binary_data,
                    request.filename,
                )

                if error:
                    log.error("%s Conversion failed: %s", log_prefix, error)
                    return ConversionResponse(
                        pdf_content="",
                        success=False,
                        # Return generic error message to client (Fix: error leakage)
                        error="Document conversion failed. Please ensure the file is valid and try again.",
                    )

                # Cache the result if database is available and PDF is not too large
                if db and len(pdf_bytes) <= MAX_CACHE_PDF_SIZE_BYTES:
                    try:
                        cache_repo = DocumentConversionCacheRepository()
                        cache_repo.cache_pdf(
                            db,
                            content_hash,
                            file_extension,
                            len(binary_data),
                            pdf_bytes,
                        )
                        db.commit()
                        log.info(
                            "%s Cached conversion for %s (hash: %s..., pdf_size: %d bytes)",
                            log_prefix,
                            request.filename,
                            content_hash[:16],
                            len(pdf_bytes),
                        )
                    except Exception as e:
                        # Cache errors should not fail the request
                        log.warning("%s Failed to cache conversion: %s", log_prefix, e)
                        try:
                            db.rollback()
                        except Exception:
                            pass
                elif db and len(pdf_bytes) > MAX_CACHE_PDF_SIZE_BYTES:
                    log.debug(
                        "%s Skipping cache for %s: PDF too large (%d bytes > %d max)",
                        log_prefix,
                        request.filename,
                        len(pdf_bytes),
                        MAX_CACHE_PDF_SIZE_BYTES,
                    )

                # Encode result to base64 for response
                pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

                log.info(
                    "%s Successfully converted %s to PDF (%d bytes)",
                    log_prefix,
                    request.filename,
                    len(pdf_bytes),
                )

                return ConversionResponse(
                    pdf_content=pdf_base64,
                    success=True,
                    error=None,
                )

            except HTTPException:
                raise
            except Exception as e:
                # Log detailed error server-side for debugging
                log.exception("%s Unexpected error during conversion: %s", log_prefix, e)
                # Return generic error to client (Fix: error message leakage - security)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Document conversion failed. Please try again or contact support if the issue persists.",
                )


class CacheStatsResponse(BaseModel):
    """Response model for cache statistics."""

    available: bool = Field(..., description="Whether cache is available (database configured)")
    cached_conversions: int = Field(0, alias="cachedConversions", description="Number of cached entries")
    total_cached_bytes: int = Field(0, alias="totalCachedBytes", description="Total size of cached PDFs in bytes")
    total_cache_hits: int = Field(0, alias="totalCacheHits", description="Total number of cache hits")
    oldest_entry_ms: Optional[int] = Field(None, alias="oldestEntryMs", description="Timestamp of oldest entry (epoch ms)")
    newest_entry_ms: Optional[int] = Field(None, alias="newestEntryMs", description="Timestamp of newest entry (epoch ms)")

    model_config = {"populate_by_name": True}


@router.get(
    "/cache-stats",
    response_model=CacheStatsResponse,
    summary="Get Cache Statistics",
    description="Get statistics about the document conversion cache.",
)
async def get_cache_stats(
    db: Optional[Session] = Depends(get_db_optional),
):
    """
    Returns statistics about the document conversion cache.
    
    This endpoint is useful for monitoring cache effectiveness and
    planning cleanup/retention policies.
    """
    if not db:
        return CacheStatsResponse(
            available=False,
            cached_conversions=0,
            total_cached_bytes=0,
            total_cache_hits=0,
        )
    
    try:
        cache_repo = DocumentConversionCacheRepository()
        stats = cache_repo.get_stats(db)
        
        return CacheStatsResponse(
            available=True,
            cached_conversions=stats["cached_conversions"],
            total_cached_bytes=stats["total_cached_bytes"],
            total_cache_hits=stats["total_cache_hits"],
            oldest_entry_ms=stats["oldest_entry_ms"],
            newest_entry_ms=stats["newest_entry_ms"],
        )
    except Exception as e:
        log.warning("[DocumentConversion] Failed to get cache stats: %s", e)
        return CacheStatsResponse(
            available=False,
            cached_conversions=0,
            total_cached_bytes=0,
            total_cache_hits=0,
        )
