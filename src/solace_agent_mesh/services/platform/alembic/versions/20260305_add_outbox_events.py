"""Add outbox_events table for generic event-driven processing

Revision ID: 20260305_outbox_events
Revises: None
Create Date: 2026-03-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql, postgresql

revision: str = "20260305_outbox_events"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if "outbox_events" in inspector.get_table_names():
        return

    dialect_name = connection.dialect.name

    if dialect_name == 'postgresql':
        id_type = postgresql.UUID()
    elif dialect_name in ('mysql', 'mariadb'):
        id_type = mysql.BINARY(16)
    else:
        id_type = sa.String(36)

    op.create_table(
        "outbox_events",
        sa.Column("id", id_type, nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_time", sa.BigInteger(), nullable=False),
        sa.Column("updated_time", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_outbox_status_retry", "outbox_events", ["status", "next_retry_at"])
    op.create_index("ix_outbox_entity", "outbox_events", ["entity_type", "entity_id", "event_type", "status"])
    op.create_index("ix_outbox_created_time", "outbox_events", ["created_time"])
    op.create_index("ix_outbox_updated_time", "outbox_events", ["updated_time"])

    if dialect_name != 'sqlite':
        op.create_check_constraint(
            "check_outbox_status",
            "outbox_events",
            "status IN ('pending', 'completed', 'error', 'skipped')"
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if "outbox_events" not in inspector.get_table_names():
        return

    dialect_name = connection.dialect.name

    if dialect_name != 'sqlite':
        op.drop_constraint("check_outbox_status", "outbox_events", type_="check")

    op.drop_index("ix_outbox_updated_time", table_name="outbox_events")
    op.drop_index("ix_outbox_created_time", table_name="outbox_events")
    op.drop_index("ix_outbox_entity", table_name="outbox_events")
    op.drop_index("ix_outbox_status_retry", table_name="outbox_events")
    op.drop_table("outbox_events")
