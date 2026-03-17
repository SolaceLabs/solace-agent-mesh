"""Add projects table and project_id to sessions

Revision ID: add_projects_table_001
Revises: 20251015_session_idx
Create Date: 2025-10-24 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = 'add_projects_table_001'
down_revision: Union[str, Sequence[str], None] = '20251015_session_idx'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create projects table and add project_id to sessions."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()
    dialect_name = bind.dialect.name

    if dialect_name == 'sqlite':
        _upgrade_sqlite(inspector, existing_tables)
    elif dialect_name == 'mysql':
        _upgrade_mysql(inspector, existing_tables)
    else:
        _upgrade_postgresql(inspector, existing_tables)


def _upgrade_postgresql(inspector, existing_tables) -> None:
    """PostgreSQL upgrade (original working code)."""
    # Create projects table if it doesn't exist
    if 'projects' not in existing_tables:
        op.create_table('projects',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('system_prompt', sa.Text(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )

    # Add project_id column to sessions if it doesn't exist
    sessions_columns = [col['name'] for col in inspector.get_columns('sessions')]
    if 'project_id' not in sessions_columns:
        op.add_column('sessions', sa.Column('project_id', sa.String(), nullable=True))
        op.create_index('ix_sessions_project_id', 'sessions', ['project_id'])
        op.create_foreign_key(
            'fk_sessions_project_id',
            'sessions',
            'projects',
            ['project_id'],
            ['id']
        )


def _upgrade_sqlite(inspector, existing_tables) -> None:
    """SQLite upgrade with table recreation (original working code)."""
    # Create projects table if it doesn't exist
    if 'projects' not in existing_tables:
        op.create_table('projects',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('system_prompt', sa.Text(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )

    # Add project_id column to sessions if it doesn't exist
    sessions_columns = [col['name'] for col in inspector.get_columns('sessions')]
    if 'project_id' not in sessions_columns:
        # SQLite doesn't support ALTER TABLE ADD CONSTRAINT, recreate table
        op.create_table(
            'sessions_new',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('name', sa.String(), nullable=True),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('agent_id', sa.String(), nullable=True),
            sa.Column('created_time', sa.BigInteger(), nullable=False),
            sa.Column('updated_time', sa.BigInteger(), nullable=False),
            sa.Column('project_id', sa.String(), nullable=True),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
            sa.PrimaryKeyConstraint('id')
        )

        # Copy data from old table
        op.execute("""
            INSERT INTO sessions_new (id, name, user_id, agent_id, created_time, updated_time)
            SELECT id, name, user_id, agent_id, created_time, updated_time
            FROM sessions
        """)

        # Drop old table
        op.drop_table('sessions')

        # Rename new table
        op.rename_table('sessions_new', 'sessions')

        # Recreate indexes
        op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])
        op.create_index('ix_sessions_project_id', 'sessions', ['project_id'])


def _upgrade_mysql(inspector, existing_tables) -> None:
    """MySQL upgrade with VARCHAR lengths."""
    # Create projects table if it doesn't exist
    if 'projects' not in existing_tables:
        op.create_table('projects',
            sa.Column('id', sa.String(36), nullable=False),  # UUID
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('user_id', sa.String(255), nullable=False),  # user ID
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('system_prompt', sa.Text(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )

    # Add project_id column to sessions if it doesn't exist
    sessions_columns = [col['name'] for col in inspector.get_columns('sessions')]
    if 'project_id' not in sessions_columns:
        op.add_column('sessions', sa.Column('project_id', sa.String(36), nullable=True))  # UUID
        op.create_index('ix_sessions_project_id', 'sessions', ['project_id'])
        op.create_foreign_key(
            'fk_sessions_project_id',
            'sessions',
            'projects',
            ['project_id'],
            ['id']
        )


def downgrade() -> None:
    """Downgrade schema - removes project-related changes."""
    bind = op.get_bind()
    inspector = inspect(bind)
    dialect_name = bind.dialect.name

    # Drop project_id column from sessions if it exists
    sessions_columns = [col['name'] for col in inspector.get_columns('sessions')]
    if 'project_id' in sessions_columns:
        if dialect_name == 'sqlite':
            # SQLite doesn't support ALTER TABLE DROP CONSTRAINT, recreate table
            op.create_table(
                'sessions_old',
                sa.Column('id', sa.String(), nullable=False),
                sa.Column('name', sa.String(), nullable=True),
                sa.Column('user_id', sa.String(), nullable=False),
                sa.Column('agent_id', sa.String(), nullable=True),
                sa.Column('created_time', sa.BigInteger(), nullable=False),
                sa.Column('updated_time', sa.BigInteger(), nullable=False),
                sa.PrimaryKeyConstraint('id')
            )

            # Copy data from current table (excluding project_id)
            op.execute("""
                INSERT INTO sessions_old (id, name, user_id, agent_id, created_time, updated_time)
                SELECT id, name, user_id, agent_id, created_time, updated_time
                FROM sessions
            """)

            # Drop current table
            op.drop_table('sessions')

            # Rename old table back
            op.rename_table('sessions_old', 'sessions')

            # Recreate index on user_id
            op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])
        else:
            # PostgreSQL, MySQL - standard ALTER TABLE (same for both)
            op.drop_constraint('fk_sessions_project_id', 'sessions', type_='foreignkey')
            op.drop_index('ix_sessions_project_id', 'sessions')
            op.drop_column('sessions', 'project_id')

    # Drop projects table if it exists
    existing_tables = inspector.get_table_names()
    if 'projects' in existing_tables:
        op.drop_table('projects')
