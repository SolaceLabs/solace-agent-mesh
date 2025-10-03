"""add token usage to tasks

Revision ID: 20250930_token_usage
Revises: 079e06e9b448
Create Date: 2025-09-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250930_token_usage'
down_revision: Union[str, None] = '079e06e9b448'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add token usage columns to tasks table."""
    op.add_column('tasks', sa.Column('total_input_tokens', sa.Integer(), nullable=True))
    op.add_column('tasks', sa.Column('total_output_tokens', sa.Integer(), nullable=True))
    op.add_column('tasks', sa.Column('total_cached_input_tokens', sa.Integer(), nullable=True))
    op.add_column('tasks', sa.Column('token_usage_details', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove token usage columns from tasks table."""
    op.drop_column('tasks', 'token_usage_details')
    op.drop_column('tasks', 'total_cached_input_tokens')
    op.drop_column('tasks', 'total_output_tokens')
    op.drop_column('tasks', 'total_input_tokens')
