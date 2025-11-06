"""add prompt pinning support

Revision ID: 20251106_prompt_pinning
Revises: 20251103_merge_heads
Create Date: 2025-11-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20251106_prompt_pinning"
down_revision: str | Sequence[str] | None = "20251103_merge_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add is_pinned column to prompt_groups table."""
    
    # Add is_pinned column with default False (0 for SQLite)
    with op.batch_alter_table('prompt_groups', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default='0')
        )
    
    # Clean up any existing string 'false' values to integer 0
    op.execute("UPDATE prompt_groups SET is_pinned = 0 WHERE is_pinned = 'false'")
    op.execute("UPDATE prompt_groups SET is_pinned = 1 WHERE is_pinned = 'true'")
    
    # Create index for efficient querying of pinned prompts
    op.create_index('ix_prompt_groups_is_pinned', 'prompt_groups', ['is_pinned'], unique=False)


def downgrade() -> None:
    """Remove is_pinned column from prompt_groups table."""
    
    # Drop index
    op.drop_index('ix_prompt_groups_is_pinned', table_name='prompt_groups')
    
    # Drop column
    with op.batch_alter_table('prompt_groups', schema=None) as batch_op:
        batch_op.drop_column('is_pinned')