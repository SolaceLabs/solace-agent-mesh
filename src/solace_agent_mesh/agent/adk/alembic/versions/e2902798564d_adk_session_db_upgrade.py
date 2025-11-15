import google.adk.sessions.database_session_service
"""ADK session DB upgrade

Revision ID: e2902798564d
Revises: 
Create Date: 2025-11-12 10:59:41.286752

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'e2902798564d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Upgrade schema."""
    if not column_exists('events', 'custom_metadata'):
        op.add_column('events', sa.Column('custom_metadata', google.adk.sessions.database_session_service.DynamicJSON(), nullable=True))

    if not column_exists('events', 'usage_metadata'):
        op.add_column('events', sa.Column('usage_metadata', google.adk.sessions.database_session_service.DynamicJSON(), nullable=True))

    if not column_exists('events', 'citation_metadata'):
        op.add_column('events', sa.Column('citation_metadata', google.adk.sessions.database_session_service.DynamicJSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    if column_exists('events', 'citation_metadata'):
        op.drop_column('events', 'citation_metadata')

    if column_exists('events', 'usage_metadata'):
        op.drop_column('events', 'usage_metadata')

    if column_exists('events', 'custom_metadata'):
        op.drop_column('events', 'custom_metadata')
