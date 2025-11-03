"""Add project_users table for multi-user project access

Revision ID: 20251023_add_project_users
Revises: 20251023_remove_created_by_user_id
Create Date: 2025-10-23

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_project_users_001'
down_revision: Union[str, None] = 'add_projects_table_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create project_users table to enable multi-user access to projects.
    
    This table tracks which users have access to which projects and their roles.
    It supports future features for collaborative project management.
    """
    # Create project_users table
    op.create_table(
        'project_users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('added_at', sa.BigInteger(), nullable=False),
        sa.Column('added_by_user_id', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('project_id', 'user_id', name='uq_project_user')
    )
    
    # Create indexes for efficient queries
    op.create_index(
        'ix_project_users_project_id',
        'project_users',
        ['project_id']
    )
    
    op.create_index(
        'ix_project_users_user_id',
        'project_users',
        ['user_id']
    )
    
    # Create composite index for common query pattern (user accessing specific project)
    op.create_index(
        'ix_project_users_user_project',
        'project_users',
        ['user_id', 'project_id']
    )


def downgrade() -> None:
    """
    Remove project_users table and related indexes.
    """
    # Drop indexes first
    op.drop_index('ix_project_users_user_project', table_name='project_users')
    op.drop_index('ix_project_users_user_id', table_name='project_users')
    op.drop_index('ix_project_users_project_id', table_name='project_users')
    
    # Drop the table
    op.drop_table('project_users')