"""Unified migration for initial schema

Revision ID: d5b3f8f2e9a0
Revises:
Create Date: 2025-07-31 17:21:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d5b3f8f2e9a0"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial schema with dialect-specific handling."""
    bind = op.get_bind()

    if bind.dialect.name == 'mysql':
        _upgrade_mysql()
    else:
        _upgrade_standard()


def _upgrade_standard() -> None:
    """Standard upgrade for PostgreSQL and SQLite (original working code)."""
    # Create sessions table without foreign key constraint
    # user_id is kept as a simple string field for tracking ownership
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create chat_messages table with CASCADE constraint and correct schema
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),  # Keep as 'message' for now to match current schema
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("sender_type", sa.String(), nullable=True),
        sa.Column("sender_name", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def _upgrade_mysql() -> None:
    """MySQL upgrade with required VARCHAR lengths."""
    # Create sessions table without foreign key constraint
    # user_id is kept as a simple string field for tracking ownership
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), nullable=False),  # UUID
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("user_id", sa.String(36), nullable=False),  # UUID
        sa.Column("agent_id", sa.String(36), nullable=True),  # UUID
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create chat_messages table with CASCADE constraint and correct schema
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(36), nullable=False),  # UUID
        sa.Column("session_id", sa.String(36), nullable=False),  # UUID
        sa.Column("message", sa.Text(), nullable=False),  # Keep as 'message' for now to match current schema
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("sender_type", sa.String(50), nullable=True),
        sa.Column("sender_name", sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade works the same for all dialects."""
    op.drop_table("chat_messages")
    op.drop_table("sessions")
