"""Create skill learning tables

Revision ID: skill_learning_001
Revises: 20251115_add_parent_task_id
Create Date: 2025-11-30

This migration creates the tables for the SAM Skill Learning System:
- skills: Main skill storage
- skill_shares: Skill sharing relationships
- skill_feedback: Feedback on skills
- skill_usages: Skill usage tracking
- learning_queue: Queue for skill extraction
- skill_embeddings: Separate embedding storage
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'skill_learning_001'
down_revision = '20251115_add_parent_task_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create skills table
    op.create_table(
        'skills',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('type', sa.String(20), nullable=False, index=True),
        sa.Column('scope', sa.String(20), nullable=False, index=True),
        sa.Column('owner_agent_name', sa.String(255), nullable=True, index=True),
        sa.Column('owner_user_id', sa.String(255), nullable=True, index=True),
        sa.Column('markdown_content', sa.Text, nullable=True),
        sa.Column('agent_chain', sa.JSON, nullable=True),
        sa.Column('tool_steps', sa.JSON, nullable=True),
        sa.Column('source_task_id', sa.String(36), nullable=True, index=True),
        sa.Column('related_task_ids', sa.JSON, nullable=True),
        sa.Column('involved_agents', sa.JSON, nullable=True),
        sa.Column('summary', sa.Text, nullable=True),
        sa.Column('created_at', sa.Integer, nullable=False, index=True),
        sa.Column('updated_at', sa.Integer, nullable=False),
        sa.Column('success_count', sa.Integer, default=0),
        sa.Column('failure_count', sa.Integer, default=0),
        sa.Column('user_corrections', sa.Integer, default=0),
        sa.Column('last_feedback_at', sa.Integer, nullable=True),
        sa.Column('parent_skill_id', sa.String(36), nullable=True, index=True),
        sa.Column('refinement_reason', sa.Text, nullable=True),
        sa.Column('complexity_score', sa.Integer, default=0),
        sa.Column('embedding', sa.JSON, nullable=True),
    )
    
    # Create composite indexes for skills
    op.create_index(
        'ix_skills_scope_owner_agent',
        'skills',
        ['scope', 'owner_agent_name']
    )
    op.create_index(
        'ix_skills_scope_owner_user',
        'skills',
        ['scope', 'owner_user_id']
    )
    op.create_index(
        'ix_skills_type_scope',
        'skills',
        ['type', 'scope']
    )
    
    # Create skill_shares table
    op.create_table(
        'skill_shares',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('skill_id', sa.String(36), sa.ForeignKey('skills.id', ondelete='CASCADE'), nullable=False),
        sa.Column('shared_with_user_id', sa.String(255), nullable=False, index=True),
        sa.Column('shared_by_user_id', sa.String(255), nullable=False, index=True),
        sa.Column('shared_at', sa.Integer, nullable=False),
    )
    
    op.create_index(
        'ix_skill_shares_skill_user',
        'skill_shares',
        ['skill_id', 'shared_with_user_id']
    )
    
    # Create skill_feedback table
    op.create_table(
        'skill_feedback',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('skill_id', sa.String(36), sa.ForeignKey('skills.id', ondelete='CASCADE'), nullable=False),
        sa.Column('task_id', sa.String(36), nullable=False, index=True),
        sa.Column('user_id', sa.String(255), nullable=True, index=True),
        sa.Column('feedback_type', sa.String(50), nullable=False, index=True),
        sa.Column('correction_text', sa.Text, nullable=True),
        sa.Column('created_at', sa.Integer, nullable=False, index=True),
    )
    
    # Create skill_usages table
    op.create_table(
        'skill_usages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('skill_id', sa.String(36), sa.ForeignKey('skills.id', ondelete='CASCADE'), nullable=False),
        sa.Column('task_id', sa.String(36), nullable=False, index=True),
        sa.Column('agent_name', sa.String(255), nullable=False, index=True),
        sa.Column('user_id', sa.String(255), nullable=True, index=True),
        sa.Column('used_at', sa.Integer, nullable=False, index=True),
    )
    
    op.create_index(
        'ix_skill_usages_skill_agent',
        'skill_usages',
        ['skill_id', 'agent_name']
    )
    
    # Create learning_queue table
    op.create_table(
        'learning_queue',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(36), nullable=False, index=True),
        sa.Column('agent_name', sa.String(255), nullable=False, index=True),
        sa.Column('user_id', sa.String(255), nullable=True, index=True),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('queued_at', sa.Integer, nullable=False, index=True),
        sa.Column('started_at', sa.Integer, nullable=True),
        sa.Column('completed_at', sa.Integer, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('retry_count', sa.Integer, default=0),
    )
    
    op.create_index(
        'ix_learning_queue_status_queued',
        'learning_queue',
        ['status', 'queued_at']
    )
    
    # Create skill_embeddings table
    op.create_table(
        'skill_embeddings',
        sa.Column('skill_id', sa.String(36), sa.ForeignKey('skills.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('embedding_model', sa.String(100), nullable=False),
        sa.Column('embedding_dimension', sa.Integer, nullable=False),
        sa.Column('embedding', sa.JSON, nullable=False),
        sa.Column('created_at', sa.Integer, nullable=False),
    )
    
    op.create_index(
        'ix_skill_embeddings_model',
        'skill_embeddings',
        ['embedding_model']
    )


def downgrade() -> None:
    op.drop_table('skill_embeddings')
    op.drop_table('learning_queue')
    op.drop_table('skill_usages')
    op.drop_table('skill_feedback')
    op.drop_table('skill_shares')
    op.drop_table('skills')