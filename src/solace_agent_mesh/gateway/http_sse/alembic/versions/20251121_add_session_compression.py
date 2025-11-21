"""Add session compression support

Revision ID: 20251121_add_session_compression
Revises: 20251121_update_account_type_free_to_basic
Create Date: 2025-11-21

"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20251121_add_session_compression"
down_revision: str | Sequence[str] | None = "20250121_token_usage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add compression support columns to sessions table."""
    # Add is_compression_branch column
    op.add_column(
        "sessions",
        sa.Column("is_compression_branch", sa.Boolean(), nullable=False, server_default="0")
    )
    
    # Add compression_metadata column
    op.add_column(
        "sessions",
        sa.Column("compression_metadata", sa.JSON(), nullable=True)
    )
    
    # Create index on is_compression_branch for efficient queries
    op.create_index(
        "idx_sessions_is_compression_branch",
        "sessions",
        ["is_compression_branch"],
        unique=False
    )


def downgrade() -> None:
    """Remove compression support columns from sessions table."""
    # Drop index
    op.drop_index("idx_sessions_is_compression_branch", table_name="sessions")
    
    # Drop columns
    op.drop_column("sessions", "compression_metadata")
    op.drop_column("sessions", "is_compression_branch")