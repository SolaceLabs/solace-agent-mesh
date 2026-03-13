"""
Model configuration database model.

Stores LLM model aliases and their settings (provider, api_base, model_auth_config, etc.)
"""

import uuid
from sqlalchemy import Column, String, Text, BigInteger, CheckConstraint

from solace_agent_mesh.shared.database import SimpleJSON, OptimizedUUID
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms

from .base import Base


class ModelConfiguration(Base):
    """Model configuration table storing LLM model aliases and settings."""

    __tablename__ = "model_configurations"
    __table_args__ = (
        CheckConstraint(
            'LENGTH(alias) >= 1 AND LENGTH(alias) <= 100',
            name='check_alias_length'
        ),
        CheckConstraint(
            'LENGTH(provider) >= 1 AND LENGTH(provider) <= 50',
            name='check_provider_length'
        ),
        CheckConstraint(
            'LENGTH(model_name) >= 1 AND LENGTH(model_name) <= 255',
            name='check_model_name_length'
        ),
        CheckConstraint(
            'LENGTH(created_by) <= 255',
            name='check_model_config_created_by_length'
        ),
        CheckConstraint(
            'LENGTH(updated_by) <= 255',
            name='check_model_config_updated_by_length'
        ),
    )

    id = Column(OptimizedUUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    alias = Column(String(100), nullable=False)  # Case-insensitive uniqueness via ix_model_configurations_alias_lower
    provider = Column(String(50), nullable=False)
    model_name = Column(String(255), nullable=False)
    api_base = Column(String(500), nullable=True)
    model_auth_type = Column(String(20), nullable=False, default="none")  # api_key, oauth2, or none
    model_auth_config = Column(SimpleJSON, nullable=False, default=dict)
    model_params = Column(SimpleJSON, nullable=False, default=dict)
    description = Column(Text, nullable=True)
    created_by = Column(String(255), nullable=False)
    updated_by = Column(String(255), nullable=False)
    created_time = Column(BigInteger, nullable=False, default=now_epoch_ms)
    updated_time = Column(
        BigInteger, nullable=False, default=now_epoch_ms, onupdate=now_epoch_ms
    )
