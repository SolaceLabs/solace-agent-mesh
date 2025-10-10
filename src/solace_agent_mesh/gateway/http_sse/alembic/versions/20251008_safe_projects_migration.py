"""Safe projects migration with existence checks

Revision ID: safe_projects_001
Revises: f6e7d8c9b0a1
Create Date: 2025-10-08 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = 'safe_projects_001'
down_revision: Union[str, Sequence[str], None] = '98882922fa59'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Safe upgrade that checks for existing tables and columns."""
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Check if projects table exists
    existing_tables = inspector.get_table_names()
    
    if 'projects' not in existing_tables:
        print("Creating projects table...")
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
    else:
        print("Projects table already exists, skipping creation.")
    
    # Check if project_id column exists in sessions table
    sessions_columns = [col['name'] for col in inspector.get_columns('sessions')]
    
    if 'project_id' not in sessions_columns:
        print("Adding project_id column to sessions table...")
        op.add_column('sessions', sa.Column('project_id', sa.String(), nullable=True))
        
        # Add foreign key constraint if projects table exists
        # Re-check tables after potential creation
        updated_tables = inspector.get_table_names()
        if 'projects' in updated_tables:
            try:
                op.create_foreign_key(
                    'fk_sessions_project_id', 
                    'sessions', 
                    'projects', 
                    ['project_id'], 
                    ['id']
                )
                print("Foreign key constraint added successfully.")
            except Exception as e:
                print(f"Warning: Could not create foreign key constraint: {e}")
    else:
        print("project_id column already exists in sessions table, skipping addition.")
    
    # Handle index cleanup/recreation safely
    _handle_indexes_safely(inspector)


def _handle_indexes_safely(inspector):
    """Safely handle index operations."""
    try:
        # Get existing indexes for sessions table only (chat_messages was dropped by tasks migration)
        existing_tables = inspector.get_table_names()
        
        if 'sessions' in existing_tables:
            sessions_indexes = [idx['name'] for idx in inspector.get_indexes('sessions')]
            
            # Only handle sessions indexes since chat_messages table was already dropped
            sessions_indexes_to_check = [
                'ix_sessions_agent_id',
                'ix_sessions_updated_time',
                'ix_sessions_user_id',
                'ix_sessions_user_id_updated_time'
            ]
            
            for index_name in sessions_indexes_to_check:
                if index_name in sessions_indexes:
                    try:
                        op.drop_index(index_name, table_name='sessions')
                        print(f"Dropped index {index_name}")
                    except Exception as e:
                        print(f"Warning: Could not drop index {index_name}: {e}")
        
        # Recreate essential sessions indexes
        _create_indexes_safe()
        
    except Exception as e:
        print(f"Warning: Index handling encountered issues: {e}")


def _create_indexes_safe():
    """Create indexes safely, ignoring errors if they already exist."""
    # Only create sessions indexes since chat_messages table was dropped by tasks migration
    indexes_to_create = [
        ('ix_sessions_user_id', 'sessions', ['user_id']),
        ('ix_sessions_agent_id', 'sessions', ['agent_id']),
        ('ix_sessions_updated_time', 'sessions', ['updated_time']),
        ('ix_sessions_user_id_updated_time', 'sessions', ['user_id', 'updated_time'])
    ]
    
    for index_name, table_name, columns in indexes_to_create:
        try:
            op.create_index(index_name, table_name, columns)
            print(f"Created index {index_name}")
        except Exception as e:
            print(f"Warning: Could not create index {index_name}: {e}")


def downgrade() -> None:
    """Downgrade schema - removes project-related changes."""
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Check if project_id column exists before trying to drop it
    sessions_columns = [col['name'] for col in inspector.get_columns('sessions')]
    
    if 'project_id' in sessions_columns:
        try:
            # Drop foreign key constraint first
            op.drop_constraint('fk_sessions_project_id', 'sessions', type_='foreignkey')
        except Exception as e:
            print(f"Warning: Could not drop foreign key constraint: {e}")
        
        # Drop the column
        op.drop_column('sessions', 'project_id')
    
    # Check if projects table exists before trying to drop it
    existing_tables = inspector.get_table_names()
    if 'projects' in existing_tables:
        op.drop_table('projects')
    
    # Recreate original indexes
    _recreate_original_indexes()


def _recreate_original_indexes():
    """Recreate the original indexes from before the projects migration."""
    try:
        # Only recreate sessions indexes since chat_messages table doesn't exist after tasks migration
        original_indexes = [
            ('ix_sessions_user_id_updated_time', 'sessions', ['user_id', 'updated_time']),
            ('ix_sessions_user_id', 'sessions', ['user_id']),
            ('ix_sessions_updated_time', 'sessions', ['updated_time']),
            ('ix_sessions_agent_id', 'sessions', ['agent_id'])
        ]
        
        for index_name, table_name, columns in original_indexes:
            try:
                op.create_index(index_name, table_name, columns)
            except Exception as e:
                print(f"Warning: Could not recreate index {index_name}: {e}")
    except Exception as e:
        print(f"Warning: Index recreation encountered issues: {e}")