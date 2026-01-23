"""Add share links tables for chat sharing feature

Revision ID: 20260123_add_share_links
Revises: 20251126_background_tasks
Create Date: 2026-01-23

This migration adds tables for the chat sharing feature:
- shared_links: Stores share link metadata and access control settings
- shared_artifacts: Tracks artifacts associated with shared sessions
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20260123_add_share_links"
down_revision: str | Sequence[str] | None = "20251126_background_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create shared_links and shared_artifacts tables."""
    
    # Get connection to check if tables exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Create shared_links table if it doesn't exist
    if 'shared_links' not in existing_tables:
        op.create_table(
            'shared_links',
            sa.Column('share_id', sa.String(21), primary_key=True),
            sa.Column('session_id', sa.String(255), nullable=False),
            sa.Column('user_id', sa.String(255), nullable=False),
            sa.Column('title', sa.String(500), nullable=True),
            sa.Column('is_public', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('require_authentication', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('allowed_domains', sa.Text(), nullable=True),
            sa.Column('created_time', sa.BigInteger(), nullable=False),
            sa.Column('updated_time', sa.BigInteger(), nullable=False),
            sa.Column('deleted_at', sa.BigInteger(), nullable=True),
        )
        
        # Create indexes for shared_links
        op.create_index('idx_shared_links_user_id', 'shared_links', ['user_id'])
        op.create_index('idx_shared_links_session_id', 'shared_links', ['session_id'])
        op.create_index('idx_shared_links_created_time', 'shared_links', ['created_time'])
        op.create_index('idx_shared_links_require_auth', 'shared_links', ['require_authentication'])
        
        # Note: SQLite doesn't support adding foreign keys after table creation
        # The foreign key constraint is defined but won't be enforced in SQLite
        # For PostgreSQL, this would work:
        # op.create_foreign_key(
        #     'fk_shared_links_session_id',
        #     'shared_links', 'sessions',
        #     ['session_id'], ['id'],
        #     ondelete='CASCADE'
        # )
    
    # Create shared_artifacts table if it doesn't exist
    if 'shared_artifacts' not in existing_tables:
        op.create_table(
            'shared_artifacts',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('share_id', sa.String(21), nullable=False),
            sa.Column('artifact_uri', sa.String(1000), nullable=False),
            sa.Column('artifact_version', sa.BigInteger(), nullable=True),
            sa.Column('is_public', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('created_time', sa.BigInteger(), nullable=False),
        )
        
        # Create indexes for shared_artifacts
        op.create_index('idx_shared_artifacts_share_id', 'shared_artifacts', ['share_id'])
        
        # Note: SQLite doesn't support adding foreign keys after table creation
        # For PostgreSQL, this would work:
        # op.create_foreign_key(
        #     'fk_shared_artifacts_share_id',
        #     'shared_artifacts', 'shared_links',
        #     ['share_id'], ['share_id'],
        #     ondelete='CASCADE'
        # )


def downgrade() -> None:
    """Drop shared_links and shared_artifacts tables."""
    
    # Drop foreign key constraints first
    op.drop_constraint('fk_shared_artifacts_share_id', 'shared_artifacts', type_='foreignkey')
    op.drop_constraint('fk_shared_links_session_id', 'shared_links', type_='foreignkey')
    
    # Drop indexes
    op.drop_index('idx_shared_artifacts_share_id', 'shared_artifacts')
    op.drop_index('idx_shared_links_require_auth', 'shared_links')
    op.drop_index('idx_shared_links_created_time', 'shared_links')
    op.drop_index('idx_shared_links_session_id', 'shared_links')
    op.drop_index('idx_shared_links_user_id', 'shared_links')
    
    # Drop tables
    op.drop_table('shared_artifacts')
    op.drop_table('shared_links')
