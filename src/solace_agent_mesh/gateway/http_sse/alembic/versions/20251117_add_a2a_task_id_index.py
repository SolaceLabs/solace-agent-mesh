"""Add index on a2a_task_id for efficient execution lookups

Revision ID: 20251117_add_a2a_task_id_index
Revises: 20251117_create_scheduled_tasks_tables
Create Date: 2025-11-17 17:23:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251117_add_a2a_task_id_index'
down_revision = '20251117_create_scheduled_tasks_tables'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add index on a2a_task_id column for efficient lookups by the stateless result collector.
    
    This index is critical for K8S deployments where the result collector needs to
    quickly find pending/running executions by their A2A task ID without maintaining
    in-memory state.
    """
    # Create partial index for pending and running executions only
    # This keeps the index small and efficient
    op.create_index(
        'idx_scheduled_task_executions_a2a_task_id_active',
        'scheduled_task_executions',
        ['a2a_task_id'],
        unique=False,
        postgresql_where=sa.text("status IN ('pending', 'running')")
    )


def downgrade():
    """Remove the a2a_task_id index."""
    op.drop_index(
        'idx_scheduled_task_executions_a2a_task_id_active',
        table_name='scheduled_task_executions'
    )