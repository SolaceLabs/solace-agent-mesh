"""Add app_tags table for tagging apps

Revision ID: 20251215_add_app_tags
Revises: 20251215_add_app_visibility
Create Date: 2025-12-15

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '20251215_add_app_tags'
down_revision: Union[str, Sequence[str], None] = '20251215_add_app_visibility'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create app_tags table for storing tags associated with apps.
    """
    bind = op.get_bind()
    inspector = inspect(bind)

    # Check if tables exist
    existing_tables = inspector.get_table_names()

    # Create app_tags table if it doesn't exist
    if 'app_tags' not in existing_tables:
        op.create_table(
            'app_tags',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('app_id', sa.String(), nullable=False),
            sa.Column('tag', sa.String(100), nullable=False),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['app_id'], ['apps.id'], ondelete='CASCADE'),
            sa.UniqueConstraint('app_id', 'tag', name='uq_app_tag')
        )

        # Create index for searching by tag
        op.create_index(
            'ix_app_tags_tag',
            'app_tags',
            ['tag']
        )

        # Create index for looking up tags by app
        op.create_index(
            'ix_app_tags_app_id',
            'app_tags',
            ['app_id']
        )


def downgrade() -> None:
    """
    Remove app_tags table.
    """
    bind = op.get_bind()
    inspector = inspect(bind)

    # Check if tables exist
    existing_tables = inspector.get_table_names()

    # Drop app_tags table if it exists
    if 'app_tags' in existing_tables:
        # Drop indexes first
        op.drop_index('ix_app_tags_app_id', table_name='app_tags')
        op.drop_index('ix_app_tags_tag', table_name='app_tags')

        # Drop the table
        op.drop_table('app_tags')
