"""Add project_user_pins table for per-user project pin preferences

Revision ID: 20260320_project_user_pins
Revises: 20260318_project_is_pinned
Create Date: 2026-03-20 00:00:00.000000

Migrates existing owner pins from projects.is_pinned into the new table.
"""
import time
import uuid
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = '20260320_project_user_pins'
down_revision: Union[str, Sequence[str], None] = '20260318_project_is_pinned'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create project_user_pins table and migrate existing owner pins."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'project_user_pins' not in existing_tables:
        op.create_table(
            'project_user_pins',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('project_id', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('pinned_at', sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('project_id', 'user_id', name='uq_project_user_pin'),
        )
        op.create_index('ix_project_user_pins_user_id', 'project_user_pins', ['user_id'], unique=False)
        op.create_index('ix_project_user_pins_project_id', 'project_user_pins', ['project_id'], unique=False)

    # Migrate existing owner pins: for every project where is_pinned=true,
    # insert a row into project_user_pins for the project owner (user_id).
    if 'projects' in existing_tables:
        projects_columns = [col['name'] for col in inspector.get_columns('projects')]
        if 'is_pinned' in projects_columns:
            # Fetch pinned projects using a bound parameter for dialect safety
            result = bind.execute(
                text("SELECT id, user_id FROM projects WHERE is_pinned = :val AND deleted_at IS NULL"),
                {"val": True}
            )
            pinned_rows = result.fetchall()

            now_ms = int(time.time() * 1000)

            for row in pinned_rows:
                project_id = row[0]
                user_id = row[1]
                pin_id = str(uuid.uuid4())
                # Insert only if not already present (idempotent)
                bind.execute(
                    text(
                        "INSERT INTO project_user_pins (id, project_id, user_id, pinned_at) "
                        "SELECT :id, :project_id, :user_id, :pinned_at "
                        "WHERE NOT EXISTS ("
                        "  SELECT 1 FROM project_user_pins "
                        "  WHERE project_id = :project_id AND user_id = :user_id"
                        ")"
                    ),
                    {"id": pin_id, "project_id": project_id, "user_id": user_id, "pinned_at": now_ms}
                )


def downgrade() -> None:
    """Drop project_user_pins table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'project_user_pins' in existing_tables:
        op.drop_index('ix_project_user_pins_project_id', table_name='project_user_pins')
        op.drop_index('ix_project_user_pins_user_id', table_name='project_user_pins')
        op.drop_table('project_user_pins')
