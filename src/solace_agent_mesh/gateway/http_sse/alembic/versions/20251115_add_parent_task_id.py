"""Add parent_task_id to tasks table

Revision ID: 20251115_add_parent_task_id
Revises: 20251108_prompt_tables_complete
Create Date: 2025-11-15

"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20251115_add_parent_task_id"
down_revision: str | Sequence[str] | None = "20251108_prompt_tables_complete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add parent_task_id column to tasks table for efficient task hierarchy queries."""
    bind = op.get_bind()

    if bind.dialect.name == 'mysql':
        _upgrade_mysql()
    else:
        _upgrade_standard()


def _upgrade_standard() -> None:
    """Standard upgrade for PostgreSQL and SQLite (original working code)."""
    op.add_column(
        "tasks", sa.Column("parent_task_id", sa.String(), nullable=True)
    )
    op.create_index(
        "ix_tasks_parent_task_id", "tasks", ["parent_task_id"], unique=False
    )


def _upgrade_mysql() -> None:
    """MySQL upgrade with required VARCHAR lengths."""
    op.add_column(
        "tasks", sa.Column("parent_task_id", sa.String(36), nullable=True)  # UUID
    )
    op.create_index(
        "ix_tasks_parent_task_id", "tasks", ["parent_task_id"], unique=False
    )


def downgrade() -> None:
    """Remove parent_task_id column from tasks table."""
    op.drop_index("ix_tasks_parent_task_id", table_name="tasks")
    op.drop_column("tasks", "parent_task_id")
