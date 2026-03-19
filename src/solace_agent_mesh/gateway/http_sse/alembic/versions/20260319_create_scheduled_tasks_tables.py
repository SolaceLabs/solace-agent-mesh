"""Create scheduled tasks tables

Revision ID: 20260319_scheduled_tasks
Revises: 20260123_add_share_links
Create Date: 2026-03-19 00:00:00.000000

Creates tables for the scheduled tasks feature:
- scheduled_tasks: task definitions with scheduling config
- scheduled_task_executions: execution history records
- scheduler_locks: distributed leader election lock
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '20260319_scheduled_tasks'
down_revision: Union[str, None] = '20260123_add_share_links'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    """Check if a table already exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    """Check if an index already exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_indexes = inspector.get_indexes(table_name)
    return any(idx["name"] == index_name for idx in existing_indexes)


def upgrade() -> None:
    dialect = op.get_bind().dialect.name

    # Create scheduled_tasks table
    if not _table_exists("scheduled_tasks"):
        op.create_table(
            "scheduled_tasks",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("namespace", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("created_by", sa.String(), nullable=False),
            sa.Column(
                "schedule_type",
                sa.Enum("cron", "interval", "one_time", name="scheduletype"),
                nullable=False,
            ),
            sa.Column("schedule_expression", sa.String(), nullable=False),
            sa.Column("timezone", sa.String(), nullable=False, server_default="UTC"),
            sa.Column("target_agent_name", sa.String(), nullable=False),
            sa.Column("target_type", sa.String(), nullable=False, server_default="agent"),
            sa.Column("task_message", sa.JSON(), nullable=False),
            sa.Column("task_metadata", sa.JSON(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("status", sa.String(), nullable=False, server_default="active"),
            sa.Column("max_retries", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("retry_delay_seconds", sa.Integer(), nullable=False, server_default=sa.text("60")),
            sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default=sa.text("3600")),
            sa.Column("source", sa.String(), nullable=True, server_default="ui"),
            sa.Column("consecutive_failure_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("run_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("notification_config", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
            sa.Column("next_run_at", sa.BigInteger(), nullable=True),
            sa.Column("last_run_at", sa.BigInteger(), nullable=True),
            sa.Column("deleted_at", sa.BigInteger(), nullable=True),
            sa.Column("deleted_by", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

        # Create indexes
        op.create_index("ix_scheduled_tasks_name", "scheduled_tasks", ["name"])
        op.create_index("ix_scheduled_tasks_namespace", "scheduled_tasks", ["namespace"])
        op.create_index("ix_scheduled_tasks_user_id", "scheduled_tasks", ["user_id"])
        op.create_index("ix_scheduled_tasks_schedule_type", "scheduled_tasks", ["schedule_type"])
        op.create_index("ix_scheduled_tasks_target_agent_name", "scheduled_tasks", ["target_agent_name"])
        op.create_index("ix_scheduled_tasks_enabled", "scheduled_tasks", ["enabled"])
        op.create_index("ix_scheduled_tasks_next_run_at", "scheduled_tasks", ["next_run_at"])
        op.create_index("ix_scheduled_tasks_deleted_at", "scheduled_tasks", ["deleted_at"])

        # Unique partial index: only one active task per (namespace, name)
        if dialect == "postgresql":
            op.execute(
                "CREATE UNIQUE INDEX uq_scheduled_tasks_namespace_name_active "
                "ON scheduled_tasks (namespace, name) WHERE deleted_at IS NULL"
            )
        elif dialect == "sqlite":
            # SQLite supports partial indexes
            op.execute(
                "CREATE UNIQUE INDEX uq_scheduled_tasks_namespace_name_active "
                "ON scheduled_tasks (namespace, name) WHERE deleted_at IS NULL"
            )
        else:
            # MySQL doesn't support partial indexes — skip unique constraint
            pass

    # Create scheduled_task_executions table
    if not _table_exists("scheduled_task_executions"):
        op.create_table(
            "scheduled_task_executions",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("scheduled_task_id", sa.String(), nullable=False),
            sa.Column(
                "status",
                sa.Enum(
                    "pending", "running", "completed", "failed",
                    "timeout", "cancelled", "skipped",
                    name="executionstatus",
                ),
                nullable=False,
            ),
            sa.Column("a2a_task_id", sa.String(), nullable=True),
            sa.Column("scheduled_for", sa.BigInteger(), nullable=False),
            sa.Column("started_at", sa.BigInteger(), nullable=True),
            sa.Column("completed_at", sa.BigInteger(), nullable=True),
            sa.Column("result_summary", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("artifacts", sa.JSON(), nullable=True),
            sa.Column("notifications_sent", sa.JSON(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["scheduled_task_id"],
                ["scheduled_tasks.id"],
            ),
        )

        # Create indexes
        op.create_index("ix_scheduled_task_executions_task_id", "scheduled_task_executions", ["scheduled_task_id"])
        op.create_index("ix_scheduled_task_executions_status", "scheduled_task_executions", ["status"])
        op.create_index("ix_scheduled_task_executions_a2a_task_id", "scheduled_task_executions", ["a2a_task_id"])
        op.create_index("ix_scheduled_task_executions_scheduled_for", "scheduled_task_executions", ["scheduled_for"])

    # Create scheduler_locks table
    if not _table_exists("scheduler_locks"):
        op.create_table(
            "scheduler_locks",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("leader_id", sa.String(), nullable=False),
            sa.Column("leader_namespace", sa.String(), nullable=False),
            sa.Column("acquired_at", sa.BigInteger(), nullable=False),
            sa.Column("expires_at", sa.BigInteger(), nullable=False),
            sa.Column("heartbeat_at", sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

        op.create_index("ix_scheduler_locks_expires_at", "scheduler_locks", ["expires_at"])


def downgrade() -> None:
    # Drop in reverse order
    if _table_exists("scheduler_locks"):
        op.drop_table("scheduler_locks")
    if _table_exists("scheduled_task_executions"):
        op.drop_table("scheduled_task_executions")
    if _table_exists("scheduled_tasks"):
        op.drop_table("scheduled_tasks")
