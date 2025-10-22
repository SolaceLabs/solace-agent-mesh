"""Safe projects migration with existence checks

Revision ID: safe_projects_001
Revises: 20251015_session_idx
Create Date: 2025-10-08 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = 'safe_projects_001'
down_revision: Union[str, Sequence[str], None] = '20251015_session_idx'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Safe upgrade that checks for existing tables and columns."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()
    
    # Create projects table if it doesn't exist
    if 'projects' not in existing_tables:
        op.create_table('projects',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('system_prompt', sa.Text(), nullable=True),
            sa.Column('is_global', sa.Boolean(), nullable=False),
            sa.Column('template_id', sa.String(), nullable=True),
            sa.Column('created_by_user_id', sa.String(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
    
    # Add project_id column to sessions if it doesn't exist
    sessions_columns = [col['name'] for col in inspector.get_columns('sessions')]
    if 'project_id' not in sessions_columns:
        op.add_column('sessions', sa.Column('project_id', sa.String(), nullable=True))
        
        # Add foreign key constraint
        try:
            op.create_foreign_key(
                'fk_sessions_project_id', 
                'sessions', 
                'projects', 
                ['project_id'], 
                ['id']
            )
        except Exception as e:
            print(f"Warning: Could not create foreign key constraint: {e}")


def downgrade() -> None:
    """Downgrade schema - removes project-related changes."""
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Drop project_id column from sessions if it exists
    sessions_columns = [col['name'] for col in inspector.get_columns('sessions')]
    if 'project_id' in sessions_columns:
        try:
            op.drop_constraint('fk_sessions_project_id', 'sessions', type_='foreignkey')
        except Exception as e:
            print(f"Warning: Could not drop foreign key constraint: {e}")
        
        op.drop_column('sessions', 'project_id')
    
    # Drop projects table if it exists
    existing_tables = inspector.get_table_names()
    if 'projects' in existing_tables:
        op.drop_table('projects')
