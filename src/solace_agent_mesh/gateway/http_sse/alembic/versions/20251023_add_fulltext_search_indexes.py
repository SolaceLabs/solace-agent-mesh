"""Add full-text search indexes for chat search optimization (PostgreSQL only)

Revision ID: fts_indexes_001
Revises: soft_del_search_001
Create Date: 2025-10-23

This migration adds PostgreSQL full-text search (FTS) indexes to optimize
chat search performance. It creates GIN indexes on the user_message and
message_bubbles columns of the chat_tasks table.

Database Compatibility:
- PostgreSQL: Creates GIN indexes for full-text search (10-100x faster)
- SQLite: Skips index creation (uses ILIKE fallback in repository)

Performance Impact (PostgreSQL only):
- Search queries will be 10-100x faster
- Supports stemming (e.g., "running" matches "run", "ran")
- Enables relevance ranking
- Scales efficiently to millions of records

Index Details:
- Uses 'english' text search configuration
- GIN (Generalized Inverted Index) for fast lookups
- Automatically maintained by PostgreSQL
"""

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'fts_indexes_001'
down_revision = 'soft_del_search_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add GIN index for full-text search on session names (PostgreSQL only).

    Creates one index:
    1. idx_sessions_name_fts - For searching session names/titles

    Note: Chat content indexes removed - search is title-only.
    Silently skips index creation for non-PostgreSQL databases (e.g., SQLite).
    """
    # Get database connection and check dialect
    conn = op.get_bind()
    dialect_name = conn.dialect.name

    # Only create FTS index for PostgreSQL
    if dialect_name == 'postgresql':
        # Create GIN index for session name full-text search
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_name_fts
            ON sessions
            USING gin(to_tsvector('english', COALESCE(name, '')))
        """)
    # For SQLite and other databases, skip FTS index creation
    # The repository will automatically use ILIKE-based search instead


def downgrade() -> None:
    """
    Remove full-text search index (PostgreSQL only).

    Note: Downgrading will revert to slower ILIKE-based search.
    Silently skips for non-PostgreSQL databases.
    """
    conn = op.get_bind()
    dialect_name = conn.dialect.name

    if dialect_name == 'postgresql':
        op.execute("DROP INDEX IF EXISTS idx_sessions_name_fts")