"""Service layer for model configuration business logic."""

import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from solace_agent_mesh.services.platform.models import ModelConfiguration
from solace_agent_mesh.services.platform.api.routers.dto.responses import (
    ModelConfigurationResponse,
)
from solace_agent_mesh.shared.utils.secret_redactor import redact_auth_config

log = logging.getLogger(__name__)


class ModelConfigService:
    """
    Service layer for model configuration business logic.

    Handles:
    - Querying model configurations
    - Converting database entities to safe response models
    - Credential redaction based on auth type
    - Future business logic (RBAC checks, update/delete operations)
    """

    def __init__(self, db: Session):
        """
        Initialize the service with a database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def list_all(self) -> List[ModelConfigurationResponse]:
        """
        Retrieve all model configurations.

        Returns:
            List of ModelConfigurationResponse objects with credentials filtered
        """
        db_configs = self.db.query(ModelConfiguration).all()
        return [self._to_response(config) for config in db_configs]

    def get_by_alias(self, alias: str) -> Optional[ModelConfigurationResponse]:
        """
        Retrieve a model configuration by alias (case-sensitive exact match).

        Args:
            alias: Model alias to look up

        Returns:
            ModelConfigurationResponse if found, None otherwise
        """
        db_config = self.db.query(ModelConfiguration).filter(
            ModelConfiguration.alias == alias
        ).first()

        if not db_config:
            return None

        return self._to_response(db_config)

    @staticmethod
    def _to_response(db_model: ModelConfiguration) -> ModelConfigurationResponse:
        """
        Convert database model to response DTO, filtering sensitive auth data.

        Uses redact_auth_config() to strip secrets (api_key, client_secret, etc.)
        from model_auth_config based on auth type. This ensures consistency with
        the connector/agent credential redaction patterns.

        Args:
            db_model: ModelConfiguration database model instance

        Returns:
            ModelConfigurationResponse with auth_type from model_auth_type column
            and auth config secrets filtered out
        """
        # Redact secrets from auth config based on auth type
        redacted_auth_config = redact_auth_config(db_model.model_auth_config)

        return ModelConfigurationResponse(
            id=db_model.id,
            alias=db_model.alias,
            provider=db_model.provider,
            model_name=db_model.model_name,
            api_base=db_model.api_base,
            auth_type=db_model.model_auth_type,
            auth_config=redacted_auth_config or {},
            model_params=db_model.model_params or {},
            description=db_model.description,
            created_by=db_model.created_by,
            updated_by=db_model.updated_by,
            created_time=db_model.created_time,
            updated_time=db_model.updated_time,
        )
