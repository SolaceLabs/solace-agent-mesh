"""Create prompt tables with role-based sharing support

Revision ID: 20251108_prompt_tables_complete
Revises: 20251103_merge_heads
Create Date: 2025-11-08

This is a squashed migration that combines:
- Initial prompt tables creation
- Prompt pinning feature
- Role-based sharing via prompt_group_users table
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20251108_prompt_tables_complete"
down_revision: str | Sequence[str] | None = "default_agent_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create complete prompt schema with sharing support."""
    
    # 1. Create prompts table (individual prompt versions)
    op.create_table(
        'prompts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for prompts
    op.create_index('ix_prompts_group_id', 'prompts', ['group_id'], unique=False)
    op.create_index('ix_prompts_user_id', 'prompts', ['user_id'], unique=False)
    
    # 2. Create prompt_groups table (prompt collections)
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
        sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ['production_prompt_id'],
            ['prompts.id'],
            ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for prompt_groups
    op.create_index('ix_prompt_groups_name', 'prompt_groups', ['name'], unique=False)
    op.create_index('ix_prompt_groups_category', 'prompt_groups', ['category'], unique=False)
    op.create_index('ix_prompt_groups_command', 'prompt_groups', ['command'], unique=True)
    op.create_index('ix_prompt_groups_user_id', 'prompt_groups', ['user_id'], unique=False)
    op.create_index('ix_prompt_groups_is_pinned', 'prompt_groups', ['is_pinned'], unique=False)
    
    # 3. Add foreign key from prompts to prompt_groups
    with op.batch_alter_table('prompts', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_prompts_group_id',
            'prompt_groups',
            ['group_id'],
            ['id'],
            ondelete='CASCADE'
        )
    
    # 4. Create prompt_group_users table (role-based sharing)
    op.create_table(
        'prompt_group_users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('prompt_group_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False, server_default='viewer'),
        sa.Column('added_at', sa.BigInteger(), nullable=False),
        sa.Column('added_by_user_id', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['prompt_group_id'], 
            ['prompt_groups.id'], 
            ondelete='CASCADE'
        ),
        sa.UniqueConstraint('prompt_group_id', 'user_id', name='uq_prompt_group_user')
    )
    
    # Indexes for prompt_group_users (optimized for sharing queries)
    op.create_index(
        'ix_prompt_group_users_prompt_group_id',
        'prompt_group_users',
        ['prompt_group_id'],
        unique=False
    )
    
    op.create_index(
        'ix_prompt_group_users_user_id',
        'prompt_group_users',
        ['user_id'],
        unique=False
    )
    
    # Composite index for fast access checks
    op.create_index(
        'ix_prompt_group_users_user_prompt',
        'prompt_group_users',
        ['user_id', 'prompt_group_id'],
        unique=False
    )
    
    # Optional: Index for role-based queries
    op.create_index(
        'ix_prompt_group_users_user_role',
        'prompt_group_users',
        ['user_id', 'role'],
        unique=False
    )


def downgrade() -> None:
    """Remove all prompt-related tables."""
    
    # Drop prompt_group_users table and indexes
    op.drop_index('ix_prompt_group_users_user_role', table_name='prompt_group_users')
    op.drop_index('ix_prompt_group_users_user_prompt', table_name='prompt_group_users')
    op.drop_index('ix_prompt_group_users_user_id', table_name='prompt_group_users')
    op.drop_index('ix_prompt_group_users_prompt_group_id', table_name='prompt_group_users')
    op.drop_table('prompt_group_users')
    
    # Drop prompt_groups indexes and table
    op.drop_index('ix_prompt_groups_is_pinned', table_name='prompt_groups')
    op.drop_index('ix_prompt_groups_user_id', table_name='prompt_groups')
    op.drop_index('ix_prompt_groups_command', table_name='prompt_groups')
    op.drop_index('ix_prompt_groups_category', table_name='prompt_groups')
    op.drop_index('ix_prompt_groups_name', table_name='prompt_groups')
    op.drop_table('prompt_groups')
    
    # Drop prompts indexes and table
    op.drop_index('ix_prompts_user_id', table_name='prompts')
    op.drop_index('ix_prompts_group_id', table_name='prompts')
    op.drop_table('prompts')