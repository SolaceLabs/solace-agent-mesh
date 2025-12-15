"""Add environment version columns to apps table

Revision ID: 20251214_add_env_versions
Revises: 20251208_app_id_sessions
Create Date: 2025-12-14 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '20251214_add_env_versions'
down_revision: Union[str, Sequence[str], None] = '20251208_add_app_id_to_sessions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add dev_version, staging_version, and prod_version columns to apps table."""
    bind = op.get_bind()
    inspector = inspect(bind)

    # Check if apps table exists
    existing_tables = inspector.get_table_names()
    if 'apps' not in existing_tables:
        return

    # Get existing columns
    existing_columns = [col['name'] for col in inspector.get_columns('apps')]

    # Add dev_version column if it doesn't exist
    if 'dev_version' not in existing_columns:
        op.add_column('apps', sa.Column('dev_version', sa.String(length=50), nullable=True))

    # Add staging_version column if it doesn't exist
    if 'staging_version' not in existing_columns:
        op.add_column('apps', sa.Column('staging_version', sa.String(length=50), nullable=True))

    # Add prod_version column if it doesn't exist
    if 'prod_version' not in existing_columns:
        op.add_column('apps', sa.Column('prod_version', sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Remove environment version columns from apps table."""
    bind = op.get_bind()
    inspector = inspect(bind)

    # Check if apps table exists
    existing_tables = inspector.get_table_names()
    if 'apps' not in existing_tables:
        return

    # Get existing columns
    existing_columns = [col['name'] for col in inspector.get_columns('apps')]

    # SQLite doesn't support DROP COLUMN, so we need to handle it differently
    dialect_name = bind.dialect.name

    if dialect_name == 'sqlite':
        # For SQLite, we can't drop columns easily
        # Just skip the downgrade for SQLite
        return

    # Drop columns for other databases
    if 'prod_version' in existing_columns:
        op.drop_column('apps', 'prod_version')

    if 'staging_version' in existing_columns:
        op.drop_column('apps', 'staging_version')

    if 'dev_version' in existing_columns:
        op.drop_column('apps', 'dev_version')
