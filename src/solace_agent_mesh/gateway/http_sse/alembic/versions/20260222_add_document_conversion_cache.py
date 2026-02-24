"""Add document conversion cache table for PDF caching

Revision ID: 20260222_doc_conv_cache
Revises: 20260207_sse_event_buffer
Create Date: 2026-02-22 00:00:00.000000

This migration adds a table to cache PDF conversions from Office documents
(DOCX, PPTX, XLSX, etc.) to avoid redundant document conversions.

Cache entries are keyed by content hash (SHA-256) and file extension,
allowing the same document uploaded by different users to share the
cached conversion.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260222_doc_conv_cache'
down_revision = '20260207_sse_event_buffer'
branch_labels = None
depends_on = None


def upgrade():
    """Add document conversion cache table."""
    
    # Create document_conversion_cache table
    op.create_table(
        'document_conversion_cache',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        # Cache key components
        sa.Column('content_hash', sa.String(64), nullable=False),  # SHA-256 hex digest
        sa.Column('file_extension', sa.String(10), nullable=False),  # docx, pptx, etc.
        # Original document metadata
        sa.Column('original_size_bytes', sa.BigInteger(), nullable=False),
        # Cached PDF data
        sa.Column('pdf_data', sa.LargeBinary(), nullable=False),
        sa.Column('pdf_size_bytes', sa.BigInteger(), nullable=False),
        # Timestamps (epoch milliseconds)
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('last_accessed_at', sa.BigInteger(), nullable=False),
        # Access statistics
        sa.Column('access_count', sa.BigInteger(), nullable=False, server_default=sa.text('1')),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create unique composite index for cache lookup
    # This ensures no duplicate entries for the same content + extension
    op.create_index(
        'ix_doc_conv_cache_lookup',
        'document_conversion_cache',
        ['content_hash', 'file_extension'],
        unique=True,
    )
    
    # Create index for cleanup queries (find old entries by last_accessed_at)
    op.create_index(
        'ix_doc_conv_cache_cleanup',
        'document_conversion_cache',
        ['last_accessed_at'],
    )


def downgrade():
    """Remove document conversion cache table."""
    
    # Remove indexes
    op.drop_index('ix_doc_conv_cache_cleanup', table_name='document_conversion_cache')
    op.drop_index('ix_doc_conv_cache_lookup', table_name='document_conversion_cache')
    
    # Drop table
    op.drop_table('document_conversion_cache')
