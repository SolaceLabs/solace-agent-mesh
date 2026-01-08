"""add tasks, task_events, feedback, and chat_tasks tables

Revision ID: 98882922fa59
Revises: f6e7d8c9b0a1
Create Date: 2025-10-06 09:57:54.735496

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "98882922fa59"
down_revision: Union[str, Sequence[str], None] = "f6e7d8c9b0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create tasks, task_events, feedback, and chat_tasks tables."""

    # Create feedback table
    op.create_table(
        "feedback",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("rating", sa.String(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_time", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_feedback_task_id"), "feedback", ["task_id"], unique=False)
    op.create_index(op.f("ix_feedback_user_id"), "feedback", ["user_id"], unique=False)
    op.create_index(
        "ix_feedback_created_time", "feedback", ["created_time"], unique=False
    )

    # Create tasks table
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("start_time", sa.BigInteger(), nullable=False),
        sa.Column("end_time", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("initial_request_text", sa.Text(), nullable=True),
        sa.Column("total_input_tokens", sa.Integer(), nullable=True),
        sa.Column("total_output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_cached_input_tokens", sa.Integer(), nullable=True),
        sa.Column("token_usage_details", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tasks_initial_request_text"),
        "tasks",
        ["initial_request_text"],
        unique=False,
    )
    op.create_index(op.f("ix_tasks_user_id"), "tasks", ["user_id"], unique=False)
    op.create_index("ix_tasks_start_time", "tasks", ["start_time"], unique=False)

    # Create task_events table
    op.create_table(
        "task_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("created_time", sa.BigInteger(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("direction", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_task_events_task_id"), "task_events", ["task_id"], unique=False
    )
    op.create_index(
        op.f("ix_task_events_user_id"), "task_events", ["user_id"], unique=False
    )

    # Create chat_tasks table
    op.create_table(
        "chat_tasks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=True),
        sa.Column("message_bubbles", sa.Text(), nullable=False),
        sa.Column("task_metadata", sa.Text(), nullable=True),
        sa.Column("created_time", sa.BigInteger(), nullable=False),
        sa.Column("updated_time", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chat_tasks_session_id", "chat_tasks", ["session_id"])
    op.create_index("ix_chat_tasks_user_id", "chat_tasks", ["user_id"])
    op.create_index("ix_chat_tasks_created_time", "chat_tasks", ["created_time"])

    # Drop old indexes from sessions and chat_messages tables
    op.drop_index(op.f("ix_chat_messages_created_time"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_session_id"), table_name="chat_messages")
    op.drop_index(
        op.f("ix_chat_messages_session_id_created_time"), table_name="chat_messages"
    )
    op.drop_index(op.f("ix_sessions_agent_id"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_updated_time"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_user_id_updated_time"), table_name="sessions")

    # Drop the chat_messages table - replaced by chat_tasks
    op.drop_table("chat_messages")


def downgrade() -> None:
    """Drop tasks, task_events, feedback, and chat_tasks tables."""

    # Recreate chat_messages table
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_time", sa.BigInteger(), nullable=False),
        sa.Column("sender_type", sa.String(length=50), nullable=True),
        sa.Column("sender_name", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Recreate old indexes
    op.create_index(
        op.f("ix_sessions_user_id_updated_time"),
        "sessions",
        ["user_id", "updated_time"],
        unique=False,
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_sessions_updated_time"), "sessions", ["updated_time"], unique=False
    )
    op.create_index(
        op.f("ix_sessions_agent_id"), "sessions", ["agent_id"], unique=False
    )
    op.create_index(
        op.f("ix_chat_messages_session_id_created_time"),
        "chat_messages",
        ["session_id", "created_time"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chat_messages_session_id"),
        "chat_messages",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chat_messages_created_time"),
        "chat_messages",
        ["created_time"],
        unique=False,
    )

    # Drop chat_tasks table
    op.drop_index("ix_chat_tasks_created_time", table_name="chat_tasks")
    op.drop_index("ix_chat_tasks_user_id", table_name="chat_tasks")
    op.drop_index("ix_chat_tasks_session_id", table_name="chat_tasks")
    op.drop_table("chat_tasks")

    # Drop task_events table
    op.drop_index(op.f("ix_task_events_user_id"), table_name="task_events")
    op.drop_index(op.f("ix_task_events_task_id"), table_name="task_events")
    op.drop_table("task_events")

    # Drop tasks table
    op.drop_index("ix_tasks_start_time", table_name="tasks")
    op.drop_index(op.f("ix_tasks_user_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_initial_request_text"), table_name="tasks")
    op.drop_table("tasks")

    # Drop feedback table
    op.drop_index("ix_feedback_created_time", table_name="feedback")
    op.drop_index(op.f("ix_feedback_user_id"), table_name="feedback")
    op.drop_index(op.f("ix_feedback_task_id"), table_name="feedback")
    op.drop_table("feedback")
