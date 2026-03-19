"""Service layer for model configuration business logic."""

import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from typing import List, Optional
from sqlalchemy.orm import Session

from solace_agent_mesh.services.platform.repositories import ModelConfigurationRepository
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
    - Business logic and validation
    - Converting database entities to safe response models
    - Credential redaction based on auth type
    - Future business logic (RBAC checks, update/delete operations)

    Delegates data access to ModelConfigurationRepository.
    """

    def __init__(self):
        """Initialize the service with a repository instance."""
        self.repository = ModelConfigurationRepository()

    def list_all(self, db: Session) -> List[ModelConfigurationResponse]:
        """
        Retrieve all model configurations.

        Args:
            db: SQLAlchemy database session

        Returns:
            List of ModelConfigurationResponse objects with credentials filtered
        """
        db_configs = self.repository.get_all(db)
        return [self._to_response(config) for config in db_configs]

    def get_by_alias(self, db: Session, alias: str, raw=False) -> Optional[ModelConfigurationResponse]:
        """
        Retrieve a model configuration by alias (case-sensitive exact match).

        Args:
            db: SQLAlchemy database session
            alias: Model alias to look up
            raw: If True, return unredacted LiteLlm config dict instead of response model

        Returns:
            ModelConfigurationResponse if found, None otherwise
        """
        db_config = self.repository.get_by_alias(db, alias)

        if not db_config:
            return None

        if raw:
            return self._to_raw_litellm_config(db_config)
        return self._to_response(db_config)
    
    def get_by_alias_or_id(self, db: Session, alias: str, raw=False) -> Optional[Dict]:
        """
        Retrieve a model configuration by alias (case-sensitive exact match) or ID.

        Args:
            db: SQLAlchemy database session
            alias: Model alias or ID to look up
            raw: If True, return unredacted LiteLlm config dict instead of response model

        Returns:
            ModelConfigurationResponse if found, None otherwise
        """
        db_config = self.repository.get_by_alias_or_id(db, alias)

        if not db_config:
            return None

        if raw:
            return self._to_raw_litellm_config(db_config)
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

    @staticmethod
    def _to_raw_litellm_config(db_model: ModelConfiguration) -> Dict:
        """Build an unredacted LiteLlm config dict from a DB record."""
        config = {"model": db_model.model_name}
        if db_model.api_base:
            config["api_base"] = db_model.api_base
        # Merge auth credentials (unredacted)
        if db_model.model_auth_config:
            auth_config = dict(db_model.model_auth_config)
            auth_config.pop("type", None)
            config.update(auth_config)
        # Merge model params
        if db_model.model_params:
            config.update(db_model.model_params)
        return config
