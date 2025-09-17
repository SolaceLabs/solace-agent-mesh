"""Convert timestamps to epoch milliseconds and align column names

Revision ID: f6e7d8c9b0a1
Revises: b1c2d3e4f5g6
Create Date: 2025-09-16 16:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6e7d8c9b0a1"
down_revision: str | None = "b1c2d3e4f5g6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Convert datetime columns to epoch milliseconds and rename columns."""
    from sqlalchemy import inspect, MetaData, Table, select, update
    from sqlalchemy.sql import func
    import time

    # For sessions table: rename created_at/updated_at to created_time/updated_time
    # and convert from DateTime to BigInteger (epoch milliseconds)

    # Step 1: Add new BigInteger columns
    op.add_column("sessions", sa.Column("created_time", sa.BigInteger(), nullable=True))
    op.add_column("sessions", sa.Column("updated_time", sa.BigInteger(), nullable=True))

    # Step 2: Use SQLAlchemy ORM for database-agnostic conversion
    bind = op.get_bind()
    inspector = inspect(bind)
    metadata = MetaData()
    sessions_table = Table('sessions', metadata, autoload_with=bind)

    # Convert existing timestamps to epoch milliseconds using SQLAlchemy functions
    # This approach works across all databases that SQLAlchemy supports
    current_time_ms = int(time.time() * 1000)

    # Update created_time from created_at (database-agnostic using SQLAlchemy)
    bind.execute(
        update(sessions_table)
        .where(sessions_table.c.created_at.isnot(None))
        .values(created_time=func.cast(
            func.extract('epoch', sessions_table.c.created_at) * 1000,
            sa.BigInteger
        ))
    )

    # Update updated_time from updated_at
    bind.execute(
        update(sessions_table)
        .where(sessions_table.c.updated_at.isnot(None))
        .values(updated_time=func.cast(
            func.extract('epoch', sessions_table.c.updated_at) * 1000,
            sa.BigInteger
        ))
    )

    # Set current epoch ms for null values
    bind.execute(
        update(sessions_table)
        .where(sessions_table.c.created_time.is_(None))
        .values(created_time=current_time_ms)
    )

    bind.execute(
        update(sessions_table)
        .where(sessions_table.c.updated_time.is_(None))
        .values(updated_time=current_time_ms)
    )

    # Step 3: Make new columns NOT NULL
    op.alter_column("sessions", "created_time", nullable=False)
    op.alter_column("sessions", "updated_time", nullable=False)

    # Step 4: Drop old DateTime columns
    op.drop_column("sessions", "created_at")
    op.drop_column("sessions", "updated_at")

    # For chat_messages table: rename created_at to created_time
    # and convert from DateTime to BigInteger (epoch milliseconds)

    # Step 1: Add new BigInteger column
    op.add_column(
        "chat_messages", sa.Column("created_time", sa.BigInteger(), nullable=True)
    )

    # Step 2: Database-agnostic conversion for chat_messages
    chat_messages_table = Table('chat_messages', metadata, autoload_with=bind)

    # Update created_time from created_at
    bind.execute(
        update(chat_messages_table)
        .where(chat_messages_table.c.created_at.isnot(None))
        .values(created_time=func.cast(
            func.extract('epoch', chat_messages_table.c.created_at) * 1000,
            sa.BigInteger
        ))
    )

    # Set current epoch ms for null values
    bind.execute(
        update(chat_messages_table)
        .where(chat_messages_table.c.created_time.is_(None))
        .values(created_time=current_time_ms)
    )

    # Step 4: Make new column NOT NULL
    op.alter_column("chat_messages", "created_time", nullable=False)

    # Step 5: Drop old DateTime column
    op.drop_column("chat_messages", "created_at")

    # Step 6: Update indexes to use new epoch timestamp columns
    # The previous migration (b1c2d3e4f5g6) created indexes on old column names,
    # we need to drop those and create new ones on the renamed columns

    # Drop old indexes on old column names (created by previous migration)
    try:
        op.drop_index("ix_sessions_updated_at", table_name="sessions")
    except Exception:
        pass  # Index might not exist in some environments

    try:
        op.drop_index("ix_sessions_user_id_updated_at", table_name="sessions")
    except Exception:
        pass

    try:
        op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    except Exception:
        pass

    try:
        op.drop_index("ix_chat_messages_session_id_created_at", table_name="chat_messages")
    except Exception:
        pass

    # Create new indexes on new column names
    # Note: ix_sessions_user_id already exists and doesn't need to be recreated

    # Index on sessions.updated_time for efficient ordering (replaces ix_sessions_updated_at)
    op.create_index("ix_sessions_updated_time", "sessions", ["updated_time"])

    # Composite index on sessions for user filtering with ordering (replaces ix_sessions_user_id_updated_at)
    op.create_index(
        "ix_sessions_user_id_updated_time", "sessions", ["user_id", "updated_time"]
    )

    # Index on chat_messages.created_time for efficient ordering (replaces ix_chat_messages_created_at)
    op.create_index("ix_chat_messages_created_time", "chat_messages", ["created_time"])

    # Composite index on chat_messages for session filtering with ordering (replaces ix_chat_messages_session_id_created_at)
    op.create_index(
        "ix_chat_messages_session_id_created_time",
        "chat_messages",
        ["session_id", "created_time"],
    )


