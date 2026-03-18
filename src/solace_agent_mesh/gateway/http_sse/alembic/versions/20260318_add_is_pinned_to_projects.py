"""Add is_pinned column to projects table

Revision ID: 20260318_add_is_pinned_to_projects
Revises: 20260222_doc_conv_cache
Create Date: 2026-03-18 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '20260318_add_is_pinned_to_projects'
down_revision: Union[str, Sequence[str], None] = '20260123_add_share_links'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_pinned column to projects table."""
    bind = op.get_bind()
    inspector = inspect(bind)

    existing_tables = inspector.get_table_names()
    if 'projects' not in existing_tables:
        return

    projects_columns = [col['name'] for col in inspector.get_columns('projects')]
    if 'is_pinned' not in projects_columns:
        op.add_column(
            'projects',
            sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default=sa.text('false'))
        )
        op.create_index('ix_projects_is_pinned', 'projects', ['is_pinned'], unique=False)


def downgrade() -> None:
    """Remove is_pinned column from projects table."""
    bind = op.get_bind()
    inspector = inspect(bind)

    existing_tables = inspector.get_table_names()
    if 'projects' not in existing_tables:
        return

    projects_columns = [col['name'] for col in inspector.get_columns('projects')]
    if 'is_pinned' in projects_columns:
        op.drop_index('ix_projects_is_pinned', table_name='projects')
        op.drop_column('projects', 'is_pinned')
