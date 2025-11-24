"""Create session_tags table and add tags column to sessions

Revision ID: 20251124_session_tags
Revises: 20251117_add_a2a_task_id_index
Create Date: 2025-11-24 15:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20251124_session_tags"
down_revision: Union[str, None] = "20251115_add_parent_task_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create session_tags table and add tags column to sessions table."""
    
    # Create session_tags table
    op.create_table(
        "session_tags",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("tag", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_time", sa.BigInteger(), nullable=False),
        sa.Column("updated_time", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Create indexes for session_tags table
    op.create_index(
        "ix_session_tags_user_id",
        "session_tags",
        ["user_id"]
    )
    
    op.create_index(
        "ix_session_tags_tag",
        "session_tags",
        ["tag"]
    )
    
    op.create_index(
        "ix_session_tags_user_id_tag",
        "session_tags",
        ["user_id", "tag"],
        unique=True
    )
    
    op.create_index(
        "ix_session_tags_user_id_position",
        "session_tags",
        ["user_id", "position"]
    )
    
    # Add tags column to sessions table
    op.add_column(
        "sessions",
        sa.Column("tags", sa.JSON(), nullable=True)
    )
    
    # Create index for tags column (GIN index for PostgreSQL, regular for others)
    try:
        op.create_index(
            "ix_sessions_tags",
            "sessions",
            ["tags"],
            postgresql_using="gin"
        )
    except Exception:
        # Fallback for non-PostgreSQL databases
        op.create_index(
            "ix_sessions_tags",
            "sessions",
            ["tags"]
        )


def downgrade() -> None:
    """Remove tags column from sessions and drop session_tags table."""
    
    # Drop sessions tags index
    op.drop_index("ix_sessions_tags", table_name="sessions")
    
    # Drop tags column from sessions
    op.drop_column("sessions", "tags")
    
    # Drop session_tags indexes
    op.drop_index("ix_session_tags_user_id_position", table_name="session_tags")
    op.drop_index("ix_session_tags_user_id_tag", table_name="session_tags")
    op.drop_index("ix_session_tags_tag", table_name="session_tags")
    op.drop_index("ix_session_tags_user_id", table_name="session_tags")
    
    # Drop session_tags table
    op.drop_table("session_tags")