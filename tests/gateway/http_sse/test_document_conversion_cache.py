"""
Integration tests for document conversion cache functionality.

These tests verify the caching behavior for document conversion using
an in-memory SQLite database to test actual database operations.
"""

import base64
import hashlib
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from solace_agent_mesh.gateway.http_sse.repository.models import Base
from solace_agent_mesh.gateway.http_sse.repository.models.document_conversion_cache_model import (
    DocumentConversionCacheModel,
)
from solace_agent_mesh.gateway.http_sse.repository.document_conversion_cache_repository import (
    DocumentConversionCacheRepository,
)
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def compute_content_hash(content: bytes, file_extension: str) -> str:
    """Compute SHA-256 hash of content combined with file extension."""
    hasher = hashlib.sha256()
    hasher.update(content)
    hasher.update(file_extension.encode("utf-8"))
    return hasher.hexdigest()


class TestDocumentConversionCacheModel:
    """Tests for the DocumentConversionCacheModel."""

    def test_model_creation(self, db_session):
        """Test that cache entries can be created and persisted."""
        content_hash = compute_content_hash(b"test content", ".docx")
        pdf_data = b"%PDF-1.4 test pdf content"
        current_time = now_epoch_ms()

        cache_entry = DocumentConversionCacheModel(
            content_hash=content_hash,
            file_extension=".docx",
            pdf_data=pdf_data,
            original_size_bytes=len(b"test content"),
            pdf_size_bytes=len(pdf_data),
            created_at=current_time,
            last_accessed_at=current_time,
            access_count=1,
        )

        db_session.add(cache_entry)
        db_session.commit()

        # Verify the entry was persisted
        retrieved = db_session.query(DocumentConversionCacheModel).filter_by(
            content_hash=content_hash
        ).first()

        assert retrieved is not None
        assert retrieved.content_hash == content_hash
        assert retrieved.file_extension == ".docx"
        assert retrieved.pdf_data == pdf_data
        assert retrieved.original_size_bytes == len(b"test content")
        assert retrieved.pdf_size_bytes == len(pdf_data)
        assert retrieved.access_count == 1
        assert retrieved.created_at == current_time
        assert retrieved.last_accessed_at == current_time

    def test_model_repr(self, db_session):
        """Test the string representation of the model."""
        content_hash = "abc123def456789012345678901234567890123456789012345678901234"
        current_time = now_epoch_ms()
        cache_entry = DocumentConversionCacheModel(
            content_hash=content_hash,
            file_extension=".pptx",
            pdf_data=b"pdf",
            original_size_bytes=100,
            pdf_size_bytes=50,
            created_at=current_time,
            last_accessed_at=current_time,
            access_count=1,
        )

        repr_str = repr(cache_entry)
        assert "DocumentConversionCacheModel" in repr_str
        assert content_hash[:16] in repr_str
        assert ".pptx" in repr_str


