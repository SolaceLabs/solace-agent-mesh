"""Add original_access_level and original_added_at to shared_link_users

Revision ID: 20260312_share_access_history
Revises: 20260308_shared_link_users
Create Date: 2026-03-12 00:00:00.000000

Tracks the original share event when a user's access level is changed,
so both the "gave access" and "changed access" notifications can be shown.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '20260312_share_access_history'
down_revision: Union[str, Sequence[str], None] = '20260308_shared_link_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add original_access_level and original_added_at columns."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'shared_link_users' in existing_tables:
        existing_columns = [col['name'] for col in inspector.get_columns('shared_link_users')]

        if 'original_access_level' not in existing_columns:
            op.add_column(
                'shared_link_users',
                sa.Column('original_access_level', sa.String(50), nullable=True)
            )

        if 'original_added_at' not in existing_columns:
            op.add_column(
                'shared_link_users',
                sa.Column('original_added_at', sa.BigInteger(), nullable=True)
            )


def downgrade() -> None:
    """Remove original_access_level and original_added_at columns."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'shared_link_users' in existing_tables:
        existing_columns = [col['name'] for col in inspector.get_columns('shared_link_users')]

        if 'original_added_at' in existing_columns:
            op.drop_column('shared_link_users', 'original_added_at')

        if 'original_access_level' in existing_columns:
            op.drop_column('shared_link_users', 'original_access_level')