def downgrade() -> None:
    """Convert back to datetime columns with original names."""
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)

    # First, drop indexes on new columns (that we created in upgrade)
    try:
        op.drop_index("ix_chat_messages_session_id_created_time", table_name="chat_messages")
    except Exception:
        pass

    try:
        op.drop_index("ix_chat_messages_created_time", table_name="chat_messages")
    except Exception:
        pass

    try:
        op.drop_index("ix_sessions_user_id_updated_time", table_name="sessions")
    except Exception:
        pass

    try:
        op.drop_index("ix_sessions_updated_time", table_name="sessions")
    except Exception:
        pass

    # Note: We don't drop ix_sessions_user_id since it existed before this migration

    # For sessions table: convert back to created_at/updated_at DateTime columns
    op.add_column("sessions", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("sessions", sa.Column("updated_at", sa.DateTime(), nullable=True))

    # Convert epoch milliseconds back to datetime using SQLAlchemy functions
    from sqlalchemy import MetaData, Table, update
    from sqlalchemy.sql import func

    bind = op.get_bind()
    metadata = MetaData()
    sessions_table = Table('sessions', metadata, autoload_with=bind)

    # Convert epoch milliseconds back to datetime (database-agnostic)
    bind.execute(
        update(sessions_table)
        .where(sessions_table.c.created_time.isnot(None))
        .values(created_at=func.to_timestamp(sessions_table.c.created_time / 1000.0))
    )

    bind.execute(
        update(sessions_table)
        .where(sessions_table.c.updated_time.isnot(None))
        .values(updated_at=func.to_timestamp(sessions_table.c.updated_time / 1000.0))
    )

    op.drop_column("sessions", "created_time")
    op.drop_column("sessions", "updated_time")

    # For chat_messages table: convert back to created_at DateTime column
    op.add_column(
        "chat_messages", sa.Column("created_at", sa.DateTime(), nullable=True)
    )

    chat_messages_table = Table('chat_messages', metadata, autoload_with=bind)

    # Convert epoch milliseconds back to datetime (database-agnostic)
    bind.execute(
        update(chat_messages_table)
        .where(chat_messages_table.c.created_time.isnot(None))
        .values(created_at=func.to_timestamp(chat_messages_table.c.created_time / 1000.0))
    )

    op.drop_column("chat_messages", "created_time")

    # Recreate the old indexes that existed before this migration (from b1c2d3e4f5g6)
    try:
        op.create_index("ix_sessions_updated_at", "sessions", ["updated_at"])
    except Exception:
        pass

    try:
        op.create_index("ix_sessions_user_id_updated_at", "sessions", ["user_id", "updated_at"])
    except Exception:
        pass

    try:
        op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])
    except Exception:
        pass

    try:
        op.create_index("ix_chat_messages_session_id_created_at", "chat_messages", ["session_id", "created_at"])
    except Exception:
        pass
