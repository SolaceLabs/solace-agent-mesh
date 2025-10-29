"""create prompt tables for prompt library feature

Revision ID: 20251029_prompt_tables
Revises: 20251015_session_idx
Create Date: 2025-10-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20251029_prompt_tables"
down_revision: str | Sequence[str] | None = "20251015_session_idx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create prompt_groups and prompts tables."""
    
    # Create prompt_groups table
    op.create_table(
        'prompt_groups',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('command', sa.String(length=50), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('author_name', sa.String(length=255), nullable=True),
        sa.Column('production_prompt_id', sa.String(), nullable=True),
        sa.Column('is_shared', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for prompt_groups
    op.create_index('ix_prompt_groups_name', 'prompt_groups', ['name'], unique=False)
    op.create_index('ix_prompt_groups_category', 'prompt_groups', ['category'], unique=False)
    op.create_index('ix_prompt_groups_command', 'prompt_groups', ['command'], unique=True)
    op.create_index('ix_prompt_groups_user_id', 'prompt_groups', ['user_id'], unique=False)
    
    # Create prompts table
    op.create_table(
        'prompts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ['group_id'], 
            ['prompt_groups.id'], 
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for prompts
    op.create_index('ix_prompts_group_id', 'prompts', ['group_id'], unique=False)
    op.create_index('ix_prompts_user_id', 'prompts', ['user_id'], unique=False)
    
    # Add foreign key for production_prompt_id (after prompts table exists)
    op.create_foreign_key(
        'fk_prompt_groups_production_prompt_id',
        'prompt_groups', 
        'prompts',
        ['production_prompt_id'], 
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Remove prompt tables."""
    
    # Drop foreign key first
    op.drop_constraint(
        'fk_prompt_groups_production_prompt_id', 
        'prompt_groups', 
        type_='foreignkey'
    )
    
    # Drop indexes
    op.drop_index('ix_prompts_user_id', table_name='prompts')
    op.drop_index('ix_prompts_group_id', table_name='prompts')
    op.drop_index('ix_prompt_groups_user_id', table_name='prompt_groups')
    op.drop_index('ix_prompt_groups_command', table_name='prompt_groups')
    op.drop_index('ix_prompt_groups_category', table_name='prompt_groups')
    op.drop_index('ix_prompt_groups_name', table_name='prompt_groups')
    
    # Drop tables
    op.drop_table('prompts')
    op.drop_table('prompt_groups')