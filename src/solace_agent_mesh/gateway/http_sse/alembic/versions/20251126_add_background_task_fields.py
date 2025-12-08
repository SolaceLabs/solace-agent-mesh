"""Add background task execution fields

Revision ID: 20251126_background_tasks
Revises: 20251202_versioned_prompt_fields
Create Date: 2025-11-26 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251126_background_tasks'
down_revision = '20251202_versioned_prompt_fields'
branch_labels = None
depends_on = None


def upgrade():
    """Add fields to support background task execution."""
    # Add execution_mode column (foreground | background)
    op.add_column('tasks', sa.Column('execution_mode', sa.String(20), nullable=True, server_default='foreground'))
    
    # Add last_activity_time for timeout detection
    op.add_column('tasks', sa.Column('last_activity_time', sa.BigInteger, nullable=True))
    
    # Add background_execution_enabled flag
    op.add_column('tasks', sa.Column('background_execution_enabled', sa.Boolean, nullable=True, server_default='false'))
    
    # Add max_execution_time_ms for timeout configuration
    op.add_column('tasks', sa.Column('max_execution_time_ms', sa.BigInteger, nullable=True))
    
    # Create index on execution_mode for efficient queries
    op.create_index('idx_tasks_execution_mode', 'tasks', ['execution_mode'])
    
    # Create index on last_activity_time for timeout monitoring
    op.create_index('idx_tasks_last_activity', 'tasks', ['last_activity_time'])


def downgrade():
    """Remove background task execution fields."""
    op.drop_index('idx_tasks_last_activity', table_name='tasks')
    op.drop_index('idx_tasks_execution_mode', table_name='tasks')
    op.drop_column('tasks', 'max_execution_time_ms')
    op.drop_column('tasks', 'background_execution_enabled')
    op.drop_column('tasks', 'last_activity_time')
    op.drop_column('tasks', 'execution_mode')