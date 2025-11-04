"""add default agent to projects

Revision ID: default_agent_001
Revises: soft_del_search_001
Create Date: 2025-01-24 01:13:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'default_agent_001'
down_revision = 'soft_del_search_001'
branch_labels = None
depends_on = None


def upgrade():
    """Add default_agent_id column to projects table."""
    op.add_column('projects', sa.Column('default_agent_id', sa.String(), nullable=True))


def downgrade():
    """Remove default_agent_id column from projects table."""
    op.drop_column('projects', 'default_agent_id')