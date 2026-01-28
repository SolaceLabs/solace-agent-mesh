"""Add gateway_type columns to sessions and chat_tasks tables

Revision ID: 20260128_gateway_type
Revises: 20251202_versioned_prompt_fields
Create Date: 2026-01-28

This migration adds gateway_type and external_context_id columns to support
persisting conversations from external gateways (Slack, Teams, etc.) in the web UI.
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20260128_gateway_type"
down_revision: str | Sequence[str] | None = "20251202_versioned_prompt_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add gateway_type and external_context_id columns."""
    
    # Add columns to sessions table
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('gateway_type', sa.String(length=50), nullable=False, server_default='web')
        )
        batch_op.add_column(
            sa.Column('external_context_id', sa.String(length=500), nullable=True)
        )
    
    # Create indexes for sessions table
    op.create_index('ix_sessions_gateway_type', 'sessions', ['gateway_type'])
    op.create_index('ix_sessions_external_context_id', 'sessions', ['external_context_id'])
    
    # Add column to chat_tasks table
    with op.batch_alter_table('chat_tasks', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('gateway_type', sa.String(length=50), nullable=False, server_default='web')
        )
    
    # Create index for chat_tasks table
    op.create_index('ix_chat_tasks_gateway_type', 'chat_tasks', ['gateway_type'])


def downgrade() -> None:
    """Remove gateway_type and external_context_id columns."""
    
    # Drop indexes first
    op.drop_index('ix_chat_tasks_gateway_type', table_name='chat_tasks')
    op.drop_index('ix_sessions_external_context_id', table_name='sessions')
    op.drop_index('ix_sessions_gateway_type', table_name='sessions')
    
    # Remove columns from chat_tasks table
    with op.batch_alter_table('chat_tasks', schema=None) as batch_op:
        batch_op.drop_column('gateway_type')
    
    # Remove columns from sessions table
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.drop_column('external_context_id')
        batch_op.drop_column('gateway_type')
