"""Add user_profiles table for user profile data including avatars

Revision ID: 20251122_add_user_profiles
Revises: 20251121_add_session_compression
Create Date: 2025-11-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251122_add_user_profiles'
down_revision: Union[str, None] = '20251121_add_session_compression'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create user_profiles table for storing user profile information."""
    op.create_table(
        'user_profiles',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('avatar_url', sa.String(), nullable=True),
        sa.Column('avatar_storage_type', sa.String(), nullable=True),  # 'local' or 's3'
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('user_id')
    )
    
    # Create indexes for faster lookups
    op.create_index('ix_user_profiles_user_id', 'user_profiles', ['user_id'], unique=True)
    op.create_index('ix_user_profiles_email', 'user_profiles', ['email'], unique=False)


def downgrade() -> None:
    """Drop user_profiles table."""
    op.drop_index('ix_user_profiles_email', table_name='user_profiles')
    op.drop_index('ix_user_profiles_user_id', table_name='user_profiles')
    op.drop_table('user_profiles')