"""Add agent_id to sessions table

Revision ID: 2b2d6a5e8b3e
Revises: 3c9a54a8a4a1
Create Date: 2025-07-16 15:25:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2b2d6a5e8b3e"
down_revision: Union[str, None] = "3c9a54a8a4a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("agent_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "agent_id")
