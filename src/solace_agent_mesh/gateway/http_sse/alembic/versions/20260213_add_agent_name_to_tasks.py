"""Add agent_name column to tasks table

Revision ID: 20260213_add_agent_name
Revises: 20260207_add_sse_event_buffer
Create Date: 2026-02-13

This migration adds the agent_name column to the tasks table to enable
proper task cancellation for timed-out background tasks.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260213_add_agent_name'
down_revision = '20260207_sse_event_buffer'
branch_labels = None
depends_on = None


def upgrade():
    """Add agent_name column to tasks table."""
    # Add agent_name column (nullable to support existing tasks)
    op.add_column('tasks', sa.Column('agent_name', sa.String(255), nullable=True, index=True))
    
    # Add index for efficient queries by agent_name
    op.create_index('idx_tasks_agent_name', 'tasks', ['agent_name'])


def downgrade():
    """Remove agent_name column from tasks table."""
    op.drop_index('idx_tasks_agent_name', table_name='tasks')
    op.drop_column('tasks', 'agent_name')
