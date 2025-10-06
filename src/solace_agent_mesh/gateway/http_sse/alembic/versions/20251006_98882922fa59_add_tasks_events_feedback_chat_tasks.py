"""add_tasks_events_feedback_chat_tasks

Revision ID: 98882922fa59
Revises: f6e7d8c9b0a1
Create Date: 2025-10-06 09:57:54.735496

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98882922fa59'
down_revision: Union[str, Sequence[str], None] = 'f6e7d8c9b0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass