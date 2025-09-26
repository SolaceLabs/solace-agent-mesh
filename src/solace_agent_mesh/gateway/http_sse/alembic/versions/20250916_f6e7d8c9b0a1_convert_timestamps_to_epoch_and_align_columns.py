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
    from sqlalchemy import inspect
    import time

    bind = op.get_bind()
    inspector = inspect(bind)
    current_time_ms = int(time.time() * 1000)

    if bind.dialect.name == 'sqlite':
        # SQLite doesn't support ALTER COLUMN, so we need to recreate tables
        _upgrade_sqlite(current_time_ms)
    else:
        # PostgreSQL, MySQL, and other databases support ALTER COLUMN
        _upgrade_standard_sql(current_time_ms)


def _upgrade_sqlite(current_time_ms: int) -> None:
    """Handle SQLite upgrade by recreating tables (SQLite doesn't support dropping columns)."""

    # 1. Create new sessions table with epoch timestamp columns
    op.create_table(
        'sessions_new',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('created_time', sa.BigInteger(), nullable=False),
        sa.Column('updated_time', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. Copy data from old table with timestamp conversion
    op.execute(f"""
        INSERT INTO sessions_new (id, name, user_id, agent_id, created_time, updated_time)
        SELECT
            id,
            name,
            user_id,
            agent_id,
            COALESCE(CAST(strftime('%s', created_at) * 1000 AS INTEGER), {current_time_ms}) as created_time,
            COALESCE(CAST(strftime('%s', updated_at) * 1000 AS INTEGER), {current_time_ms}) as updated_time
        FROM sessions
    """)

    # 3. Drop old table and rename new table
    op.drop_table('sessions')
    op.rename_table('sessions_new', 'sessions')

    # 4. Create new chat_messages table with epoch timestamp column
    op.create_table(
        'chat_messages_new',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('sender_type', sa.String(), nullable=True),
        sa.Column('sender_name', sa.String(), nullable=True),
        sa.Column('created_time', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE')
    )

    # 5. Copy data from old chat_messages table with timestamp conversion
    op.execute(f"""
        INSERT INTO chat_messages_new (id, session_id, message, sender_type, sender_name, created_time)
        SELECT
            id,
            session_id,
            message,
            sender_type,
            sender_name,
            COALESCE(CAST(strftime('%s', created_at) * 1000 AS INTEGER), {current_time_ms}) as created_time
        FROM chat_messages
    """)

    # 6. Drop old table and rename new table
    op.drop_table('chat_messages')
    op.rename_table('chat_messages_new', 'chat_messages')

    # 7. Create indexes
    _create_updated_indexes()


def _upgrade_standard_sql(current_time_ms: int) -> None:
    """Handle PostgreSQL/MySQL upgrade using ALTER COLUMN (standard SQL approach)."""

    bind = op.get_bind()

    # For sessions table
    op.add_column("sessions", sa.Column("created_time", sa.BigInteger(), nullable=True))
    op.add_column("sessions", sa.Column("updated_time", sa.BigInteger(), nullable=True))

    # Convert timestamps using database-appropriate functions
    if bind.dialect.name == 'postgresql':
        op.execute("""
            UPDATE sessions
            SET created_time = CAST(EXTRACT(EPOCH FROM created_at) * 1000 AS BIGINT)
            WHERE created_at IS NOT NULL
        """)

        op.execute("""
            UPDATE sessions
            SET updated_time = CAST(EXTRACT(EPOCH FROM updated_at) * 1000 AS BIGINT)
            WHERE updated_at IS NOT NULL
        """)
    else:
        # MySQL and other databases use UNIX_TIMESTAMP
        op.execute("""
            UPDATE sessions
            SET created_time = CAST(UNIX_TIMESTAMP(created_at) * 1000 AS UNSIGNED)
            WHERE created_at IS NOT NULL
        """)

        op.execute("""
            UPDATE sessions
            SET updated_time = CAST(UNIX_TIMESTAMP(updated_at) * 1000 AS UNSIGNED)
            WHERE updated_at IS NOT NULL
        """)

    # Set current epoch ms for null values
    op.execute(f"""
        UPDATE sessions
        SET created_time = {current_time_ms}
        WHERE created_time IS NULL
    """)

    op.execute(f"""
        UPDATE sessions
        SET updated_time = {current_time_ms}
        WHERE updated_time IS NULL
    """)

    # Make new columns NOT NULL
    op.alter_column("sessions", "created_time", nullable=False)
    op.alter_column("sessions", "updated_time", nullable=False)

    # Drop old columns
    op.drop_column("sessions", "created_at")
    op.drop_column("sessions", "updated_at")

    # For chat_messages table
    op.add_column("chat_messages", sa.Column("created_time", sa.BigInteger(), nullable=True))

    if bind.dialect.name == 'postgresql':
        op.execute("""
            UPDATE chat_messages
            SET created_time = CAST(EXTRACT(EPOCH FROM created_at) * 1000 AS BIGINT)
            WHERE created_at IS NOT NULL
        """)
    else:
        # MySQL and other databases use UNIX_TIMESTAMP
        op.execute("""
            UPDATE chat_messages
            SET created_time = CAST(UNIX_TIMESTAMP(created_at) * 1000 AS UNSIGNED)
            WHERE created_at IS NOT NULL
        """)

    op.execute(f"""
        UPDATE chat_messages
        SET created_time = {current_time_ms}
        WHERE created_time IS NULL
    """)

    op.alter_column("chat_messages", "created_time", nullable=False)
    op.drop_column("chat_messages", "created_at")

    # Add indexes - this will be called after either upgrade path
    _create_updated_indexes()


def _create_updated_indexes() -> None:
    """Create indexes on new timestamp columns."""

    # For SQLite, indexes are recreated when tables are recreated
    # For other databases, we need to manage index transitions

    bind = op.get_bind()

    if bind.dialect.name == 'sqlite':
        # SQLite: Create all indexes fresh (old ones were dropped with table recreation)
        _create_indexes_safe("ix_sessions_user_id", "sessions", ["user_id"])
        _create_indexes_safe("ix_sessions_agent_id", "sessions", ["agent_id"])
        _create_indexes_safe("ix_sessions_updated_time", "sessions", ["updated_time"])
        _create_indexes_safe("ix_sessions_user_id_updated_time", "sessions", ["user_id", "updated_time"])

        _create_indexes_safe("ix_chat_messages_session_id", "chat_messages", ["session_id"])
        _create_indexes_safe("ix_chat_messages_created_time", "chat_messages", ["created_time"])
        _create_indexes_safe("ix_chat_messages_session_id_created_time", "chat_messages", ["session_id", "created_time"])

    else:
        # PostgreSQL/MySQL: Drop old indexes and create new ones
        _drop_index_safe("ix_sessions_updated_at", "sessions")
        _drop_index_safe("ix_sessions_user_id_updated_at", "sessions")
        _drop_index_safe("ix_chat_messages_created_at", "chat_messages")
        _drop_index_safe("ix_chat_messages_session_id_created_at", "chat_messages")

        # Create new indexes (user_id and agent_id indexes already exist)
        _create_indexes_safe("ix_sessions_updated_time", "sessions", ["updated_time"])
        _create_indexes_safe("ix_sessions_user_id_updated_time", "sessions", ["user_id", "updated_time"])
        _create_indexes_safe("ix_chat_messages_created_time", "chat_messages", ["created_time"])
        _create_indexes_safe("ix_chat_messages_session_id_created_time", "chat_messages", ["session_id", "created_time"])


def _create_indexes_safe(index_name: str, table_name: str, columns: list) -> None:
    """Create index only if it doesn't exist."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if bind.dialect.name == 'postgresql':
        columns_str = ', '.join(columns)
        bind.execute(sa.text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})"))
    elif bind.dialect.name == 'sqlite':
        try:
            op.create_index(index_name, table_name, columns)
        except Exception:
            pass
    else:
        existing_indexes = inspector.get_indexes(table_name)
        index_exists = any(idx['name'] == index_name for idx in existing_indexes)
        if not index_exists:
            op.create_index(index_name, table_name, columns)


def _drop_index_safe(index_name: str, table_name: str) -> None:
    """Drop index only if it exists."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(f"DROP INDEX IF EXISTS {index_name}"))
    elif bind.dialect.name == 'sqlite':
        try:
            op.drop_index(index_name, table_name=table_name)
        except Exception:
            pass
    else:
        existing_indexes = inspector.get_indexes(table_name)
        index_exists = any(idx['name'] == index_name for idx in existing_indexes)
        if index_exists:
            op.drop_index(index_name, table_name=table_name)


def downgrade() -> None:
    """Convert back to datetime columns with original names."""
    bind = op.get_bind()

    if bind.dialect.name == 'sqlite':
        _downgrade_sqlite()
    else:
        _downgrade_standard_sql()


def _downgrade_sqlite() -> None:
    """Handle SQLite downgrade by recreating tables with original datetime columns."""

    # 1. Create sessions table with original datetime columns
    op.create_table(
        'sessions_old',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. Copy data back with timestamp conversion
    op.execute("""
        INSERT INTO sessions_old (id, name, user_id, agent_id, created_at, updated_at)
        SELECT
            id,
            name,
            user_id,
            agent_id,
            datetime(created_time / 1000.0, 'unixepoch') as created_at,
            datetime(updated_time / 1000.0, 'unixepoch') as updated_at
        FROM sessions
    """)

    # 3. Drop new table and rename old table
    op.drop_table('sessions')
    op.rename_table('sessions_old', 'sessions')

    # 4. Create chat_messages table with original datetime column
    op.create_table(
        'chat_messages_old',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('sender_type', sa.String(), nullable=True),
        sa.Column('sender_name', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE')
    )

    # 5. Copy data back with timestamp conversion
    op.execute("""
        INSERT INTO chat_messages_old (id, session_id, message, sender_type, sender_name, created_at)
        SELECT
            id,
            session_id,
            message,
            sender_type,
            sender_name,
            datetime(created_time / 1000.0, 'unixepoch') as created_at
        FROM chat_messages
    """)

    # 6. Drop new table and rename old table
    op.drop_table('chat_messages')
    op.rename_table('chat_messages_old', 'chat_messages')

    # 7. Recreate original indexes
    _create_indexes_safe("ix_sessions_user_id", "sessions", ["user_id"])
    _create_indexes_safe("ix_sessions_agent_id", "sessions", ["agent_id"])
    _create_indexes_safe("ix_sessions_updated_at", "sessions", ["updated_at"])
    _create_indexes_safe("ix_sessions_user_id_updated_at", "sessions", ["user_id", "updated_at"])
    _create_indexes_safe("ix_chat_messages_session_id", "chat_messages", ["session_id"])
    _create_indexes_safe("ix_chat_messages_created_at", "chat_messages", ["created_at"])
    _create_indexes_safe("ix_chat_messages_session_id_created_at", "chat_messages", ["session_id", "created_at"])


def _downgrade_standard_sql() -> None:
    """Handle PostgreSQL/MySQL downgrade using ALTER COLUMN."""
    bind = op.get_bind()

    # Drop indexes on new columns
    _drop_index_safe("ix_chat_messages_session_id_created_time", "chat_messages")
    _drop_index_safe("ix_chat_messages_created_time", "chat_messages")
    _drop_index_safe("ix_sessions_user_id_updated_time", "sessions")
    _drop_index_safe("ix_sessions_updated_time", "sessions")

    # For sessions table: convert back to datetime columns
    op.add_column("sessions", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("sessions", sa.Column("updated_at", sa.DateTime(), nullable=True))

    # Convert epoch milliseconds back to datetime based on database type
    if bind.dialect.name == 'postgresql':
        op.execute("""
            UPDATE sessions
            SET created_at = to_timestamp(created_time / 1000.0)
            WHERE created_time IS NOT NULL
        """)

        op.execute("""
            UPDATE sessions
            SET updated_at = to_timestamp(updated_time / 1000.0)
            WHERE updated_time IS NOT NULL
        """)
    else:
        # MySQL and other databases
        op.execute("""
            UPDATE sessions
            SET created_at = FROM_UNIXTIME(created_time / 1000.0)
            WHERE created_time IS NOT NULL
        """)

        op.execute("""
            UPDATE sessions
            SET updated_at = FROM_UNIXTIME(updated_time / 1000.0)
            WHERE updated_time IS NOT NULL
        """)

    op.drop_column("sessions", "created_time")
    op.drop_column("sessions", "updated_time")

    # For chat_messages table: convert back to datetime column
    op.add_column("chat_messages", sa.Column("created_at", sa.DateTime(), nullable=True))

    if bind.dialect.name == 'postgresql':
        op.execute("""
            UPDATE chat_messages
            SET created_at = to_timestamp(created_time / 1000.0)
            WHERE created_time IS NOT NULL
        """)
    else:
        # MySQL and other databases
        op.execute("""
            UPDATE chat_messages
            SET created_at = FROM_UNIXTIME(created_time / 1000.0)
            WHERE created_time IS NOT NULL
        """)

    op.drop_column("chat_messages", "created_time")

    # Recreate the old indexes
    _create_indexes_safe("ix_sessions_updated_at", "sessions", ["updated_at"])
    _create_indexes_safe("ix_sessions_user_id_updated_at", "sessions", ["user_id", "updated_at"])
    _create_indexes_safe("ix_chat_messages_created_at", "chat_messages", ["created_at"])
    _create_indexes_safe("ix_chat_messages_session_id_created_at", "chat_messages", ["session_id", "created_at"])
