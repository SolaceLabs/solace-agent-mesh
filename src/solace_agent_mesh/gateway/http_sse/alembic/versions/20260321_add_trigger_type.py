"""Add trigger_type and triggered_by to scheduled_task_executions

Revision ID: 20260321_execution_trigger_type
Revises: 20260319_scheduled_tasks
Create Date: 2026-03-21 00:00:00.000000

Adds provenance tracking to execution rows so manual "Run Now" triggers
can be distinguished from scheduled fires in the execution history UI.

- trigger_type: 'scheduled' | 'manual' (NOT NULL, defaults to 'scheduled'
  for all existing rows — the prior behavior was scheduled-only).
- triggered_by: user_id for manual triggers (NULL for scheduled).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = '20260321_execution_trigger_type'
down_revision: Union[str, Sequence[str], None] = '20260319_scheduled_tasks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if 'scheduled_task_executions' not in inspector.get_table_names():
        return

    existing = {col['name'] for col in inspector.get_columns('scheduled_task_executions')}

    dialect_name = bind.dialect.name
    if dialect_name == 'sqlite':
        with op.batch_alter_table('scheduled_task_executions') as batch_op:
            if 'trigger_type' not in existing:
                batch_op.add_column(
                    sa.Column(
                        'trigger_type',
                        sa.String(length=16),
                        nullable=False,
                        server_default='SCHEDULED',
                    )
                )
            if 'triggered_by' not in existing:
                batch_op.add_column(sa.Column('triggered_by', sa.String(length=255), nullable=True))
        # Index creation outside batch to avoid batch-mode quirks
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('scheduled_task_executions')}
        if 'ix_scheduled_task_executions_trigger_type' not in existing_indexes:
            op.create_index(
                'ix_scheduled_task_executions_trigger_type',
                'scheduled_task_executions',
                ['trigger_type'],
                unique=False,
            )
    else:
        if 'trigger_type' not in existing:
            op.add_column(
                'scheduled_task_executions',
                sa.Column(
                    'trigger_type',
                    sa.String(length=16),
                    nullable=False,
                    server_default='SCHEDULED',
                ),
            )
            op.create_index(
                'ix_scheduled_task_executions_trigger_type',
                'scheduled_task_executions',
                ['trigger_type'],
                unique=False,
            )
        if 'triggered_by' not in existing:
            op.add_column(
                'scheduled_task_executions',
                sa.Column('triggered_by', sa.String(length=255), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if 'scheduled_task_executions' not in inspector.get_table_names():
        return

    existing_indexes = {idx['name'] for idx in inspector.get_indexes('scheduled_task_executions')}
    if 'ix_scheduled_task_executions_trigger_type' in existing_indexes:
        op.drop_index(
            'ix_scheduled_task_executions_trigger_type',
            table_name='scheduled_task_executions',
        )

    dialect_name = bind.dialect.name
    existing = {col['name'] for col in inspector.get_columns('scheduled_task_executions')}
    if dialect_name == 'sqlite':
        with op.batch_alter_table('scheduled_task_executions') as batch_op:
            if 'triggered_by' in existing:
                batch_op.drop_column('triggered_by')
            if 'trigger_type' in existing:
                batch_op.drop_column('trigger_type')
    else:
        if 'triggered_by' in existing:
            op.drop_column('scheduled_task_executions', 'triggered_by')
        if 'trigger_type' in existing:
            op.drop_column('scheduled_task_executions', 'trigger_type')
