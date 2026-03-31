"""
Model configuration database model.

Stores LLM model aliases and their settings (provider, api_base, model_auth_config, etc.)
"""

from sqlalchemy import Column, String, Text, BigInteger, CheckConstraint

from solace_agent_mesh.shared.database import SimpleJSON, OptimizedUUID
from solace_agent_mesh.shared.database.id_generators import generate_uuidv7
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from solace_agent_mesh.services.platform.constants import MODEL_CONFIGURATION_CONSTRAINTS

from solace_agent_mesh.shared.database.base import Base


class ModelConfiguration(Base):
    """Model configuration table storing LLM model aliases and settings."""

    __tablename__ = "model_configurations"
    __table_args__ = (
        CheckConstraint(
            f'LENGTH(alias) >= {MODEL_CONFIGURATION_CONSTRAINTS["ALIAS_MIN_LENGTH"]} AND LENGTH(alias) <= {MODEL_CONFIGURATION_CONSTRAINTS["ALIAS_MAX_LENGTH"]}',
            name='check_alias_length'
        ),
        CheckConstraint(
            f'LENGTH(provider) >= 1 AND LENGTH(provider) <= {MODEL_CONFIGURATION_CONSTRAINTS["PROVIDER_MAX_LENGTH"]}',
            name='check_provider_length'
        ),
        CheckConstraint(
            f'LENGTH(model_name) >= 1 AND LENGTH(model_name) <= {MODEL_CONFIGURATION_CONSTRAINTS["MODEL_NAME_MAX_LENGTH"]}',
            name='check_model_name_length'
        ),
        CheckConstraint(
            f'LENGTH(created_by) <= {MODEL_CONFIGURATION_CONSTRAINTS["CREATED_BY_MAX_LENGTH"]}',
            name='check_model_config_created_by_length'
        ),
        CheckConstraint(
            f'LENGTH(updated_by) <= {MODEL_CONFIGURATION_CONSTRAINTS["UPDATED_BY_MAX_LENGTH"]}',
            name='check_model_config_updated_by_length'
        ),
    )

    id = Column(OptimizedUUID, primary_key=True, default=generate_uuidv7)
    alias = Column(String(MODEL_CONFIGURATION_CONSTRAINTS["ALIAS_MAX_LENGTH"]), nullable=False, unique=True)
    provider = Column(String(MODEL_CONFIGURATION_CONSTRAINTS["PROVIDER_MAX_LENGTH"]), nullable=False)
    model_name = Column(String(MODEL_CONFIGURATION_CONSTRAINTS["MODEL_NAME_MAX_LENGTH"]), nullable=False)
    api_base = Column(String(MODEL_CONFIGURATION_CONSTRAINTS["API_BASE_MAX_LENGTH"]), nullable=True)
    model_auth_type = Column(String(MODEL_CONFIGURATION_CONSTRAINTS["MODEL_AUTH_TYPE_MAX_LENGTH"]), nullable=False, default="none")
    model_auth_config = Column(SimpleJSON, nullable=False, default=dict)
    model_params = Column(SimpleJSON, nullable=False, default=dict)
    description = Column(Text, nullable=True)
    created_by = Column(String(MODEL_CONFIGURATION_CONSTRAINTS["CREATED_BY_MAX_LENGTH"]), nullable=False)
    updated_by = Column(String(MODEL_CONFIGURATION_CONSTRAINTS["UPDATED_BY_MAX_LENGTH"]), nullable=False)
    created_time = Column(BigInteger, nullable=False, default=now_epoch_ms)
    updated_time = Column(
        BigInteger, nullable=False, default=now_epoch_ms, onupdate=now_epoch_ms
    )
