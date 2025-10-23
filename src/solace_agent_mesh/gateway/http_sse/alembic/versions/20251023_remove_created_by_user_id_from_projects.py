"""Remove created_by_user_id from projects table

Revision ID: 20251023_remove_created_by_user_id
Revises: 20251023_remove_is_global_column
Create Date: 2025-10-23

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251023_remove_created_by_user_id'
down_revision: Union[str, None] = 'remove_is_global_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove created_by_user_id column from projects table.
    
    This column was originally intended to track the creator of project templates,
    but since we're removing the notion of project templates, it's redundant with
    user_id (which represents the project owner).
    """
    # Drop the created_by_user_id column from projects table
    op.drop_column('projects', 'created_by_user_id')


def downgrade() -> None:
    """
    Re-add created_by_user_id column to projects table.
    
    Note: This will populate the column with the same value as user_id
    for all existing projects.
    """
    # Add the created_by_user_id column back
    op.add_column('projects', 
        sa.Column('created_by_user_id', sa.String(), nullable=True)
    )
    
    # Populate created_by_user_id with user_id for existing rows
    op.execute("""
        UPDATE projects 
        SET created_by_user_id = user_id 
        WHERE created_by_user_id IS NULL
    """)
    
    # Make the column non-nullable after populating it
    op.alter_column('projects', 'created_by_user_id', nullable=False)