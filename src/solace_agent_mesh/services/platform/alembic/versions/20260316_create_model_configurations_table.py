"""Create model_configurations table.

Revision ID: 20260316_model_configs
Revises: 20260305_outbox_events
Create Date: 2026-03-16

"""
import logging
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from solace_agent_mesh.shared.database import OptimizedUUID, SimpleJSON

log = logging.getLogger(__name__)

revision: str = '20260316_model_configs'
down_revision: Union[str, None] = '20260305_outbox_events'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade: create table."""
    # Create table
    op.create_table(
        'model_configurations',
        sa.Column('id', OptimizedUUID, nullable=False),
        sa.Column('alias', sa.String(100), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('model_name', sa.String(255), nullable=False),
        sa.Column('api_base', sa.String(2048), nullable=True),
        sa.Column('model_auth_type', sa.String(50), nullable=False, server_default='none'),
        sa.Column('model_auth_config', SimpleJSON(), nullable=False),
        sa.Column('model_params', SimpleJSON(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.Column('updated_by', sa.String(255), nullable=False),
        sa.Column('created_time', sa.BigInteger(), nullable=False),
        sa.Column('updated_time', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('LENGTH(alias) >= 1 AND LENGTH(alias) <= 100', name='check_alias_length'),
        sa.CheckConstraint('LENGTH(provider) >= 1 AND LENGTH(provider) <= 50', name='check_provider_length'),
        sa.CheckConstraint('LENGTH(model_name) >= 1 AND LENGTH(model_name) <= 255', name='check_model_name_length'),
        sa.CheckConstraint('LENGTH(created_by) <= 255', name='check_model_config_created_by_length'),
        sa.CheckConstraint('LENGTH(updated_by) <= 255', name='check_model_config_updated_by_length'),
    )

    # Create indexes
    op.create_index('ix_model_configurations_alias', 'model_configurations', ['alias'], unique=True)
    op.create_index('ix_model_configurations_provider', 'model_configurations', ['provider'])
    op.create_index('ix_model_configurations_auth_type', 'model_configurations', ['model_auth_type'])


def downgrade() -> None:
    """Downgrade: drop table and indexes."""
    op.drop_index('ix_model_configurations_auth_type', table_name='model_configurations')
    op.drop_index('ix_model_configurations_provider', table_name='model_configurations')
    op.drop_index('ix_model_configurations_alias', table_name='model_configurations')
    op.drop_table('model_configurations')
