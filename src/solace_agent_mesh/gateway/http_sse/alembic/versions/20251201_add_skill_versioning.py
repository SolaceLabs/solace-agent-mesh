"""Add skill versioning tables (skill_groups, skill_versions)

Revision ID: skill_versioning_001
Revises: skill_learning_001
Create Date: 2025-12-01

This migration adds versioning support for skills, following the prompt versioning pattern:
- skill_groups: Container for skill versions (like prompt_groups)
- skill_versions: Individual versions of skills (like prompts)

The migration also migrates existing skills to the new structure.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import uuid


# revision identifiers, used by Alembic.
revision = 'skill_versioning_001'
down_revision = 'skill_learning_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create skill versioning tables and migrate existing data."""
    
    # 1. Create skill_groups table (container for versions)
    op.create_table(
        'skill_groups',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        
        # Classification
        sa.Column('type', sa.String(20), nullable=False),  # learned, authored
        sa.Column('scope', sa.String(20), nullable=False),  # agent, user, shared, global
        
        # Ownership
        sa.Column('owner_agent_name', sa.String(255), nullable=True),
        sa.Column('owner_user_id', sa.String(255), nullable=True),
        
        # Production version reference (will be set after skill_versions is created)
        sa.Column('production_version_id', sa.String(36), nullable=True),
        
        # Status
        sa.Column('is_archived', sa.Boolean, default=False, nullable=False),
        
        # Timestamps (epoch ms)
        sa.Column('created_at', sa.BigInteger, nullable=False),
        sa.Column('updated_at', sa.BigInteger, nullable=False),
    )
    
    # Indexes for skill_groups
    op.create_index('ix_skill_groups_name', 'skill_groups', ['name'])
    op.create_index('ix_skill_groups_owner_agent', 'skill_groups', ['owner_agent_name'])
    op.create_index('ix_skill_groups_owner_user', 'skill_groups', ['owner_user_id'])
    op.create_index('ix_skill_groups_scope', 'skill_groups', ['scope'])
    op.create_index('ix_skill_groups_type', 'skill_groups', ['type'])
    op.create_index('ix_skill_groups_is_archived', 'skill_groups', ['is_archived'])
    
    # Unique constraint: name must be unique per agent
    op.create_index(
        'ix_skill_groups_agent_name_unique',
        'skill_groups',
        ['owner_agent_name', 'name'],
        unique=True
    )
    
    # 2. Create skill_versions table (individual versions)
    op.create_table(
        'skill_versions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('group_id', sa.String(36), sa.ForeignKey('skill_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.Integer, nullable=False),
        
        # Content
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('markdown_content', sa.Text, nullable=True),
        sa.Column('agent_chain', sa.JSON, nullable=True),
        sa.Column('tool_steps', sa.JSON, nullable=True),
        sa.Column('summary', sa.Text, nullable=True),
        
        # Source tracking
        sa.Column('source_task_id', sa.String(36), nullable=True),
        sa.Column('related_task_ids', sa.JSON, nullable=True),
        sa.Column('involved_agents', sa.JSON, nullable=True),
        
        # Embedding for vector search
        sa.Column('embedding', sa.JSON, nullable=True),
        
        # Quality metrics
        sa.Column('complexity_score', sa.Integer, default=0),
        
        # Version metadata
        sa.Column('created_by_user_id', sa.String(255), nullable=True),
        sa.Column('creation_reason', sa.Text, nullable=True),
        
        # Timestamps (epoch ms)
        sa.Column('created_at', sa.BigInteger, nullable=False),
    )
    
    # Indexes for skill_versions
    op.create_index('ix_skill_versions_group_id', 'skill_versions', ['group_id'])
    op.create_index('ix_skill_versions_version', 'skill_versions', ['group_id', 'version'])
    op.create_index('ix_skill_versions_source_task', 'skill_versions', ['source_task_id'])
    op.create_index('ix_skill_versions_created_at', 'skill_versions', ['created_at'])
    
    # 3. Add foreign key from skill_groups to skill_versions for production_version_id
    # Note: We can't add this as a proper FK due to circular dependency, 
    # but we'll handle it in the application layer
    
    # 4. Create skill_group_users table for sharing (like prompt_group_users)
    op.create_table(
        'skill_group_users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('skill_group_id', sa.String(36), sa.ForeignKey('skill_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='viewer'),  # owner, editor, viewer
        sa.Column('added_at', sa.BigInteger, nullable=False),
        sa.Column('added_by_user_id', sa.String(255), nullable=False),
    )
    
    # Indexes for skill_group_users
    op.create_index('ix_skill_group_users_group_id', 'skill_group_users', ['skill_group_id'])
    op.create_index('ix_skill_group_users_user_id', 'skill_group_users', ['user_id'])
    op.create_index(
        'ix_skill_group_users_user_group',
        'skill_group_users',
        ['user_id', 'skill_group_id'],
        unique=True
    )
    
    # 5. Migrate existing skills to the new structure
    # This is done in a data migration step
    connection = op.get_bind()
    
    # Check if there are existing skills to migrate
    result = connection.execute(text("SELECT COUNT(*) FROM skills"))
    skill_count = result.scalar()
    
    if skill_count > 0:
        # Get all existing skills
        skills = connection.execute(text("""
            SELECT id, name, description, type, scope, owner_agent_name, owner_user_id,
                   markdown_content, agent_chain, tool_steps, source_task_id, related_task_ids,
                   involved_agents, summary, created_at, updated_at, success_count, failure_count,
                   user_corrections, last_feedback_at, complexity_score, embedding
            FROM skills
        """)).fetchall()
        
        for skill in skills:
            # Generate new group ID
            group_id = str(uuid.uuid4())
            
            # Create skill_group
            connection.execute(text("""
                INSERT INTO skill_groups (
                    id, name, description, type, scope, owner_agent_name, owner_user_id,
                    production_version_id, is_archived, created_at, updated_at
                ) VALUES (
                    :group_id, :name, :description, :type, :scope, :owner_agent_name, :owner_user_id,
                    :version_id, 0, :created_at, :updated_at
                )
            """), {
                'group_id': group_id,
                'name': skill[1],  # name
                'description': skill[2][:500] if skill[2] else None,  # description (truncated for group)
                'type': skill[3],  # type
                'scope': skill[4],  # scope
                'owner_agent_name': skill[5],  # owner_agent_name
                'owner_user_id': skill[6],  # owner_user_id
                'version_id': skill[0],  # Use original skill ID as version ID
                'created_at': skill[14],  # created_at
                'updated_at': skill[15],  # updated_at
            })
            
            # Create skill_version (using original skill ID to preserve references)
            connection.execute(text("""
                INSERT INTO skill_versions (
                    id, group_id, version, description, markdown_content, agent_chain, tool_steps,
                    source_task_id, related_task_ids, involved_agents, summary, embedding,
                    complexity_score, creation_reason, created_at
                ) VALUES (
                    :id, :group_id, 1, :description, :markdown_content, :agent_chain, :tool_steps,
                    :source_task_id, :related_task_ids, :involved_agents, :summary, :embedding,
                    :complexity_score, 'Initial version (migrated from legacy)', :created_at
                )
            """), {
                'id': skill[0],  # Keep original ID
                'group_id': group_id,
                'description': skill[2],  # description
                'markdown_content': skill[7],  # markdown_content
                'agent_chain': skill[8],  # agent_chain
                'tool_steps': skill[9],  # tool_steps
                'source_task_id': skill[10],  # source_task_id
                'related_task_ids': skill[11],  # related_task_ids
                'involved_agents': skill[12],  # involved_agents
                'summary': skill[13],  # summary
                'embedding': skill[21],  # embedding
                'complexity_score': skill[20] or 0,  # complexity_score
                'created_at': skill[14],  # created_at
            })
    
    # 6. Update skill_feedback to reference skill_versions instead of skills
    # Add group_id column to skill_feedback for easier querying
    op.add_column('skill_feedback', sa.Column('group_id', sa.String(36), nullable=True))
    
    # Populate group_id from the migration
    if skill_count > 0:
        connection.execute(text("""
            UPDATE skill_feedback
            SET group_id = (
                SELECT sv.group_id FROM skill_versions sv WHERE sv.id = skill_feedback.skill_id
            )
        """))
    
    # 7. Update skill_usages to reference skill_versions
    op.add_column('skill_usages', sa.Column('group_id', sa.String(36), nullable=True))
    
    if skill_count > 0:
        connection.execute(text("""
            UPDATE skill_usages
            SET group_id = (
                SELECT sv.group_id FROM skill_versions sv WHERE sv.id = skill_usages.skill_id
            )
        """))
    
    # 8. Update skill_shares to reference skill_groups instead of skills
    # Rename skill_id to group_id
    op.add_column('skill_shares', sa.Column('group_id', sa.String(36), nullable=True))
    
    if skill_count > 0:
        connection.execute(text("""
            UPDATE skill_shares
            SET group_id = (
                SELECT sv.group_id FROM skill_versions sv WHERE sv.id = skill_shares.skill_id
            )
        """))


def downgrade() -> None:
    """Remove skill versioning tables."""
    
    # Remove added columns
    op.drop_column('skill_shares', 'group_id')
    op.drop_column('skill_usages', 'group_id')
    op.drop_column('skill_feedback', 'group_id')
    
    # Drop tables in reverse order
    op.drop_table('skill_group_users')
    op.drop_table('skill_versions')
    op.drop_table('skill_groups')