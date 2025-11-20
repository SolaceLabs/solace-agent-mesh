"""Create scheduled tasks tables

Revision ID: 20251117_create_scheduled_tasks_tables
Revises: 20251108_prompt_tables_complete
Create Date: 2025-11-17

This migration creates the infrastructure for scheduled tasks:
- scheduled_tasks: Task definitions with scheduling configuration
- scheduled_task_executions: Individual execution records
- scheduler_locks: Distributed leader election lock
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20251117_create_scheduled_tasks_tables"
down_revision: str | Sequence[str] | None = "20251108_prompt_tables_complete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create scheduled tasks schema."""
    
    # 1. Create scheduled_tasks table
    op.create_table(
        'scheduled_tasks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        
        # Ownership & Multi-tenancy
        sa.Column('namespace', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=False),
        
        # Scheduling Configuration
        sa.Column('schedule_type', sa.String(), nullable=False),
        sa.Column('schedule_expression', sa.String(), nullable=False),
        sa.Column('timezone', sa.String(), nullable=False, server_default='UTC'),
        
        # Task Configuration
        sa.Column('target_agent_name', sa.String(), nullable=False),
        sa.Column('task_message', sa.JSON(), nullable=False),
        sa.Column('task_metadata', sa.JSON(), nullable=True),
        
        # Execution Control
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('retry_delay_seconds', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='3600'),
        
        # Notification Configuration
        sa.Column('notification_config', sa.JSON(), nullable=True),
        
        # Timestamps (epoch milliseconds)
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.Column('next_run_at', sa.BigInteger(), nullable=True),
        sa.Column('last_run_at', sa.BigInteger(), nullable=True),
        
        # Soft delete
        sa.Column('deleted_at', sa.BigInteger(), nullable=True),
        sa.Column('deleted_by', sa.String(), nullable=True),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for scheduled_tasks
    op.create_index('ix_scheduled_tasks_name', 'scheduled_tasks', ['name'], unique=False)
    op.create_index('ix_scheduled_tasks_namespace', 'scheduled_tasks', ['namespace'], unique=False)
    op.create_index('ix_scheduled_tasks_user_id', 'scheduled_tasks', ['user_id'], unique=False)
    op.create_index('ix_scheduled_tasks_schedule_type', 'scheduled_tasks', ['schedule_type'], unique=False)
    op.create_index('ix_scheduled_tasks_target_agent_name', 'scheduled_tasks', ['target_agent_name'], unique=False)
    op.create_index('ix_scheduled_tasks_enabled', 'scheduled_tasks', ['enabled'], unique=False)
    op.create_index('ix_scheduled_tasks_next_run_at', 'scheduled_tasks', ['next_run_at'], unique=False)
    
    # Composite index for efficient scheduling queries
    op.create_index(
        'ix_scheduled_tasks_enabled_next_run',
        'scheduled_tasks',
        ['enabled', 'next_run_at'],
        unique=False
    )
    
    # Composite index for user queries
    op.create_index(
        'ix_scheduled_tasks_namespace_user',
        'scheduled_tasks',
        ['namespace', 'user_id'],
        unique=False
    )
    
    # 2. Create scheduled_task_executions table
    op.create_table(
        'scheduled_task_executions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('scheduled_task_id', sa.String(), nullable=False),
        
        # Execution Details
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('a2a_task_id', sa.String(), nullable=True),
        
        # Timing (epoch milliseconds)
        sa.Column('scheduled_for', sa.BigInteger(), nullable=False),
        sa.Column('started_at', sa.BigInteger(), nullable=True),
        sa.Column('completed_at', sa.BigInteger(), nullable=True),
        
        # Results
        sa.Column('result_summary', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        
        # Artifacts & Notifications
        sa.Column('artifacts', sa.JSON(), nullable=True),
        sa.Column('notifications_sent', sa.JSON(), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['scheduled_task_id'],
            ['scheduled_tasks.id'],
            ondelete='CASCADE'
        )
    )
    
    # Indexes for scheduled_task_executions
    op.create_index(
        'ix_scheduled_task_executions_scheduled_task_id',
        'scheduled_task_executions',
        ['scheduled_task_id'],
        unique=False
    )
    op.create_index(
        'ix_scheduled_task_executions_status',
        'scheduled_task_executions',
        ['status'],
        unique=False
    )
    op.create_index(
        'ix_scheduled_task_executions_a2a_task_id',
        'scheduled_task_executions',
        ['a2a_task_id'],
        unique=False
    )
    op.create_index(
        'ix_scheduled_task_executions_scheduled_for',
        'scheduled_task_executions',
        ['scheduled_for'],
        unique=False
    )
    
    # Composite index for execution history queries
    op.create_index(
        'ix_scheduled_task_executions_task_scheduled',
        'scheduled_task_executions',
        ['scheduled_task_id', 'scheduled_for'],
        unique=False
    )
    
    # 3. Create scheduler_locks table (for distributed leader election)
    op.create_table(
        'scheduler_locks',
        sa.Column('id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('leader_id', sa.String(), nullable=False),
        sa.Column('leader_namespace', sa.String(), nullable=False),
        sa.Column('acquired_at', sa.BigInteger(), nullable=False),
        sa.Column('expires_at', sa.BigInteger(), nullable=False),
        sa.Column('heartbeat_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Index for lock expiration checks
    op.create_index(
        'ix_scheduler_locks_expires_at',
        'scheduler_locks',
        ['expires_at'],
        unique=False
    )


def downgrade() -> None:
    """Remove scheduled tasks schema."""
    
    # Drop scheduler_locks
    op.drop_index('ix_scheduler_locks_expires_at', table_name='scheduler_locks')
    op.drop_table('scheduler_locks')
    
    # Drop scheduled_task_executions
    op.drop_index('ix_scheduled_task_executions_task_scheduled', table_name='scheduled_task_executions')
    op.drop_index('ix_scheduled_task_executions_scheduled_for', table_name='scheduled_task_executions')
    op.drop_index('ix_scheduled_task_executions_a2a_task_id', table_name='scheduled_task_executions')
    op.drop_index('ix_scheduled_task_executions_status', table_name='scheduled_task_executions')
    op.drop_index('ix_scheduled_task_executions_scheduled_task_id', table_name='scheduled_task_executions')
    op.drop_table('scheduled_task_executions')
    
    # Drop scheduled_tasks
    op.drop_index('ix_scheduled_tasks_namespace_user', table_name='scheduled_tasks')
    op.drop_index('ix_scheduled_tasks_enabled_next_run', table_name='scheduled_tasks')
    op.drop_index('ix_scheduled_tasks_next_run_at', table_name='scheduled_tasks')
    op.drop_index('ix_scheduled_tasks_enabled', table_name='scheduled_tasks')
    op.drop_index('ix_scheduled_tasks_target_agent_name', table_name='scheduled_tasks')
    op.drop_index('ix_scheduled_tasks_schedule_type', table_name='scheduled_tasks')
    op.drop_index('ix_scheduled_tasks_user_id', table_name='scheduled_tasks')
    op.drop_index('ix_scheduled_tasks_namespace', table_name='scheduled_tasks')
    op.drop_index('ix_scheduled_tasks_name', table_name='scheduled_tasks')
    op.drop_table('scheduled_tasks')