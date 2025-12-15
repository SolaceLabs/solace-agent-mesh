"""Add app visibility and app_users table

Revision ID: 20251215_add_app_visibility
Revises: 20251214_add_env_versions
Create Date: 2025-12-15

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '20251215_add_app_visibility'
down_revision: Union[str, Sequence[str], None] = '20251214_add_env_versions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add is_public column to apps table and create app_users table.

    This enables:
    - Public/private visibility for apps
    - Multi-user access to apps with roles (owner, editor, viewer)
    """
    bind = op.get_bind()
    inspector = inspect(bind)

    # Check if apps table exists
    existing_tables = inspector.get_table_names()

    if 'apps' in existing_tables:
        # Get existing columns
        existing_columns = [col['name'] for col in inspector.get_columns('apps')]

        # Add is_public column if it doesn't exist
        if 'is_public' not in existing_columns:
            op.add_column('apps', sa.Column('is_public', sa.Boolean(), nullable=False, server_default='0'))

    # Create app_users table if it doesn't exist
    if 'app_users' not in existing_tables:
        op.create_table(
            'app_users',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('app_id', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('role', sa.String(), nullable=False),
            sa.Column('added_at', sa.BigInteger(), nullable=False),
            sa.Column('added_by_user_id', sa.String(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['app_id'], ['apps.id'], ondelete='CASCADE'),
            sa.UniqueConstraint('app_id', 'user_id', name='uq_app_user')
        )

        # Create indexes for efficient queries
        op.create_index(
            'ix_app_users_app_id',
            'app_users',
            ['app_id']
        )

        op.create_index(
            'ix_app_users_user_id',
            'app_users',
            ['user_id']
        )

        # Create composite index for common query pattern (user accessing specific app)
        op.create_index(
            'ix_app_users_user_app',
            'app_users',
            ['user_id', 'app_id']
        )


def downgrade() -> None:
    """
    Remove app_users table and is_public column from apps.
    """
    bind = op.get_bind()
    inspector = inspect(bind)
    dialect_name = bind.dialect.name

    # Check if tables exist
    existing_tables = inspector.get_table_names()

    # Drop app_users table if it exists
    if 'app_users' in existing_tables:
        # Drop indexes first
        op.drop_index('ix_app_users_user_app', table_name='app_users')
        op.drop_index('ix_app_users_user_id', table_name='app_users')
        op.drop_index('ix_app_users_app_id', table_name='app_users')

        # Drop the table
        op.drop_table('app_users')

    # Drop is_public column from apps if it exists
    if 'apps' in existing_tables:
        existing_columns = [col['name'] for col in inspector.get_columns('apps')]

        if 'is_public' in existing_columns:
            # SQLite doesn't support DROP COLUMN
            if dialect_name != 'sqlite':
                op.drop_column('apps', 'is_public')
