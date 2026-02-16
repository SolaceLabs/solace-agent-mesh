"""Add agent checkpoint tables for stateless peer-call checkpointing

Revision ID: a1b2c3d4e5f6
Revises: e2902798564d
Create Date: 2026-02-16

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "c9f4a28e71b3"
down_revision: Union[str, Sequence[str], None] = "e2902798564d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    bind = op.get_bind()
    insp = inspect(bind)
    return table_name in insp.get_table_names()


def upgrade() -> None:
    """Create checkpoint tables for stateless agent operation."""

    if not table_exists("agent_paused_tasks"):
        op.create_table(
            "agent_paused_tasks",
            sa.Column("logical_task_id", sa.String, primary_key=True),
            sa.Column("agent_name", sa.String, nullable=False),
            sa.Column("a2a_context", sa.Text, nullable=False),
            sa.Column("effective_session_id", sa.String, nullable=True),
            sa.Column("user_id", sa.String, nullable=True),
            sa.Column("current_invocation_id", sa.String, nullable=True),
            sa.Column("produced_artifacts", sa.Text, nullable=True),
            sa.Column("artifact_signals_to_return", sa.Text, nullable=True),
            sa.Column("response_buffer", sa.Text, nullable=True),
            sa.Column("flags", sa.Text, nullable=True),
            sa.Column("security_context", sa.Text, nullable=True),
            sa.Column("token_usage", sa.Text, nullable=True),
            sa.Column("checkpointed_at", sa.Float, nullable=False),
        )
        op.create_index(
            "ix_agent_paused_tasks_agent_name",
            "agent_paused_tasks",
            ["agent_name"],
        )

    if not table_exists("agent_peer_sub_tasks"):
        op.create_table(
            "agent_peer_sub_tasks",
            sa.Column("sub_task_id", sa.String, primary_key=True),
            sa.Column(
                "logical_task_id",
                sa.String,
                sa.ForeignKey(
                    "agent_paused_tasks.logical_task_id", ondelete="CASCADE"
                ),
                nullable=False,
            ),
            sa.Column("invocation_id", sa.String, nullable=False),
            sa.Column("correlation_data", sa.Text, nullable=False),
            sa.Column("timeout_deadline", sa.Float, nullable=True),
            sa.Column("created_at", sa.Float, nullable=False),
        )
        op.create_index(
            "ix_agent_peer_sub_tasks_logical_task_id",
            "agent_peer_sub_tasks",
            ["logical_task_id"],
        )
        op.create_index(
            "ix_agent_peer_sub_tasks_invocation_id",
            "agent_peer_sub_tasks",
            ["invocation_id"],
        )
        op.create_index(
            "ix_agent_peer_sub_tasks_timeout",
            "agent_peer_sub_tasks",
            ["timeout_deadline"],
        )

    if not table_exists("agent_parallel_invocations"):
        op.create_table(
            "agent_parallel_invocations",
            sa.Column(
                "logical_task_id",
                sa.String,
                sa.ForeignKey(
                    "agent_paused_tasks.logical_task_id", ondelete="CASCADE"
                ),
                primary_key=True,
            ),
            sa.Column("invocation_id", sa.String, primary_key=True),
            sa.Column("total_expected", sa.Integer, nullable=False),
            sa.Column("completed_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("results", sa.Text, nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    """Drop checkpoint tables."""

    if table_exists("agent_parallel_invocations"):
        op.drop_table("agent_parallel_invocations")

    if table_exists("agent_peer_sub_tasks"):
        op.drop_table("agent_peer_sub_tasks")

    if table_exists("agent_paused_tasks"):
        op.drop_table("agent_paused_tasks")
