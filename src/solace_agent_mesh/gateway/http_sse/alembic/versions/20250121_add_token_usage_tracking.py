"""Add token usage tracking tables

Revision ID: 20250121_token_usage
Revises: 20251115_add_parent_task_id
Create Date: 2025-01-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import JSON

# revision identifiers, used by Alembic.
revision = '20250121_token_usage'
down_revision = '20251115_add_parent_task_id'
branch_labels = None
depends_on = None


def upgrade():
    """Create token usage tracking tables."""
    
    # Create user_quotas table
    op.create_table(
        'user_quotas',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('monthly_quota', sa.BigInteger(), nullable=True),
        sa.Column('account_type', sa.String(), nullable=False, server_default='free'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('quota_reset_day', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.Column('last_reset_at', sa.BigInteger(), nullable=True),
        sa.Column('custom_settings', JSON(), nullable=True),
        sa.PrimaryKeyConstraint('user_id')
    )
    op.create_index('idx_user_quotas_account_type', 'user_quotas', ['account_type'])
    op.create_index('idx_user_quotas_is_active', 'user_quotas', ['is_active'])
    op.create_index('idx_user_quotas_user_id', 'user_quotas', ['user_id'])
    
    # Create monthly_usage table
    op.create_table(
        'monthly_usage',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('month', sa.String(), nullable=False),
        sa.Column('total_usage', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('prompt_usage', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('completion_usage', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('cached_usage', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('usage_by_model', JSON(), nullable=True),
        sa.Column('usage_by_source', JSON(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.Column('last_reset_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'month', name='uq_user_month')
    )
    op.create_index('idx_monthly_usage_user_month', 'monthly_usage', ['user_id', 'month'])
    op.create_index('idx_monthly_usage_month', 'monthly_usage', ['month'])
    op.create_index('idx_monthly_usage_user_id', 'monthly_usage', ['user_id'])
    
    # Create token_transactions table
    op.create_table(
        'token_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('task_id', sa.String(), nullable=True),
        sa.Column('transaction_type', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('raw_tokens', sa.Integer(), nullable=False),
        sa.Column('token_cost', sa.BigInteger(), nullable=False),
        sa.Column('rate', sa.Float(), nullable=False),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('tool_name', sa.String(), nullable=True),
        sa.Column('context', sa.String(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('transaction_metadata', JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_token_tx_user_created', 'token_transactions', ['user_id', 'created_at'])
    op.create_index('idx_token_tx_task', 'token_transactions', ['task_id'])
    op.create_index('idx_token_tx_model', 'token_transactions', ['model'])
    op.create_index('idx_token_tx_created', 'token_transactions', ['created_at'])
    op.create_index('idx_token_tx_user_id', 'token_transactions', ['user_id'])


def downgrade():
    """Drop token usage tracking tables."""
    
    # Drop indexes first
    op.drop_index('idx_token_tx_user_id', table_name='token_transactions')
    op.drop_index('idx_token_tx_created', table_name='token_transactions')
    op.drop_index('idx_token_tx_model', table_name='token_transactions')
    op.drop_index('idx_token_tx_task', table_name='token_transactions')
    op.drop_index('idx_token_tx_user_created', table_name='token_transactions')
    
    op.drop_index('idx_monthly_usage_user_id', table_name='monthly_usage')
    op.drop_index('idx_monthly_usage_month', table_name='monthly_usage')
    op.drop_index('idx_monthly_usage_user_month', table_name='monthly_usage')
    
    op.drop_index('idx_user_quotas_user_id', table_name='user_quotas')
    op.drop_index('idx_user_quotas_is_active', table_name='user_quotas')
    op.drop_index('idx_user_quotas_account_type', table_name='user_quotas')
    
    # Drop tables
    op.drop_table('token_transactions')
    op.drop_table('monthly_usage')
    op.drop_table('user_quotas')