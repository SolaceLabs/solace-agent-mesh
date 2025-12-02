"""Add bundled resources support to skill versions

Revision ID: skill_bundled_resources_001
Revises: skill_versioning_001
Create Date: 2025-12-02

This migration adds support for storing bundled resources (scripts, data files)
alongside skill versions. The actual files are stored in object storage (S3 or
filesystem), while the database stores:
- URI reference to the storage location
- Manifest of included files for quick listing
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'skill_bundled_resources_001'
down_revision = 'skill_versioning_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add bundled resources columns to skill_versions table."""
    
    # Add URI reference to bundled resources storage location
    # Format: "s3://bucket/skills/{group_id}/{version_id}/"
    #     or: "file:///data/skills/{group_id}/{version_id}/"
    op.add_column(
        'skill_versions',
        sa.Column('bundled_resources_uri', sa.String(500), nullable=True)
    )
    
    # Add manifest of bundled files for quick listing without storage access
    # Format: {"scripts": ["main.py", "helpers.py"], "resources": ["template.json"]}
    op.add_column(
        'skill_versions',
        sa.Column('bundled_resources_manifest', sa.JSON, nullable=True)
    )
    
    # Add index for skills that have bundled resources (for filtering)
    op.create_index(
        'ix_skill_versions_has_resources',
        'skill_versions',
        ['bundled_resources_uri'],
        postgresql_where=sa.text('bundled_resources_uri IS NOT NULL')
    )


def downgrade() -> None:
    """Remove bundled resources columns from skill_versions table."""
    
    op.drop_index('ix_skill_versions_has_resources', table_name='skill_versions')
    op.drop_column('skill_versions', 'bundled_resources_manifest')
    op.drop_column('skill_versions', 'bundled_resources_uri')