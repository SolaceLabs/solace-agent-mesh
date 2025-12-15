"""Add icon_emoji and icon_background columns to apps table

Revision ID: 20251215_add_app_icon
Revises: 20251215_add_app_tags
Create Date: 2025-12-15

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '20251215_add_app_icon'
down_revision: Union[str, Sequence[str], None] = '20251215_add_app_tags'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add icon_emoji and icon_background columns to apps table."""
    bind = op.get_bind()
    inspector = inspect(bind)

    # Check if apps table exists
    existing_tables = inspector.get_table_names()
    if 'apps' not in existing_tables:
        return

    # Get existing columns
    existing_columns = [col['name'] for col in inspector.get_columns('apps')]

    # Add icon_emoji column if it doesn't exist
    if 'icon_emoji' not in existing_columns:
        op.add_column('apps', sa.Column('icon_emoji', sa.String(length=10), nullable=True))

    # Add icon_background column if it doesn't exist
    if 'icon_background' not in existing_columns:
        op.add_column('apps', sa.Column('icon_background', sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Remove icon columns from apps table."""
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
    if 'icon_background' in existing_columns:
        op.drop_column('apps', 'icon_background')

    if 'icon_emoji' in existing_columns:
        op.drop_column('apps', 'icon_emoji')
