"""Add app_id to sessions table

Revision ID: 20251208_add_app_id_to_sessions
Revises: 20251207_add_apps_tables
Create Date: 2025-12-08

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251208_add_app_id_to_sessions'
down_revision = '20251207_add_apps_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add app_id column to sessions table (nullable, no foreign key constraint)
    op.add_column('sessions', sa.Column('app_id', sa.String(255), nullable=True))
    op.create_index('idx_sessions_app_id', 'sessions', ['app_id'])


def downgrade() -> None:
    # Remove index and column
    op.drop_index('idx_sessions_app_id', 'sessions')
    op.drop_column('sessions', 'app_id')
