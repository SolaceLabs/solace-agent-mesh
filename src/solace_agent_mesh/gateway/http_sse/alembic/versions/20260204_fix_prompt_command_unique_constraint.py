"""Fix prompt_groups command unique constraint to be per-user

Revision ID: 20260204_fix_command_constraint
Revises: 20251202_versioned_prompt_fields
Create Date: 2026-02-04

The original migration created a globally unique constraint on the 'command' column,
but commands should be unique per user, not globally. This allows different users
to have prompts with the same command name.

This migration:
1. Drops the global unique index on 'command'
2. Creates a composite unique constraint on (command, user_id)
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20260204_fix_command_constraint"
down_revision: str | Sequence[str] | None = "20251126_background_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Change command uniqueness from global to per-user."""
    
    # Drop the existing global unique index on command
    op.drop_index('ix_prompt_groups_command', table_name='prompt_groups')
    
    # Create a new composite unique index on (command, user_id)
    # This allows different users to have the same command
    op.create_index(
        'ix_prompt_groups_command_user_id',
        'prompt_groups',
        ['command', 'user_id'],
        unique=True
    )
    
    # Also create a non-unique index on command alone for query performance
    op.create_index(
        'ix_prompt_groups_command',
        'prompt_groups',
        ['command'],
        unique=False
    )


def downgrade() -> None:
    """Revert to global unique constraint on command."""
    
    # Drop the composite unique index
    op.drop_index('ix_prompt_groups_command_user_id', table_name='prompt_groups')
    
    # Drop the non-unique command index
    op.drop_index('ix_prompt_groups_command', table_name='prompt_groups')
    
    # Recreate the original global unique index
    # Note: This may fail if there are duplicate commands across users
    op.create_index(
        'ix_prompt_groups_command',
        'prompt_groups',
        ['command'],
        unique=True
    )
