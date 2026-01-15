"""Add resource_access_shares table for resource sharing functionality

Revision ID: 20260115_resource_sharing
Revises: 20251126_background_tasks
Create Date: 2026-01-15

This table stores resource sharing permissions for projects and other resources.
Enterprise implementation uses this table to track which users have access to which resources.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '20260115_resource_sharing'
down_revision: Union[str, None] = '20251126_background_tasks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'resource_access_shares',
        sa.Column('resource_id', sa.String(255), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False, server_default='project'),
        sa.Column('shared_with_user_id', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('shared_by_user_id', sa.String(255), nullable=False),
        sa.Column('shared_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('resource_id', 'resource_type', 'shared_with_user_id'),
    )

    op.create_index('ix_resource_access_shares_resource', 'resource_access_shares', ['resource_id', 'resource_type'])
    op.create_index('ix_resource_access_shares_shared_with', 'resource_access_shares', ['shared_with_user_id'])
    op.create_index('ix_resource_access_shares_shared_by', 'resource_access_shares', ['shared_by_user_id'])
    op.create_index('ix_resource_access_shares_role', 'resource_access_shares', ['role'])
    op.create_index('ix_resource_access_shares_resource_type', 'resource_access_shares', ['resource_type'])


def downgrade() -> None:
    op.drop_index('ix_resource_access_shares_resource_type', 'resource_access_shares')
    op.drop_index('ix_resource_access_shares_role', 'resource_access_shares')
    op.drop_index('ix_resource_access_shares_shared_by', 'resource_access_shares')
    op.drop_index('ix_resource_access_shares_shared_with', 'resource_access_shares')
    op.drop_index('ix_resource_access_shares_resource', 'resource_access_shares')
    op.drop_table('resource_access_shares')
