"""add retention indexes

Revision ID: add_retention_indexes
Revises: 20250910_d5b3f8f2e9a0
Create Date: 2025-01-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_retention_indexes'
down_revision = '20250910_d5b3f8f2e9a0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add indexes to support efficient data retention cleanup queries."""
    # Add index on tasks.start_time for efficient TTL queries
    op.create_index(
        'ix_tasks_start_time',
        'tasks',
        ['start_time'],
        unique=False
    )
    
    # Add index on feedback.created_time for efficient TTL queries
    op.create_index(
        'ix_feedback_created_time',
        'feedback',
        ['created_time'],
        unique=False
    )


def downgrade() -> None:
    """Remove retention indexes."""
    # Remove index on feedback.created_time
    op.drop_index('ix_feedback_created_time', table_name='feedback')
    
    # Remove index on tasks.start_time
    op.drop_index('ix_tasks_start_time', table_name='tasks')
