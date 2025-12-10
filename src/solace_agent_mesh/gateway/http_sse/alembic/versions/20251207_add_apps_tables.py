"""Add apps and app_versions tables for SAM Apps feature

Revision ID: 20251207_add_apps_tables
Revises: 20251126_background_tasks
Create Date: 2025-12-07 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '20251207_add_apps_tables'
down_revision: Union[str, Sequence[str], None] = '20251126_background_tasks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create apps and app_versions tables for SAM Apps feature."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    # Create apps table if it doesn't exist
    if 'apps' not in existing_tables:
        op.create_table(
            'apps',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('app_id', sa.String(length=255), nullable=False),
            sa.Column('user_id', sa.String(length=255), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('workspace_id', sa.String(length=255), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
            sa.Column('current_version', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_time', sa.BigInteger(), nullable=False),
            sa.Column('updated_time', sa.BigInteger(), nullable=False),
            sa.Column('archived_time', sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'app_id', name='uq_apps_user_app')
        )

        # Create indexes for apps table
        op.create_index('ix_apps_user_id', 'apps', ['user_id'])
        op.create_index('ix_apps_app_id', 'apps', ['app_id'])
        op.create_index('ix_apps_status', 'apps', ['status'])
        op.create_index('ix_apps_user_status', 'apps', ['user_id', 'status'])

    # Create app_versions table if it doesn't exist
    if 'app_versions' not in existing_tables:
        op.create_table(
            'app_versions',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('app_id', sa.String(length=255), nullable=False),
            sa.Column('version_number', sa.Integer(), nullable=False),
            sa.Column('deployed_time', sa.BigInteger(), nullable=False),
            sa.Column('build_path', sa.String(length=500), nullable=False),
            sa.Column('git_commit', sa.String(length=100), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('app_id', 'version_number', name='uq_app_versions_app_version')
        )

        # Create indexes for app_versions table
        op.create_index('ix_app_versions_app_id', 'app_versions', ['app_id'])
        op.create_index('ix_app_versions_deployed_time', 'app_versions', ['deployed_time'])

        # Create foreign key from app_versions to apps
        # Note: Handle SQLite separately as it has limited ALTER TABLE support
        dialect_name = bind.dialect.name
        if dialect_name != 'sqlite':
            op.create_foreign_key(
                'fk_app_versions_app_id',
                'app_versions',
                'apps',
                ['app_id'],
                ['app_id'],
                ondelete='CASCADE'
            )


def downgrade() -> None:
    """Drop apps and app_versions tables."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()
    dialect_name = bind.dialect.name

    # Drop app_versions table if it exists
    if 'app_versions' in existing_tables:
        # Drop foreign key first (for non-SQLite databases)
        if dialect_name != 'sqlite':
            op.drop_constraint('fk_app_versions_app_id', 'app_versions', type_='foreignkey')

        # Drop indexes
        op.drop_index('ix_app_versions_deployed_time', 'app_versions')
        op.drop_index('ix_app_versions_app_id', 'app_versions')

        # Drop table
        op.drop_table('app_versions')

    # Drop apps table if it exists
    if 'apps' in existing_tables:
        # Drop indexes
        op.drop_index('ix_apps_user_status', 'apps')
        op.drop_index('ix_apps_status', 'apps')
        op.drop_index('ix_apps_app_id', 'apps')
        op.drop_index('ix_apps_user_id', 'apps')

        # Drop table
        op.drop_table('apps')
