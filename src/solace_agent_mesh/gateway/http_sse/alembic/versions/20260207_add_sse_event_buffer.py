"""Add SSE event buffer table for background task event replay

Revision ID: 20260207_sse_event_buffer
Revises: 20260204_fix_command_constraint
Create Date: 2026-02-07 00:00:00.000000

This migration adds a table to persist SSE events for background tasks.
When a background task completes while the user is away, the events are
stored in this table and replayed when the user returns to the session.
This ensures the frontend processes events through the same code path
as live streaming, guaranteeing consistency.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260207_sse_event_buffer'
down_revision = '20260204_fix_command_constraint'
branch_labels = None
depends_on = None


def upgrade():
    """Add SSE event buffer table and related columns."""
    
    # Create sse_event_buffer table
    op.create_table(
        'sse_event_buffer',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.String(255), nullable=False),
        sa.Column('session_id', sa.String(255), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('event_sequence', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.BigInteger(), nullable=False),  # Epoch milliseconds
        sa.Column('consumed', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column('consumed_at', sa.BigInteger(), nullable=True),  # Epoch milliseconds
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id', 'event_sequence', name='sse_event_buffer_task_seq_unique')
    )
    
    # Create indexes for efficient queries
    op.create_index('idx_sse_event_buffer_task_id', 'sse_event_buffer', ['task_id'])
    op.create_index('idx_sse_event_buffer_session_id', 'sse_event_buffer', ['session_id'])
    op.create_index('idx_sse_event_buffer_consumed', 'sse_event_buffer', ['consumed'])
    op.create_index('idx_sse_event_buffer_created_at', 'sse_event_buffer', ['created_at'])
    
    # Add columns to tasks table for tracking event buffer state
    op.add_column('tasks', sa.Column('session_id', sa.String(255), nullable=True))
    op.add_column('tasks', sa.Column('events_buffered', sa.Boolean(), nullable=True, server_default=sa.text('FALSE')))
    op.add_column('tasks', sa.Column('events_consumed', sa.Boolean(), nullable=True, server_default=sa.text('FALSE')))
    
    # Create indexes for efficient queries on event buffer state
    op.create_index('idx_tasks_session_id', 'tasks', ['session_id'])
    op.create_index('idx_tasks_events_buffered', 'tasks', ['events_buffered'])


def downgrade():
    """Remove SSE event buffer table and related columns."""
    
    # Remove columns from tasks table
    op.drop_index('idx_tasks_events_buffered', table_name='tasks')
    op.drop_index('idx_tasks_session_id', table_name='tasks')
    op.drop_column('tasks', 'events_consumed')
    op.drop_column('tasks', 'events_buffered')
    op.drop_column('tasks', 'session_id')
    
    # Remove indexes from sse_event_buffer table
    op.drop_index('idx_sse_event_buffer_created_at', table_name='sse_event_buffer')
    op.drop_index('idx_sse_event_buffer_consumed', table_name='sse_event_buffer')
    op.drop_index('idx_sse_event_buffer_session_id', table_name='sse_event_buffer')
    op.drop_index('idx_sse_event_buffer_task_id', table_name='sse_event_buffer')
    
    # Drop sse_event_buffer table
    op.drop_table('sse_event_buffer')
