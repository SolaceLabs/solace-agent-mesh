"""Add soft delete and search support for sessions and projects

Revision ID: add_soft_delete_search_001
Revises: remove_is_global_001
Create Date: 2025-10-23 16:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = 'soft_del_search_001'
down_revision: Union[str, Sequence[str], None] = 'add_project_users_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add soft delete columns and search indexes."""
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Add soft delete columns to sessions table
    if 'sessions' in inspector.get_table_names():
        sessions_columns = [col['name'] for col in inspector.get_columns('sessions')]
        
        if 'deleted_at' not in sessions_columns:
            op.add_column('sessions', sa.Column('deleted_at', sa.BigInteger(), nullable=True))
        
        if 'deleted_by' not in sessions_columns:
            op.add_column('sessions', sa.Column('deleted_by', sa.String(), nullable=True))
        
        # Create index on deleted_at for efficient filtering
        try:
            op.create_index('ix_sessions_deleted_at', 'sessions', ['deleted_at'])
        except Exception:
            pass  # Index might already exist
        
        # Create composite index for user queries with soft delete
        try:
            op.create_index('ix_sessions_user_deleted', 'sessions', ['user_id', 'deleted_at'])
        except Exception:
            pass
    
    # Add soft delete columns to projects table
    if 'projects' in inspector.get_table_names():
        projects_columns = [col['name'] for col in inspector.get_columns('projects')]
        
        if 'deleted_at' not in projects_columns:
            op.add_column('projects', sa.Column('deleted_at', sa.BigInteger(), nullable=True))
        
        if 'deleted_by' not in projects_columns:
            op.add_column('projects', sa.Column('deleted_by', sa.String(), nullable=True))
        
        # Create index on deleted_at for efficient filtering
        try:
            op.create_index('ix_projects_deleted_at', 'projects', ['deleted_at'])
        except Exception:
            pass
        
        # Create composite index for user queries with soft delete
        try:
            op.create_index('ix_projects_user_deleted', 'projects', ['user_id', 'deleted_at'])
        except Exception:
            pass


def downgrade() -> None:
    """Remove soft delete columns and search indexes."""
    bind = op.get_bind()
    inspector = inspect(bind)

    # Drop soft delete indexes from sessions
    if 'sessions' in inspector.get_table_names():
        try:
            op.drop_index('ix_sessions_user_deleted', table_name='sessions')
        except Exception:
            pass
        
        try:
            op.drop_index('ix_sessions_deleted_at', table_name='sessions')
        except Exception:
            pass
        
        sessions_columns = [col['name'] for col in inspector.get_columns('sessions')]
        if 'deleted_by' in sessions_columns:
            op.drop_column('sessions', 'deleted_by')
        if 'deleted_at' in sessions_columns:
            op.drop_column('sessions', 'deleted_at')
    
    # Drop indexes and columns from projects
    if 'projects' in inspector.get_table_names():
        try:
            op.drop_index('ix_projects_user_deleted', table_name='projects')
        except Exception:
            pass
        
        try:
            op.drop_index('ix_projects_deleted_at', table_name='projects')
        except Exception:
            pass
        
        projects_columns = [col['name'] for col in inspector.get_columns('projects')]
        if 'deleted_by' in projects_columns:
            op.drop_column('projects', 'deleted_by')
        if 'deleted_at' in projects_columns:
            op.drop_column('projects', 'deleted_at')