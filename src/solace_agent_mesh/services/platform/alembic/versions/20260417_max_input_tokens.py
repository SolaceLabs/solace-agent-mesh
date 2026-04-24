"""Add max_input_tokens to model_configurations.

Revision ID: 20260417_max_input_tokens
Revises: 20260316_model_configs
Create Date: 2026-04-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260417_max_input_tokens'
down_revision: Union[str, None] = '20260316_model_configs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'model_configurations',
        sa.Column('max_input_tokens', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('model_configurations', 'max_input_tokens')
