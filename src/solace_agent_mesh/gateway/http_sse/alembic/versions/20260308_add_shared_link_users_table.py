"""Add shared_link_users table for user-specific chat sharing

Revision ID: 20260308_shared_link_users
Revises: 20260123_add_share_links
Create Date: 2026-03-08 00:00:00.000000

This migration adds a table to track which users have access to specific
shared links, enabling user-specific sharing similar to project sharing.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '20260308_shared_link_users'
down_revision: Union[str, Sequence[str], None] = '20260123_add_share_links'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add shared_link_users table for user-specific sharing."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'shared_link_users' not in existing_tables:
        op.create_table(
            'shared_link_users',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('share_id', sa.String(21), nullable=False),
            sa.Column('user_email', sa.String(255), nullable=False),
            sa.Column('access_level', sa.String(50), nullable=False, server_default='RESOURCE_VIEWER'),
            sa.Column('added_at', sa.BigInteger(), nullable=False),
            sa.Column('added_by_user_id', sa.String(255), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['share_id'], ['shared_links.share_id'], ondelete='CASCADE'),
            sa.UniqueConstraint('share_id', 'user_email', name='uq_shared_link_user')
        )

        # The unique constraint on (share_id, user_email) already creates a composite index.
        # Add a single-column index on user_email for "shared with me" lookups.
        op.create_index(
            'ix_shared_link_users_user_email',
            'shared_link_users',
            ['user_email']
        )


def downgrade() -> None:
    """Remove shared_link_users table and related indexes."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'shared_link_users' in existing_tables:
        # Drop indexes first
        try:
            op.drop_index('ix_shared_link_users_user_email', table_name='shared_link_users')
        except Exception:
            pass

        # Drop the table
        op.drop_table('shared_link_users')
