"""Add share links tables for chat sharing feature

Revision ID: 20260123_add_share_links
Revises: 20260222_doc_conv_cache
Create Date: 2026-01-23

This migration adds tables for the chat sharing feature:
- shared_links: Stores share link metadata and access control settings
- shared_artifacts: Tracks artifacts associated with shared sessions
- shared_link_users: Tracks which users have access to specific shared links
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260123_add_share_links"
down_revision: str | Sequence[str] | None = "20260222_doc_conv_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create shared_links, shared_artifacts, and shared_link_users tables."""

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # --- shared_links ---
    if "shared_links" not in existing_tables:
        op.create_table(
            "shared_links",
            sa.Column("share_id", sa.String(21), primary_key=True),
            sa.Column("session_id", sa.String(255), nullable=False),
            sa.Column("user_id", sa.String(255), nullable=False),
            sa.Column("title", sa.String(500), nullable=True),
            sa.Column(
                "is_public", sa.Boolean(), nullable=False, server_default="1"
            ),
            sa.Column(
                "require_authentication",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("allowed_domains", sa.Text(), nullable=True),
            sa.Column("created_time", sa.BigInteger(), nullable=False),
            sa.Column("updated_time", sa.BigInteger(), nullable=False),
            sa.Column("deleted_at", sa.BigInteger(), nullable=True),
        )

        op.create_index(
            "idx_shared_links_user_id", "shared_links", ["user_id"]
        )
        op.create_index(
            "idx_shared_links_session_id", "shared_links", ["session_id"]
        )
        op.create_index(
            "idx_shared_links_created_time", "shared_links", ["created_time"]
        )
        op.create_index(
            "idx_shared_links_require_auth",
            "shared_links",
            ["require_authentication"],
        )
        op.create_index(
            "idx_shared_links_deleted_at", "shared_links", ["deleted_at"]
        )

        # Unique partial index: one active share per (session_id, user_id)
        op.create_index(
            "uq_shared_links_session_user_active",
            "shared_links",
            ["session_id", "user_id"],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
            sqlite_where=sa.text("deleted_at IS NULL"),
        )

    # --- shared_artifacts ---
    if "shared_artifacts" not in existing_tables:
        op.create_table(
            "shared_artifacts",
            sa.Column(
                "id", sa.BigInteger(), primary_key=True, autoincrement=True
            ),
            sa.Column("share_id", sa.String(21), nullable=False),
            sa.Column("artifact_uri", sa.String(1000), nullable=False),
            sa.Column("artifact_version", sa.BigInteger(), nullable=True),
            sa.Column(
                "is_public", sa.Boolean(), nullable=False, server_default="1"
            ),
            sa.Column("created_time", sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(
                ["share_id"],
                ["shared_links.share_id"],
                name="fk_shared_artifacts_share_id",
                ondelete="CASCADE",
            ),
        )

        op.create_index(
            "idx_shared_artifacts_share_id",
            "shared_artifacts",
            ["share_id"],
        )

    # --- shared_link_users ---
    if "shared_link_users" not in existing_tables:
        op.create_table(
            "shared_link_users",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("share_id", sa.String(21), nullable=False),
            sa.Column("user_email", sa.String(255), nullable=False),
            sa.Column(
                "access_level",
                sa.String(50),
                nullable=False,
                server_default="RESOURCE_VIEWER",
            ),
            sa.Column("added_at", sa.BigInteger(), nullable=False),
            sa.Column("added_by_user_id", sa.String(255), nullable=False),
            sa.Column(
                "original_access_level", sa.String(50), nullable=True
            ),
            sa.Column("original_added_at", sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["share_id"],
                ["shared_links.share_id"],
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "share_id", "user_email", name="uq_shared_link_user"
            ),
        )

        op.create_index(
            "ix_shared_link_users_user_email",
            "shared_link_users",
            ["user_email"],
        )


def downgrade() -> None:
    """Drop shared_link_users, shared_artifacts, and shared_links tables."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # Drop in reverse dependency order
    if "shared_link_users" in existing_tables:
        try:
            op.drop_index(
                "ix_shared_link_users_user_email",
                table_name="shared_link_users",
            )
        except Exception:
            pass
        op.drop_table("shared_link_users")

    if "shared_artifacts" in existing_tables:
        op.drop_index(
            "idx_shared_artifacts_share_id", "shared_artifacts"
        )
        op.drop_table("shared_artifacts")

    if "shared_links" in existing_tables:
        try:
            op.drop_index(
                "uq_shared_links_session_user_active", "shared_links"
            )
        except Exception:
            pass
        op.drop_index("idx_shared_links_deleted_at", "shared_links")
        op.drop_index("idx_shared_links_require_auth", "shared_links")
        op.drop_index("idx_shared_links_created_time", "shared_links")
        op.drop_index("idx_shared_links_session_id", "shared_links")
        op.drop_index("idx_shared_links_user_id", "shared_links")
        op.drop_table("shared_links")