class TestDocumentConversionCacheRepository:
    """Tests for the DocumentConversionCacheRepository."""

    def test_cache_and_retrieve_pdf(self, db_session):
        """Test caching a PDF and retrieving it."""
        repo = DocumentConversionCacheRepository()
        
        original_content = b"This is a test DOCX file content"
        pdf_content = b"%PDF-1.4 converted pdf content here"
        file_extension = ".docx"
        content_hash = compute_content_hash(original_content, file_extension)

        # Cache the PDF
        repo.cache_pdf(
            db=db_session,
            content_hash=content_hash,
            file_extension=file_extension,
            pdf_data=pdf_content,
            original_size=len(original_content),
        )
        db_session.commit()

        # Retrieve the cached PDF
        cached_pdf = repo.get_cached_pdf(db_session, content_hash, file_extension)
        db_session.commit()

        assert cached_pdf is not None
        assert cached_pdf == pdf_content

    def test_cache_miss_returns_none(self, db_session):
        """Test that cache miss returns None."""
        repo = DocumentConversionCacheRepository()

        result = repo.get_cached_pdf(db_session, "nonexistent_hash", ".docx")

        assert result is None

    def test_access_count_increments(self, db_session):
        """Test that access count increments on cache hits."""
        repo = DocumentConversionCacheRepository()
        
        content_hash = "test_hash_123_" + "0" * 50
        file_extension = ".docx"
        pdf_content = b"pdf content"

        # Cache the PDF
        repo.cache_pdf(
            db=db_session,
            content_hash=content_hash,
            file_extension=file_extension,
            pdf_data=pdf_content,
            original_size=100,
        )
        db_session.commit()

        # Access it multiple times
        for i in range(3):
            repo.get_cached_pdf(db_session, content_hash, file_extension)
            db_session.commit()

        # Check access count
        entry = db_session.query(DocumentConversionCacheModel).filter_by(
            content_hash=content_hash
        ).first()

        assert entry.access_count == 4  # 1 initial + 3 accesses

    def test_last_accessed_at_updates(self, db_session):
        """Test that last_accessed_at updates on cache hits."""
        repo = DocumentConversionCacheRepository()
        
        content_hash = "test_hash_456_" + "0" * 50
        file_extension = ".pptx"

        # Cache the PDF
        repo.cache_pdf(
            db=db_session,
            content_hash=content_hash,
            file_extension=file_extension,
            pdf_data=b"pdf",
            original_size=50,
        )
        db_session.commit()

        # Get initial last_accessed_at
        entry = db_session.query(DocumentConversionCacheModel).filter_by(
            content_hash=content_hash
        ).first()
        initial_access_time = entry.last_accessed_at

        # Access the cache
        repo.get_cached_pdf(db_session, content_hash, file_extension)
        db_session.commit()

        # Refresh and check
        db_session.refresh(entry)
        assert entry.last_accessed_at >= initial_access_time

    def test_different_extensions_cached_separately(self, db_session):
        """Test that same content with different extensions is cached separately."""
        repo = DocumentConversionCacheRepository()
        
        content = b"same content"
        pdf_docx = b"pdf from docx"
        pdf_pptx = b"pdf from pptx"

        hash_docx = compute_content_hash(content, ".docx")
        hash_pptx = compute_content_hash(content, ".pptx")

        # Cache both
        repo.cache_pdf(db_session, hash_docx, ".docx", len(content), pdf_docx)
        repo.cache_pdf(db_session, hash_pptx, ".pptx", len(content), pdf_pptx)
        db_session.commit()

        # Retrieve both
        cached_docx = repo.get_cached_pdf(db_session, hash_docx, ".docx")
        cached_pptx = repo.get_cached_pdf(db_session, hash_pptx, ".pptx")

        assert cached_docx == pdf_docx
        assert cached_pptx == pdf_pptx
        assert cached_docx != cached_pptx

    def test_delete_cached_pdf(self, db_session):
        """Test deleting a cached PDF."""
        repo = DocumentConversionCacheRepository()
        
        content_hash = "delete_test_hash_" + "0" * 47
        file_extension = ".docx"

        # Cache and then delete
        repo.cache_pdf(db_session, content_hash, file_extension, 100, b"pdf")
        db_session.commit()
        
        deleted = repo.delete_cached_pdf(db_session, content_hash, file_extension)
        db_session.commit()

        assert deleted is True

        # Verify it's gone
        result = repo.get_cached_pdf(db_session, content_hash, file_extension)
        assert result is None

    def test_delete_nonexistent_returns_false(self, db_session):
        """Test that deleting nonexistent entry returns False."""
        repo = DocumentConversionCacheRepository()

        deleted = repo.delete_cached_pdf(db_session, "nonexistent", ".docx")

        assert deleted is False

    def test_cleanup_old_entries(self, db_session):
        """Test cleanup of old cache entries."""
        repo = DocumentConversionCacheRepository()

        # Create an old entry by manually setting last_accessed_at
        old_time = now_epoch_ms() - (48 * 60 * 60 * 1000)  # 48 hours ago
        old_entry = DocumentConversionCacheModel(
            content_hash="old_hash_" + "0" * 55,
            file_extension=".docx",
            pdf_data=b"old pdf",
            original_size_bytes=100,
            pdf_size_bytes=50,
            created_at=old_time,
            last_accessed_at=old_time,
            access_count=1,
        )
        db_session.add(old_entry)
        db_session.commit()

        # Create a recent entry
        repo.cache_pdf(db_session, "recent_hash_" + "0" * 52, ".docx", 100, b"recent pdf")
        db_session.commit()

        # Cleanup entries older than 24 hours
        cutoff_ms = now_epoch_ms() - (24 * 60 * 60 * 1000)
        deleted_count = repo.cleanup_old_entries(db_session, cutoff_ms)
        db_session.commit()

        assert deleted_count == 1

        # Verify old entry is gone, recent entry remains
        assert repo.get_cached_pdf(db_session, "old_hash_" + "0" * 55, ".docx") is None
        assert repo.get_cached_pdf(db_session, "recent_hash_" + "0" * 52, ".docx") is not None

    def test_get_stats(self, db_session):
        """Test getting cache statistics."""
        repo = DocumentConversionCacheRepository()

        # Add some entries
        repo.cache_pdf(db_session, "hash1_" + "0" * 58, ".docx", 500, b"pdf1" * 100)
        repo.cache_pdf(db_session, "hash2_" + "0" * 58, ".pptx", 1000, b"pdf2" * 200)
        db_session.commit()

        # Access one entry
        repo.get_cached_pdf(db_session, "hash1_" + "0" * 58, ".docx")
        db_session.commit()

        stats = repo.get_stats(db_session)

        assert stats["cached_conversions"] == 2
        assert stats["total_cached_bytes"] > 0
        assert stats["total_cache_hits"] == 3  # 2 initial + 1 access

    def test_duplicate_cache_entry_handled(self, db_session):
        """Test that duplicate cache entries are handled gracefully."""
        repo = DocumentConversionCacheRepository()
        
        content_hash = "duplicate_hash_" + "0" * 50
        file_extension = ".docx"

        # Cache the same content twice
        result1 = repo.cache_pdf(db_session, content_hash, file_extension, 100, b"pdf1")
        db_session.commit()
        
        result2 = repo.cache_pdf(db_session, content_hash, file_extension, 100, b"pdf2")
        # Note: result2 should be False due to IntegrityError handling

        # Should not raise an error, and one entry should exist
        count = db_session.query(DocumentConversionCacheModel).filter_by(
            content_hash=content_hash
        ).count()

        assert count == 1
        assert result1 is True
        assert result2 is False


