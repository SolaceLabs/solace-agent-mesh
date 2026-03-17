"""Service layer for model configuration business logic."""

import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from solace_agent_mesh.services.platform.models import ModelConfiguration
from solace_agent_mesh.services.platform.api.routers.dto.responses import (
    ModelConfigurationResponse,
)
from solace_agent_mesh.services.platform.api.routers.dto.requests import (
    ModelConfigurationCreateRequest,
    ModelConfigurationUpdateRequest,
)
from solace_agent_mesh.shared.utils.secret_redactor import redact_auth_config
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms

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

    def get_raw_config_by_alias(self, alias: str) -> Optional[ModelConfiguration]:
        """
        Retrieve raw model configuration by alias (case-sensitive exact match).

        This returns the unredacted database model with all credentials intact.
        For internal use only (e.g., backend proxy calls to fetch models).
        Do NOT return this to external API clients.

        Args:
            alias: Model alias to look up

        Returns:
            ModelConfiguration database model if found, None otherwise
        """
        return self.db.query(ModelConfiguration).filter(
            ModelConfiguration.alias == alias
        ).first()

    def create(
        self, request: ModelConfigurationCreateRequest, created_by: str
    ) -> ModelConfigurationResponse:
        """
        Create a new model configuration.

        Args:
            request: Create request with model details
            created_by: User or system identifier creating the configuration

        Returns:
            ModelConfigurationResponse for the created configuration

        Raises:
            ValueError: If alias already exists (case-insensitive)
        """
        # Check for duplicate alias (case-insensitive)
        existing = self.db.query(ModelConfiguration).filter(
            func.lower(ModelConfiguration.alias) == request.alias.lower()
        ).first()

        if existing:
            raise ValueError(f"Model configuration with alias '{request.alias}' already exists")

        # Create new configuration
        db_config = ModelConfiguration(
            alias=request.alias,
            provider=request.provider,
            model_name=request.model_name,
            api_base=request.api_base,
            model_auth_type=request.auth_type,
            model_auth_config=request.auth_config or {},
            model_params=request.model_params or {},
            description=request.description,
            created_by=created_by,
            updated_by=created_by,
            created_time=now_epoch_ms(),
            updated_time=now_epoch_ms(),
        )

        self.db.add(db_config)
        self.db.commit()
        self.db.refresh(db_config)

        return self._to_response(db_config)

    def update(
        self,
        alias: str,
        request: ModelConfigurationUpdateRequest,
        updated_by: str,
    ) -> Optional[ModelConfigurationResponse]:
        """
        Update an existing model configuration.

        Only provided (non-None) fields are updated.
        For auth_config: if provided, it's merged with existing secrets (preserving
        secrets for fields not in the update request).

        Args:
            alias: Model alias to update
            request: Update request with new values
            updated_by: User or system identifier performing the update

        Returns:
            ModelConfigurationResponse if found and updated, None if not found

        Raises:
            ValueError: If new alias already exists (case-insensitive)
        """
        db_config = self.db.query(ModelConfiguration).filter(
            ModelConfiguration.alias == alias
        ).first()

        if not db_config:
            return None

        # If updating alias, check for case-insensitive collision with other configs
        if request.alias is not None and request.alias.lower() != alias.lower():
            existing = self.db.query(ModelConfiguration).filter(
                func.lower(ModelConfiguration.alias) == request.alias.lower()
            ).first()
            if existing:
                raise ValueError(f"Model configuration with alias '{request.alias}' already exists")

        # Update only provided fields
        if request.alias is not None:
            db_config.alias = request.alias
        if request.provider is not None:
            db_config.provider = request.provider
        if request.model_name is not None:
            db_config.model_name = request.model_name
        if request.api_base is not None:
            db_config.api_base = request.api_base
        if request.auth_type is not None:
            db_config.model_auth_type = request.auth_type
        if request.auth_config is not None:
            # Merge with existing auth config (preserve existing secrets)
            existing_config = db_config.model_auth_config or {}
            db_config.model_auth_config = {**existing_config, **request.auth_config}
        if request.model_params is not None:
            db_config.model_params = request.model_params
        if request.description is not None:
            db_config.description = request.description

        db_config.updated_by = updated_by
        db_config.updated_time = now_epoch_ms()

        self.db.commit()
        self.db.refresh(db_config)

        return self._to_response(db_config)

    def delete(self, alias: str) -> bool:
        """
        Delete a model configuration by alias.

        Args:
            alias: Model alias to delete

        Returns:
            True if configuration was found and deleted, False otherwise
        """
        db_config = self.db.query(ModelConfiguration).filter(
            ModelConfiguration.alias == alias
        ).first()

        if not db_config:
            return False

        self.db.delete(db_config)
        self.db.commit()

        return True

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
