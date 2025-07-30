"""add session name to sessions table

Revision ID: 5c1a2b3d4e5f
Revises: 4e5f6g7h8i9j
Create Date: 2024-07-22 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5c1a2b3d4e5f"
down_revision: Union[str, None] = "4e5f6g7h8i9j"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "name")
