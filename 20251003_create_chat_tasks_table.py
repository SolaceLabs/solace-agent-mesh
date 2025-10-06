"""create chat_tasks table

Revision ID: 20250103_chat_tasks
Revises: 20250930_token_usage
Create Date: 2025-01-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250103_chat_tasks'
down_revision: Union[str, None] = '20250930_token_usage'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create chat_tasks table for frontend-driven chat persistence."""
    op.create_table(
        'chat_tasks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('user_message', sa.Text(), nullable=True),
        sa.Column('message_bubbles', sa.Text(), nullable=False),
        sa.Column('task_metadata', sa.Text(), nullable=True),
        sa.Column('created_time', sa.BigInteger(), nullable=False),
        sa.Column('updated_time', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['session_id'],
            ['sessions.id'],
            ondelete='CASCADE'
        )
    )
    
    # Create indexes for common queries
    op.create_index(
        'ix_chat_tasks_session_id',
        'chat_tasks',
        ['session_id']
    )
    op.create_index(
        'ix_chat_tasks_user_id',
        'chat_tasks',
        ['user_id']
    )
    op.create_index(
        'ix_chat_tasks_created_time',
        'chat_tasks',
        ['created_time']
    )


def downgrade() -> None:
    """Drop chat_tasks table and its indexes."""
    op.drop_index('ix_chat_tasks_created_time', table_name='chat_tasks')
    op.drop_index('ix_chat_tasks_user_id', table_name='chat_tasks')
    op.drop_index('ix_chat_tasks_session_id', table_name='chat_tasks')
    op.drop_table('chat_tasks')
