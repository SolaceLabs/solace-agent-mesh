"""Add last_viewed_at to sessions

Revision ID: 20260417_last_viewed_at
Revises: 20260322_trigger_type_fix
Create Date: 2026-04-17 00:00:00.000000

Adds a per-session ``last_viewed_at`` epoch-ms column so the UI can show an
"unseen updates" indicator against sessions whose ``updated_time`` has
advanced since the user last opened them. Nullable with no default — a
``NULL`` value is treated as "never viewed" by the frontend, which falls
back to ``created_time``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision: str = "20260417_last_viewed_at"
down_revision: Union[str, Sequence[str], None] = "20260322_trigger_type_fix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "sessions" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("sessions")}
    if "last_viewed_at" in columns:
        return
    op.add_column("sessions", sa.Column("last_viewed_at", sa.BigInteger(), nullable=True))

    # Backfill existing rows so pre-existing sessions don't all show an
    # "unseen updates" dot on first load after rollout. New rows created
    # after this migration keep NULL until the user first views them.
    bind.execute(text("UPDATE sessions SET last_viewed_at = updated_time WHERE last_viewed_at IS NULL"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "sessions" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("sessions")}
    if "last_viewed_at" not in columns:
        return
    op.drop_column("sessions", "last_viewed_at")
