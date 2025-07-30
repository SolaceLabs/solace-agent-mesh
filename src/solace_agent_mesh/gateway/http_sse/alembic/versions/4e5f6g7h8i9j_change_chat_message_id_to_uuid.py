"""Change chat_message id to uuid

Revision ID: 4e5f6g7h8i9j
Revises: 2b2d6a5e8b3e
Create Date: 2025-07-21 23:45:44.297Z

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4e5f6g7h8i9j"
down_revision: Union[str, None] = "2b2d6a5e8b3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        batch_op.alter_column(
            "id",
            existing_type=sa.INTEGER(),
            type_=sa.String(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "parent_message_id",
            existing_type=sa.INTEGER(),
            type_=sa.String(),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        batch_op.alter_column(
            "id",
            existing_type=sa.String(),
            type_=sa.INTEGER(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "parent_message_id",
            existing_type=sa.String(),
            type_=sa.INTEGER(),
            existing_nullable=True,
        )
