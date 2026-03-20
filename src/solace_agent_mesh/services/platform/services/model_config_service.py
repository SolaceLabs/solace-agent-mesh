"""Service layer for model configuration business logic."""

import logging

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from solace_agent_mesh.services.platform.repositories import ModelConfigurationRepository
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
from solace_agent_mesh.shared.exceptions.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
)

log = logging.getLogger(__name__)

# Default API bases for known providers
_DEFAULT_API_BASES = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "google_ai_studio": "https://generativelanguage.googleapis.com/v1beta",
    "vertex_ai": "https://us-central1-aiplatform.googleapis.com/v1",
    "azure_openai": "https://{resource_name}.openai.azure.com/",
    "bedrock": "https://bedrock-runtime.us-east-1.amazonaws.com",
    "ollama": "http://localhost:11434",
}


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

    def get_by_alias(self, db: Session, alias: str, raw=False) -> ModelConfigurationResponse:
        """
        Retrieve a model configuration by alias (case-sensitive exact match).

        Args:
            db: SQLAlchemy database session
            alias: Model alias to look up
            raw: If True, return unredacted LiteLlm config dict instead of response model

        Returns:
            ModelConfigurationResponse if found, or dict if raw=True

        Raises:
            EntityNotFoundError: If no configuration found with the given alias
        """
        db_config = self.repository.get_by_alias(db, alias)

        if not db_config:
            raise EntityNotFoundError("ModelConfiguration", alias)

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

    def get_raw_config_by_alias(self, db: Session, alias: str) -> Optional[ModelConfiguration]:
        """
        Retrieve raw model configuration by alias (case-sensitive exact match).

        This returns the unredacted database model with all credentials intact.
        For internal use only (e.g., backend proxy calls to fetch models).
        Do NOT return this to external API clients.

        Args:
            db: SQLAlchemy database session
            alias: Model alias to look up

        Returns:
            ModelConfiguration database model if found, None otherwise
        """
        return db.query(ModelConfiguration).filter(
            ModelConfiguration.alias == alias
        ).first()

    def create(
        self, db: Session, request: ModelConfigurationCreateRequest, created_by: str
    ) -> ModelConfigurationResponse:
        """
        Create a new model configuration.

        For known providers, auto-fills api_base if not provided.

        Args:
            db: SQLAlchemy database session
            request: Create request with model details
            created_by: User or system identifier creating the configuration

        Returns:
            ModelConfigurationResponse for the created configuration

        Raises:
            EntityAlreadyExistsError: If alias already exists (case-sensitive, matches unique index)
        """
        # Check for duplicate alias (case-sensitive, matches unique index)
        if self.repository.exists_by_alias(db, request.alias):
            raise EntityAlreadyExistsError("ModelConfiguration", "alias", request.alias)

        # Auto-fill api_base for known providers if not provided
        api_base = request.api_base
        if not api_base and request.provider in _DEFAULT_API_BASES:
            api_base = _DEFAULT_API_BASES[request.provider]

        # Extract auth_type from auth_config['type'], default to 'none'
        auth_config = request.auth_config or {}
        auth_type = auth_config.get("type", "none")

        # Create new configuration
        db_config = ModelConfiguration(
            alias=request.alias,
            provider=request.provider,
            model_name=request.model_name,
            api_base=api_base,
            model_auth_type=auth_type,
            model_auth_config=auth_config,
            model_params=request.model_params or {},
            description=request.description,
            created_by=created_by,
            updated_by=created_by,
            created_time=now_epoch_ms(),
            updated_time=now_epoch_ms(),
        )

        self.repository.create(db, db_config)

        return self._to_response(db_config)

    def update(
        self,
        db: Session,
        alias: str,
        request: ModelConfigurationUpdateRequest,
        updated_by: str,
    ) -> ModelConfigurationResponse:
        """
        Update an existing model configuration.

        Only provided (non-None) fields are updated.
        For auth_config: if provided, it's merged with existing secrets (preserving
        secrets for fields not in the update request).

        Args:
            db: SQLAlchemy database session
            alias: Model alias to update
            request: Update request with new values
            updated_by: User or system identifier performing the update

        Returns:
            ModelConfigurationResponse for the updated configuration

        Raises:
            EntityNotFoundError: If no configuration found with the given alias
            EntityAlreadyExistsError: If new alias already exists (case-sensitive)
        """
        db_config = self.repository.get_by_alias(db, alias)

        if not db_config:
            raise EntityNotFoundError("ModelConfiguration", alias)

        # If updating alias, check for case-sensitive collision with other configs
        if request.alias is not None and request.alias != alias:
            if self.repository.exists_by_alias(db, request.alias):
                raise EntityAlreadyExistsError("ModelConfiguration", "alias", request.alias)

        # Update only provided fields
        if request.alias is not None:
            db_config.alias = request.alias
        if request.provider is not None:
            db_config.provider = request.provider
        if request.model_name is not None:
            db_config.model_name = request.model_name
        if request.api_base is not None:
            db_config.api_base = request.api_base
        elif request.provider is not None and request.provider in _DEFAULT_API_BASES:
            # Auto-fill api_base if provider changed to a known provider
            db_config.api_base = _DEFAULT_API_BASES[request.provider]
        if request.auth_config is not None:
            # Merge with existing auth config (preserve existing secrets)
            existing_config = db_config.model_auth_config or {}
            merged_config = {**existing_config, **request.auth_config}
            db_config.model_auth_config = merged_config
            # Update auth_type from the merged config's 'type' field
            if "type" in merged_config:
                db_config.model_auth_type = merged_config["type"]
        if request.model_params is not None:
            db_config.model_params = request.model_params
        if request.description is not None:
            db_config.description = request.description

        db_config.updated_by = updated_by
        db_config.updated_time = now_epoch_ms()

        self.repository.update(db, db_config)

        return self._to_response(db_config)

    def delete(self, db: Session, alias: str) -> None:
        """
        Delete a model configuration by alias.

        Args:
            db: SQLAlchemy database session
            alias: Model alias to delete

        Raises:
            EntityNotFoundError: If no configuration found with the given alias
        """
        db_config = self.repository.get_by_alias(db, alias)

        if not db_config:
            raise EntityNotFoundError("ModelConfiguration", alias)

        self.repository.delete(db, db_config)

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
