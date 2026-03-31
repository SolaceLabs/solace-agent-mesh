"""Add project_user_pins table for per-user project pin preferences

Revision ID: 20260320_project_user_pins
Revises: 20260318_project_is_pinned
Create Date: 2026-03-20 00:00:00.000000

Steps performed by upgrade():
  1. Create project_user_pins(id, project_id, user_id, pinned_at) with a
     UNIQUE(project_id, user_id) constraint.
  2. Migrate existing owner pins: copy rows where projects.is_pinned = true
     into project_user_pins for the project owner.
  3. Drop the now-redundant projects.is_pinned column (and its index) to
     eliminate the dual-source-of-truth.

downgrade() reverses step 3 only (re-adds the column, best-effort restore of
data from project_user_pins) and then drops the new table.
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
    """
    1. Create project_user_pins table.
    2. Migrate owner pins from projects.is_pinned.
    3. Drop the legacy projects.is_pinned column.
    """
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    # ── Step 1: create the new table ────────────────────────────────────────
    if 'project_user_pins' not in existing_tables:
        op.create_table(
            'project_user_pins',
            sa.Column('id', sa.String(36), nullable=False),
            sa.Column('project_id', sa.String(36), nullable=False),
            sa.Column('user_id', sa.String(255), nullable=False),
            sa.Column('pinned_at', sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('project_id', 'user_id', name='uq_project_user_pin'),
        )
        op.create_index('ix_project_user_pins_user_id', 'project_user_pins', ['user_id'], unique=False)
        op.create_index('ix_project_user_pins_project_id', 'project_user_pins', ['project_id'], unique=False)

    # ── Step 2: migrate existing owner pins ─────────────────────────────────
    if 'projects' in existing_tables:
        projects_columns = [col['name'] for col in inspector.get_columns('projects')]
        if 'is_pinned' in projects_columns:
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
                # Idempotent insert
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

            # ── Step 3: drop the legacy column ──────────────────────────────
            # SQLite does not support DROP COLUMN before version 3.35.0.
            # We handle both dialects gracefully.
            dialect_name = bind.dialect.name
            if dialect_name == 'sqlite':
                # SQLite: recreate the table without the column.
                # Alembic's batch mode handles this transparently.
                with op.batch_alter_table('projects') as batch_op:
                    batch_op.drop_index('ix_projects_is_pinned')
                    batch_op.drop_column('is_pinned')
            else:
                op.drop_index('ix_projects_is_pinned', table_name='projects')
                op.drop_column('projects', 'is_pinned')


def downgrade() -> None:
    """
    Re-add projects.is_pinned and restore data from project_user_pins,
    then drop the project_user_pins table.
    """
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    # Re-add the column (default false so existing rows are safe)
    if 'projects' in existing_tables:
        projects_columns = [col['name'] for col in inspector.get_columns('projects')]
        if 'is_pinned' not in projects_columns:
            dialect_name = bind.dialect.name
            if dialect_name == 'sqlite':
                with op.batch_alter_table('projects') as batch_op:
                    batch_op.add_column(
                        sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default=sa.text('false'))
                    )
                    batch_op.create_index('ix_projects_is_pinned', ['is_pinned'])
            else:
                op.add_column(
                    'projects',
                    sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default=sa.text('false'))
                )
                op.create_index('ix_projects_is_pinned', 'projects', ['is_pinned'], unique=False)

        # Best-effort restore: mark projects as pinned for their owner if a pin row exists
        if 'project_user_pins' in existing_tables:
            bind.execute(
                text(
                    "UPDATE projects SET is_pinned = :val "
                    "WHERE id IN ("
                    "  SELECT project_id FROM project_user_pins WHERE user_id = projects.user_id"
                    ")"
                ),
                {"val": True}
            )

    # Drop the new table
    if 'project_user_pins' in existing_tables:
        op.drop_index('ix_project_user_pins_project_id', table_name='project_user_pins')
        op.drop_index('ix_project_user_pins_user_id', table_name='project_user_pins')
        op.drop_table('project_user_pins')
