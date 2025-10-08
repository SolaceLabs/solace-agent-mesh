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
down_revision: Union[str, Sequence[str], None] = 'f6e7d8c9b0a1'
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
        # Get existing indexes
        sessions_indexes = [idx['name'] for idx in inspector.get_indexes('sessions')]
        chat_messages_indexes = [idx['name'] for idx in inspector.get_indexes('chat_messages')]
        
        # Drop indexes that might conflict (only if they exist)
        indexes_to_drop = [
            ('ix_chat_messages_created_time', 'chat_messages'),
            ('ix_chat_messages_session_id', 'chat_messages'),
            ('ix_chat_messages_session_id_created_time', 'chat_messages'),
            ('ix_sessions_agent_id', 'sessions'),
            ('ix_sessions_updated_time', 'sessions'),
            ('ix_sessions_user_id', 'sessions'),
            ('ix_sessions_user_id_updated_time', 'sessions')
        ]
        
        for index_name, table_name in indexes_to_drop:
            relevant_indexes = sessions_indexes if table_name == 'sessions' else chat_messages_indexes
            if index_name in relevant_indexes:
                try:
                    op.drop_index(index_name, table_name=table_name)
                    print(f"Dropped index {index_name}")
                except Exception as e:
                    print(f"Warning: Could not drop index {index_name}: {e}")
        
        # Recreate essential indexes
        _create_indexes_safe()
        
    except Exception as e:
        print(f"Warning: Index handling encountered issues: {e}")


def _create_indexes_safe():
    """Create indexes safely, ignoring errors if they already exist."""
    indexes_to_create = [
        ('ix_sessions_user_id', 'sessions', ['user_id']),
        ('ix_sessions_agent_id', 'sessions', ['agent_id']),
        ('ix_sessions_updated_time', 'sessions', ['updated_time']),
        ('ix_sessions_user_id_updated_time', 'sessions', ['user_id', 'updated_time']),
        ('ix_chat_messages_session_id', 'chat_messages', ['session_id']),
        ('ix_chat_messages_created_time', 'chat_messages', ['created_time']),
        ('ix_chat_messages_session_id_created_time', 'chat_messages', ['session_id', 'created_time'])
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
        original_indexes = [
            ('ix_sessions_user_id_updated_time', 'sessions', ['user_id', 'updated_time']),
            ('ix_sessions_user_id', 'sessions', ['user_id']),
            ('ix_sessions_updated_time', 'sessions', ['updated_time']),
            ('ix_sessions_agent_id', 'sessions', ['agent_id']),
            ('ix_chat_messages_session_id_created_time', 'chat_messages', ['session_id', 'created_time']),
            ('ix_chat_messages_session_id', 'chat_messages', ['session_id']),
            ('ix_chat_messages_created_time', 'chat_messages', ['created_time'])
        ]
        
        for index_name, table_name, columns in original_indexes:
            try:
                op.create_index(index_name, table_name, columns)
            except Exception as e:
                print(f"Warning: Could not recreate index {index_name}: {e}")
    except Exception as e:
        print(f"Warning: Index recreation encountered issues: {e}")