"""Normalize scheduled_task_executions.trigger_type to enum-NAME casing

Revision ID: 20260322_trigger_type_fix
Revises: 20260321_execution_trigger_type
Create Date: 2026-03-22 00:00:00.000000

SQLAlchemy's ``SQLEnum`` maps string columns to Python enum members by
**member name** (e.g. ``SCHEDULED``), not by value. The previous migration
(20260321) shipped with ``server_default='scheduled'`` (lowercase value),
which for any deployment that upgraded before the fix left existing rows
with lowercase strings that the ORM cannot load — every SELECT on
``scheduled_task_executions`` raises ``LookupError: 'scheduled' is not
among the defined enum values``.

This migration normalises any lowercase values to their enum-NAME form so
the ORM can round-trip them again. It is idempotent.
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import inspect, text


revision: str = '20260322_trigger_type_fix'
down_revision: Union[str, Sequence[str], None] = '20260321_execution_trigger_type'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if 'scheduled_task_executions' not in inspector.get_table_names():
        return
    columns = {col['name'] for col in inspector.get_columns('scheduled_task_executions')}
    if 'trigger_type' not in columns:
        return

    bind.execute(
        text(
            "UPDATE scheduled_task_executions "
            "SET trigger_type = 'SCHEDULED' "
            "WHERE trigger_type = 'scheduled'"
        )
    )
    bind.execute(
        text(
            "UPDATE scheduled_task_executions "
            "SET trigger_type = 'MANUAL' "
            "WHERE trigger_type = 'manual'"
        )
    )


def downgrade() -> None:
    # Intentionally a no-op: the lowercase state was a bug, not a schema
    # we want to restore. Re-running the downgrade of 20260321 will drop
    # the column entirely if needed.
    pass
