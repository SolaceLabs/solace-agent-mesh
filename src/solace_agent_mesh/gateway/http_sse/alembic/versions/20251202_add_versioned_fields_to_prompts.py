"""Add versioned metadata fields to prompts table

Revision ID: 20251202_versioned_prompt_fields
Revises: 20251115_add_parent_task_id
Create Date: 2025-12-02

This migration adds name, description, category, and command fields to the prompts table
to enable full versioning of all prompt metadata, not just the prompt_text content.
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20251202_versioned_prompt_fields"
down_revision: str | Sequence[str] | None = "20251115_add_parent_task_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add versioned metadata fields to prompts table."""
    
    # Add new columns to prompts table
    with op.batch_alter_table('prompts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('name', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('category', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('command', sa.String(length=50), nullable=True))
    
    # Migrate existing data: copy metadata from prompt_groups to prompts
    # This ensures existing prompt versions have the metadata from their group
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE prompts 
        SET name = pg.name,
            description = pg.description,
            category = pg.category,
            command = pg.command
        FROM prompt_groups pg
        WHERE prompts.group_id = pg.id
    """))


def downgrade() -> None:
    """Remove versioned metadata fields from prompts table."""
    
    with op.batch_alter_table('prompts', schema=None) as batch_op:
        batch_op.drop_column('command')
        batch_op.drop_column('category')
        batch_op.drop_column('description')
        batch_op.drop_column('name')