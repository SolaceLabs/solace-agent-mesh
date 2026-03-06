"""
Repository for Document Conversion Cache operations.

This repository handles persistence of cached PDF conversions from Office
documents (DOCX, PPTX, etc.) to avoid redundant LibreOffice conversions.
"""

import logging
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from .models.document_conversion_cache_model import DocumentConversionCacheModel
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms

log = logging.getLogger(__name__)


class DocumentConversionCacheRepository:
    """Repository for document conversion cache database operations."""

    def __init__(self):
        self.log_identifier = "[DocumentConversionCacheRepository]"

    def get_cached_pdf(
        self,
        db: DBSession,
        content_hash: str,
        file_extension: str,
    ) -> Optional[bytes]:
        """
        Get cached PDF by content hash and file extension.
        
        Updates access statistics (last_accessed_at, access_count) on cache hit
        to support LRU-like cleanup behavior. Uses atomic SQL increment to avoid
        race conditions when multiple requests access the same cache entry.
        
        Args:
            db: Database session
            content_hash: SHA-256 hex digest of the original document content
            file_extension: File extension (docx, pptx, etc.)
            
        Returns:
            Cached PDF bytes, or None if not cached
        """
        entry = db.query(DocumentConversionCacheModel).filter(
            DocumentConversionCacheModel.content_hash == content_hash,
            DocumentConversionCacheModel.file_extension == file_extension,
        ).first()
        
        if entry:
            # Get the PDF data before updating stats
            pdf_data = entry.pdf_data
            pdf_size = entry.pdf_size_bytes
            
            # Update access stats atomically using SQL increment
            # This prevents race conditions where concurrent reads could lose count updates
            db.query(DocumentConversionCacheModel).filter(
                DocumentConversionCacheModel.id == entry.id
            ).update({
                "last_accessed_at": now_epoch_ms(),
                "access_count": DocumentConversionCacheModel.access_count + 1,
            })
            
            log.debug(
                "%s Cache HIT for %s.%s (size: %d bytes)",
                self.log_identifier,
                content_hash[:16],
                file_extension,
                pdf_size,
            )
            
            return pdf_data
        
        log.debug(
            "%s Cache MISS for %s.%s",
            self.log_identifier,
            content_hash[:16],
            file_extension,
        )
        return None

    def cache_pdf(
        self,
        db: DBSession,
        content_hash: str,
        file_extension: str,
        original_size: int,
        pdf_data: bytes,
    ) -> bool:
        """
        Cache a converted PDF.
        
        Uses INSERT with conflict handling to avoid race conditions when
        multiple requests try to cache the same document simultaneously.
        
        Args:
            db: Database session
            content_hash: SHA-256 hex digest of the original document content
            file_extension: File extension (docx, pptx, etc.)
            original_size: Size of the original document in bytes
            pdf_data: Converted PDF content
            
        Returns:
            True if cached successfully, False if already cached (race condition)
        """
        current_time = now_epoch_ms()
        
        entry = DocumentConversionCacheModel(
            content_hash=content_hash,
            file_extension=file_extension,
            original_size_bytes=original_size,
            pdf_data=pdf_data,
            pdf_size_bytes=len(pdf_data),
            created_at=current_time,
            last_accessed_at=current_time,
            access_count=1,
        )
        
        try:
            db.add(entry)
            db.flush()  # Trigger constraint check
            
            log.info(
                "%s Cached PDF for %s.%s (original: %d bytes, pdf: %d bytes)",
                self.log_identifier,
                content_hash[:16],
                file_extension,
                original_size,
                len(pdf_data),
            )
            return True
            
        except IntegrityError:
            # Another request already cached this document (race condition)
            # This is expected and not an error
            db.rollback()
            log.debug(
                "%s Cache entry already exists for %s.%s (race condition)",
                self.log_identifier,
                content_hash[:16],
                file_extension,
            )
            return False

    def delete_cached_pdf(
        self,
        db: DBSession,
        content_hash: str,
        file_extension: str,
    ) -> bool:
        """
        Delete a cached PDF entry.
        
        Args:
            db: Database session
            content_hash: SHA-256 hex digest of the original document content
            file_extension: File extension (docx, pptx, etc.)
            
        Returns:
            True if deleted, False if not found
        """
        deleted = db.query(DocumentConversionCacheModel).filter(
            DocumentConversionCacheModel.content_hash == content_hash,
            DocumentConversionCacheModel.file_extension == file_extension,
        ).delete()
        
        if deleted > 0:
            log.debug(
                "%s Deleted cache entry for %s.%s",
                self.log_identifier,
                content_hash[:16],
                file_extension,
            )
        
        return deleted > 0

    def cleanup_old_entries(
        self,
        db: DBSession,
        older_than_ms: int,
    ) -> int:
        """
        Delete cache entries not accessed since the specified time.
        
        This implements LRU-like cleanup based on last_accessed_at timestamp.
        
        Args:
            db: Database session
            older_than_ms: Delete entries with last_accessed_at before this epoch time (ms)
            
        Returns:
            Number of entries deleted
        """
        deleted = db.query(DocumentConversionCacheModel).filter(
            DocumentConversionCacheModel.last_accessed_at < older_than_ms
        ).delete()
        
        if deleted > 0:
            log.info(
                "%s Cleaned up %d old cache entries (older than %d ms)",
                self.log_identifier,
                deleted,
                older_than_ms,
            )
        
        return deleted

    def get_stats(self, db: DBSession) -> dict:
        """
        Get cache statistics.
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with cache statistics:
            - cached_conversions: Number of cached entries
            - total_cached_bytes: Total size of cached PDFs
            - total_cache_hits: Sum of all access counts
            - oldest_entry_ms: Timestamp of oldest entry (by last_accessed_at)
            - newest_entry_ms: Timestamp of newest entry (by last_accessed_at)
        """
        stats = db.query(
            func.count(DocumentConversionCacheModel.id),
            func.sum(DocumentConversionCacheModel.pdf_size_bytes),
            func.sum(DocumentConversionCacheModel.access_count),
            func.min(DocumentConversionCacheModel.last_accessed_at),
            func.max(DocumentConversionCacheModel.last_accessed_at),
        ).first()
        
        return {
            "cached_conversions": stats[0] or 0,
            "total_cached_bytes": stats[1] or 0,
            "total_cache_hits": stats[2] or 0,
            "oldest_entry_ms": stats[3],
            "newest_entry_ms": stats[4],
        }

    def get_entry_count(self, db: DBSession) -> int:
        """
        Get the number of cached entries.
        
        Args:
            db: Database session
            
        Returns:
            Number of cached entries
        """
        return db.query(func.count(DocumentConversionCacheModel.id)).scalar() or 0
