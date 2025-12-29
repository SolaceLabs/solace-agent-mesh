"""Add app_storage table for persistent key-value storage

Revision ID: 20251221_add_app_storage
Revises: 20251215_add_app_icon
Create Date: 2025-12-21
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251221_add_app_storage"
down_revision = "20251215_add_app_icon"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create app_storage table for SAM SDK storage API."""
    op.create_table(
        "app_storage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column("app_id", sa.String(255), nullable=False, index=True),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("created_time", sa.BigInteger, nullable=False),
        sa.Column("updated_time", sa.BigInteger, nullable=False),
    )

    # Create composite unique index for efficient lookups
    op.create_index(
        "ix_app_storage_user_app_key",
        "app_storage",
        ["user_id", "app_id", "key"],
        unique=True,
    )


def downgrade() -> None:
    """Drop app_storage table."""
    op.drop_index("ix_app_storage_user_app_key", table_name="app_storage")
    op.drop_table("app_storage")
