"""Merge multiple migration heads

Revision ID: 20251103_merge_heads
Revises: default_agent_001, 20251029_prompt_tables
Create Date: 2025-11-03

This migration merges two separate migration branches:
- Branch 1: Projects and soft delete features (default_agent_001)
- Branch 2: Prompt library features (20251029_prompt_tables)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251103_merge_heads'
down_revision: Union[str, Sequence[str], None] = ('default_agent_001', '20251029_prompt_tables')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration - no schema changes needed."""
    pass


def downgrade() -> None:
    """Merge migration - no schema changes to revert."""
    pass