class TestCacheIntegration:
    """Integration tests for the full caching workflow."""

    def test_full_cache_workflow(self, db_session):
        """Test the complete cache workflow: miss -> store -> hit."""
        repo = DocumentConversionCacheRepository()

        # Simulate document content
        document_content = b"This is a PowerPoint presentation content"
        file_extension = ".pptx"
        content_hash = compute_content_hash(document_content, file_extension)

        # Step 1: Cache miss
        cached = repo.get_cached_pdf(db_session, content_hash, file_extension)
        assert cached is None

        # Step 2: "Convert" and cache (simulated)
        converted_pdf = b"%PDF-1.4 converted presentation"
        repo.cache_pdf(
            db=db_session,
            content_hash=content_hash,
            file_extension=file_extension,
            pdf_data=converted_pdf,
            original_size=len(document_content),
        )
        db_session.commit()

        # Step 3: Cache hit
        cached = repo.get_cached_pdf(db_session, content_hash, file_extension)
        db_session.commit()
        assert cached == converted_pdf

        # Step 4: Verify stats
        stats = repo.get_stats(db_session)
        assert stats["cached_conversions"] == 1
        assert stats["total_cache_hits"] == 2  # 1 initial + 1 access

    def test_base64_content_caching(self, db_session):
        """Test caching with base64-encoded content (as used in the API)."""
        repo = DocumentConversionCacheRepository()

        # Simulate base64-encoded document
        original_bytes = b"Document content here"
        base64_content = base64.b64encode(original_bytes).decode("utf-8")
        
        # Decode and hash (as the router does)
        decoded_content = base64.b64decode(base64_content)
        file_extension = ".docx"
        content_hash = compute_content_hash(decoded_content, file_extension)

        # Cache the converted PDF
        pdf_content = b"%PDF-1.4 converted document"
        repo.cache_pdf(db_session, content_hash, file_extension, len(decoded_content), pdf_content)
        db_session.commit()

        # Retrieve using the same hash
        cached = repo.get_cached_pdf(db_session, content_hash, file_extension)
        assert cached == pdf_content

    def test_large_document_caching(self, db_session):
        """Test caching of larger documents."""
        repo = DocumentConversionCacheRepository()

        # Simulate a larger document (1MB)
        large_content = b"x" * (1024 * 1024)
        large_pdf = b"%PDF-1.4 " + (b"y" * (1024 * 1024))
        
        content_hash = compute_content_hash(large_content, ".docx")

        # Cache and retrieve
        repo.cache_pdf(db_session, content_hash, ".docx", len(large_content), large_pdf)
        db_session.commit()
        
        cached = repo.get_cached_pdf(db_session, content_hash, ".docx")

        assert cached == large_pdf
        assert len(cached) > 1024 * 1024
