"""add performance indexes for query optimization

Revision ID: 20251015_session_idx
Revises: 98882922fa59
Create Date: 2025-10-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20251015_session_idx"
down_revision: str | Sequence[str] | None = "98882922fa59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add composite indexes for optimal query performance."""

    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)

    op.create_index(
        "ix_sessions_user_updated",
        "sessions",
        ["user_id", sa.text("updated_time DESC")],
        unique=False,
    )

    op.create_index(
        "ix_chat_tasks_session_user_created",
        "chat_tasks",
        ["session_id", "user_id", "created_time"],
        unique=False,
    )

    op.create_index(
        "ix_tasks_user_start_time",
        "tasks",
        ["user_id", sa.text("start_time DESC")],
        unique=False,
    )

    op.create_index(
        "ix_task_events_task_created",
        "task_events",
        ["task_id", "created_time"],
        unique=False,
    )

    op.drop_index("ix_tasks_initial_request_text", table_name="tasks")


def downgrade() -> None:
    """Remove performance indexes."""

    op.create_index(
        op.f("ix_tasks_initial_request_text"),
        "tasks",
        ["initial_request_text"],
        unique=False,
    )

    op.drop_index("ix_task_events_task_created", table_name="task_events")
    op.drop_index("ix_tasks_user_start_time", table_name="tasks")
    op.drop_index("ix_chat_tasks_session_user_created", table_name="chat_tasks")
    op.drop_index("ix_sessions_user_updated", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
