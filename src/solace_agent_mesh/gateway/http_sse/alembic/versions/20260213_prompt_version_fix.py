"""Deprecate production_prompt_id field - latest version is always active

Revision ID: 20260213_prompt_version_fix
Revises: 20260207_sse_event_buffer
Create Date: 2026-02-13

This migration documents the deprecation of the production_prompt_id field.
The field is kept for backward compatibility but is no longer actively used.

BEHAVIOR CHANGE:
- Previously: Users could manually set which version was "active" via make-production endpoint
- Now: The latest version (highest version number) is always the active version
- To "restore" an old version, users create a new version with that content

The production_prompt_id field remains in the database schema for backward compatibility
but is now computed dynamically by the API based on the latest version.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260213_prompt_version_fix'
down_revision = '20260207_sse_event_buffer'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Document the deprecation of production_prompt_id.
    
    No schema changes are made in this migration. The field is kept for
    backward compatibility but the application logic now computes the
    active version dynamically as the latest version.
    """
    # No schema changes - this is a documentation migration
    pass


def downgrade() -> None:
    """
    Revert to previous behavior.
    
    Note: This would require re-implementing the make-production endpoint
    and updating all API responses to use the stored production_prompt_id
    instead of computing it dynamically.
    """
    # No schema changes to revert
    pass
