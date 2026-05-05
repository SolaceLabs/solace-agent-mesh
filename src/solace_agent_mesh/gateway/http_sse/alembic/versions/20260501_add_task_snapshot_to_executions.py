"""Add task_snapshot column to scheduled_task_executions

Revision ID: 20260501_task_snapshot
Revises: 20260417_last_viewed_at
Create Date: 2026-05-01 00:00:00.000000

Persists the task config that was used for each execution so the UI can
show a per-execution snapshot of name/description/schedule/agent/instructions
even if the task is later edited or deleted. Existing rows stay NULL — the
frontend falls back to the live task config for executions that ran before
this column existed.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = '20260501_task_snapshot'
down_revision: Union[str, Sequence[str], None] = '20260417_last_viewed_at'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if 'scheduled_task_executions' not in inspector.get_table_names():
        return

    existing = {col['name'] for col in inspector.get_columns('scheduled_task_executions')}
    if 'task_snapshot' in existing:
        return

    dialect_name = bind.dialect.name
    if dialect_name == 'sqlite':
        with op.batch_alter_table('scheduled_task_executions') as batch_op:
            batch_op.add_column(sa.Column('task_snapshot', sa.JSON(), nullable=True))
    else:
        op.add_column(
            'scheduled_task_executions',
            sa.Column('task_snapshot', sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if 'scheduled_task_executions' not in inspector.get_table_names():
        return

    existing = {col['name'] for col in inspector.get_columns('scheduled_task_executions')}
    if 'task_snapshot' not in existing:
        return

    dialect_name = bind.dialect.name
    if dialect_name == 'sqlite':
        with op.batch_alter_table('scheduled_task_executions') as batch_op:
            batch_op.drop_column('task_snapshot')
    else:
        op.drop_column('scheduled_task_executions', 'task_snapshot')
