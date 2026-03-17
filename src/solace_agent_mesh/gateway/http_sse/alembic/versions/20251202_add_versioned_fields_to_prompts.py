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

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = {col['name'] for col in inspector.get_columns('prompts')}

    # Add new columns only if they don't exist (idempotency for corrupted databases)
    columns_to_add = {
        'name': sa.Column('name', sa.String(length=255), nullable=True),
        'description': sa.Column('description', sa.Text(), nullable=True),
        'category': sa.Column('category', sa.String(length=100), nullable=True),
        'command': sa.Column('command', sa.String(length=50), nullable=True)
    }

    columns_needing_addition = [
        (col_name, col_def)
        for col_name, col_def in columns_to_add.items()
        if col_name not in existing_columns
    ]

    if columns_needing_addition:
        with op.batch_alter_table('prompts', schema=None) as batch_op:
            for col_name, col_def in columns_needing_addition:
                batch_op.add_column(col_def)

        # Migrate existing data: copy metadata from prompt_groups to prompts
        # This ensures existing prompt versions have the metadata from their group
        #
        # Using dialect-agnostic subquery approach (works on SQLite and PostgreSQL)
        connection.execute(sa.text("""
            UPDATE prompts
            SET name = (SELECT name FROM prompt_groups WHERE id = prompts.group_id),
                description = (SELECT description FROM prompt_groups WHERE id = prompts.group_id),
                category = (SELECT category FROM prompt_groups WHERE id = prompts.group_id),
                command = (SELECT command FROM prompt_groups WHERE id = prompts.group_id)
            WHERE group_id IS NOT NULL
        """))


def downgrade() -> None:
    """Remove versioned metadata fields from prompts table."""

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = {col['name'] for col in inspector.get_columns('prompts')}

    # Only drop columns that exist (idempotency for partial downgrade failures)
    columns_to_drop = ['command', 'category', 'description', 'name']
    columns_needing_removal = [
        col_name for col_name in columns_to_drop
        if col_name in existing_columns
    ]

    if columns_needing_removal:
        with op.batch_alter_table('prompts', schema=None) as batch_op:
            for col_name in columns_needing_removal:
                batch_op.drop_column(col_name)