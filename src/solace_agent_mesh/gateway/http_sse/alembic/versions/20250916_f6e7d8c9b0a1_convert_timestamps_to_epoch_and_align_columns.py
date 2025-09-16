"""Convert timestamps to epoch milliseconds and align column names

Revision ID: b1c2d3e4f5g6
Revises: b1c2d3e4f5g6
Create Date: 2025-09-16 16:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6e7d8c9b0a1"
down_revision: str | None = "d5b3f8f2e9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Convert datetime columns to epoch milliseconds and rename columns."""

    # For sessions table: rename created_at/updated_at to created_time/updated_time
    # and convert from DateTime to BigInteger (epoch milliseconds)

    # Step 1: Add new BigInteger columns
    op.add_column("sessions", sa.Column("created_time", sa.BigInteger(), nullable=True))
    op.add_column("sessions", sa.Column("updated_time", sa.BigInteger(), nullable=True))

    # Step 2: Update new columns with converted values (multiply by 1000 to get milliseconds)
    # Note: SQLite doesn't have built-in datetime functions that return epoch ms,
    # so we'll use a reasonable approach with strftime
    op.execute("""
        UPDATE sessions
        SET created_time = CAST((julianday(created_at) - 2440587.5) * 86400000 AS INTEGER)
        WHERE created_at IS NOT NULL
    """)

    op.execute("""
        UPDATE sessions
        SET updated_time = CAST((julianday(updated_at) - 2440587.5) * 86400000 AS INTEGER)
        WHERE updated_at IS NOT NULL
    """)

    # Step 3: Set current epoch ms for null values
    op.execute("""
        UPDATE sessions
        SET created_time = CAST((julianday('now') - 2440587.5) * 86400000 AS INTEGER)
        WHERE created_time IS NULL
    """)

    op.execute("""
        UPDATE sessions
        SET updated_time = CAST((julianday('now') - 2440587.5) * 86400000 AS INTEGER)
        WHERE updated_time IS NULL
    """)

    # Step 4: Make new columns NOT NULL
    op.alter_column("sessions", "created_time", nullable=False)
    op.alter_column("sessions", "updated_time", nullable=False)

    # Step 5: Drop old DateTime columns
    op.drop_column("sessions", "created_at")
    op.drop_column("sessions", "updated_at")

    # For chat_messages table: rename created_at to created_time
    # and convert from DateTime to BigInteger (epoch milliseconds)

    # Step 1: Add new BigInteger column
    op.add_column(
        "chat_messages", sa.Column("created_time", sa.BigInteger(), nullable=True)
    )

    # Step 2: Update new column with converted values
    op.execute("""
        UPDATE chat_messages
        SET created_time = CAST((julianday(created_at) - 2440587.5) * 86400000 AS INTEGER)
        WHERE created_at IS NOT NULL
    """)

    # Step 3: Set current epoch ms for null values
    op.execute("""
        UPDATE chat_messages
        SET created_time = CAST((julianday('now') - 2440587.5) * 86400000 AS INTEGER)
        WHERE created_time IS NULL
    """)

    # Step 4: Make new column NOT NULL
    op.alter_column("chat_messages", "created_time", nullable=False)

    # Step 5: Drop old DateTime column
    op.drop_column("chat_messages", "created_at")

    # Step 6: Create indexes on new epoch timestamp columns for performance
    # Index on sessions.user_id for efficient user session filtering
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    # Index on sessions.updated_time for efficient ordering
    op.create_index("ix_sessions_updated_time", "sessions", ["updated_time"])

    # Composite index on sessions for user filtering with ordering
    op.create_index(
        "ix_sessions_user_id_updated_time", "sessions", ["user_id", "updated_time"]
    )

    # Index on chat_messages.created_time for efficient ordering
    op.create_index("ix_chat_messages_created_time", "chat_messages", ["created_time"])

    # Composite index on chat_messages for session filtering with ordering
    op.create_index(
        "ix_chat_messages_session_id_created_time",
        "chat_messages",
        ["session_id", "created_time"],
    )


def downgrade() -> None:
    """Convert back to datetime columns with original names."""

    # First, drop indexes on new columns
    op.drop_index("ix_chat_messages_session_id_created_time", table_name="chat_messages")
    op.drop_index("ix_chat_messages_created_time", table_name="chat_messages")
    op.drop_index("ix_sessions_user_id_updated_time", table_name="sessions")
    op.drop_index("ix_sessions_updated_time", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")

    # For sessions table: convert back to created_at/updated_at DateTime columns
    op.add_column("sessions", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("sessions", sa.Column("updated_at", sa.DateTime(), nullable=True))

    # Convert epoch milliseconds back to datetime
    op.execute("""
        UPDATE sessions
        SET created_at = datetime(created_time / 1000.0, 'unixepoch')
        WHERE created_time IS NOT NULL
    """)

    op.execute("""
        UPDATE sessions
        SET updated_at = datetime(updated_time / 1000.0, 'unixepoch')
        WHERE updated_time IS NOT NULL
    """)

    op.drop_column("sessions", "created_time")
    op.drop_column("sessions", "updated_time")

    # For chat_messages table: convert back to created_at DateTime column
    op.add_column(
        "chat_messages", sa.Column("created_at", sa.DateTime(), nullable=True)
    )

    op.execute("""
        UPDATE chat_messages
        SET created_at = datetime(created_time / 1000.0, 'unixepoch')
        WHERE created_time IS NOT NULL
    """)

    op.drop_column("chat_messages", "created_time")
