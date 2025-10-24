"""Remove is_global column from projects table

Revision ID: remove_is_global_001
Revises: safe_projects_001
Create Date: 2025-10-23 14:16:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = 'remove_is_global_001'
down_revision: Union[str, Sequence[str], None] = 'safe_projects_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove is_global column from projects table if it exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Check if projects table exists
    existing_tables = inspector.get_table_names()
    if 'projects' in existing_tables:
        # Check if is_global column exists
        projects_columns = [col['name'] for col in inspector.get_columns('projects')]
        if 'is_global' in projects_columns:
            op.drop_column('projects', 'is_global')


def downgrade() -> None:
    """Add is_global column back to projects table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Check if projects table exists
    existing_tables = inspector.get_table_names()
    if 'projects' in existing_tables:
        # Check if is_global column doesn't exist
        projects_columns = [col['name'] for col in inspector.get_columns('projects')]
        if 'is_global' not in projects_columns:
            op.add_column('projects', sa.Column('is_global', sa.Boolean(), nullable=False, server_default='0'))