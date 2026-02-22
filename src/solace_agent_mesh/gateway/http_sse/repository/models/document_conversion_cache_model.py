"""
Document Conversion Cache SQLAlchemy model.

This model stores cached PDF conversions from Office documents (DOCX, PPTX, etc.)
to avoid redundant LibreOffice conversions for the same document content.

Cache entries are keyed by content hash (SHA-256) and file extension, allowing
the same document uploaded by different users to share the cached conversion.
"""

from sqlalchemy import BigInteger, Column, Index, Integer, LargeBinary, String

from .base import Base


class DocumentConversionCacheModel(Base):
    """SQLAlchemy model for document conversion cache entries."""

    __tablename__ = "document_conversion_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Cache key components
    content_hash = Column(String(64), nullable=False)  # SHA-256 hex digest
    file_extension = Column(String(10), nullable=False)  # docx, pptx, xlsx, etc.
    
    # Original document metadata
    original_size_bytes = Column(BigInteger, nullable=False)
    
    # Cached PDF data
    pdf_data = Column(LargeBinary, nullable=False)
    pdf_size_bytes = Column(BigInteger, nullable=False)
    
    # Timestamps (epoch milliseconds)
    created_at = Column(BigInteger, nullable=False)
    last_accessed_at = Column(BigInteger, nullable=False)
    
    # Access statistics
    access_count = Column(BigInteger, nullable=False, default=1)

    __table_args__ = (
        # Unique composite index for cache lookup
        Index(
            "ix_doc_conv_cache_lookup",
            "content_hash",
            "file_extension",
            unique=True,
        ),
        # Index for cleanup queries (find old entries)
        Index(
            "ix_doc_conv_cache_cleanup",
            "last_accessed_at",
        ),
    )

    def __repr__(self):
        return (
            f"<DocumentConversionCacheModel("
            f"id={self.id}, "
            f"content_hash={self.content_hash[:16]}..., "
            f"extension={self.file_extension}, "
            f"pdf_size={self.pdf_size_bytes}, "
            f"access_count={self.access_count}"
            f")>"
        )
