"""Add database indexes for performance optimization

Revision ID: b1c2d3e4f5g6
Revises: d5b3f8f2e9a0
Create Date: 2025-01-11 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5g6"
down_revision: Union[str, None] = "d5b3f8f2e9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add indexes for common query patterns
    
    # Index on sessions.user_id for efficient user session filtering
    op.create_index(
        "ix_sessions_user_id", 
        "sessions", 
        ["user_id"]
    )
    
    # Index on sessions.updated_at for efficient ordering
    op.create_index(
        "ix_sessions_updated_at", 
        "sessions", 
        ["updated_at"]
    )
    
    # Composite index on sessions for user filtering with ordering
    op.create_index(
        "ix_sessions_user_id_updated_at", 
        "sessions", 
        ["user_id", "updated_at"]
    )
    
    # Index on chat_messages.session_id for efficient message retrieval
    op.create_index(
        "ix_chat_messages_session_id", 
        "chat_messages", 
        ["session_id"]
    )
    
    # Index on chat_messages.created_at for message ordering
    op.create_index(
        "ix_chat_messages_created_at", 
        "chat_messages", 
        ["created_at"]
    )
    
    # Composite index on chat_messages for session filtering with ordering
    op.create_index(
        "ix_chat_messages_session_id_created_at", 
        "chat_messages", 
        ["session_id", "created_at"]
    )
    
    # Index on sessions.agent_id for agent-specific queries
    op.create_index(
        "ix_sessions_agent_id", 
        "sessions", 
        ["agent_id"]
    )


def downgrade() -> None:
    # Remove indexes in reverse order
    op.drop_index("ix_sessions_agent_id", table_name="sessions")
    op.drop_index("ix_chat_messages_session_id_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_index("ix_sessions_user_id_updated_at", table_name="sessions")
    op.drop_index("ix_sessions_updated_at", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")