"""Add FK on shared_artifacts.share_id and unique constraint on shared_links(session_id, user_id).

Revision ID: 20260317_share_constraints
Revises: ff67f8633203
Create Date: 2026-03-17
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '20260317_share_constraints'
down_revision: Union[str, Sequence[str], None] = 'ff67f8633203'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add FK constraint: shared_artifacts.share_id -> shared_links.share_id
    op.create_foreign_key(
        'fk_shared_artifacts_share_id',
        'shared_artifacts', 'shared_links',
        ['share_id'], ['share_id'],
        ondelete='CASCADE',
    )

    # Add unique constraint to prevent duplicate active shares per session/user
    # (session_id, user_id) should be unique among non-deleted rows.
    # Since SQLite and some DBs don't support partial unique indexes well,
    # we use a filtered unique index where deleted_at IS NULL.
    op.create_index(
        'uq_shared_links_session_user_active',
        'shared_links',
        ['session_id', 'user_id'],
        unique=True,
        postgresql_where='deleted_at IS NULL',
        sqlite_where='deleted_at IS NULL',
    )


def downgrade() -> None:
    op.drop_index('uq_shared_links_session_user_active', 'shared_links')
    op.drop_constraint('fk_shared_artifacts_share_id', 'shared_artifacts', type_='foreignkey')
