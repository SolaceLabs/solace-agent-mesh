"""Service layer for model configuration business logic."""

import logging
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session

try:
    import litellm
except ImportError:
    litellm = None

from solace_agent_mesh.services.platform.repositories import ModelConfigurationRepository
from solace_agent_mesh.services.platform.models import ModelConfiguration
from solace_agent_mesh.services.platform.api.routers.dto.responses import (
    ModelConfigurationResponse,
)
from solace_agent_mesh.services.platform.api.routers.dto.requests import (
    ModelConfigurationCreateRequest,
    ModelConfigurationUpdateRequest,
    ModelConfigurationTestRequest,
)
from solace_agent_mesh.shared.utils.secret_redactor import redact_auth_config
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from solace_agent_mesh.common.oauth.oauth_client import OAuth2Client

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

    def get_by_alias(self, db: Session, alias: str) -> Optional[ModelConfigurationResponse]:
        """
        Retrieve a model configuration by alias (case-sensitive exact match).

        Args:
            db: SQLAlchemy database session
            alias: Model alias to look up

        Returns:
            ModelConfigurationResponse if found, None otherwise
        """
        db_config = self.repository.get_by_alias(db, alias)

        if not db_config:
            return None

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
            ValueError: If alias already exists (case-sensitive, matches unique index)
        """
        # Check for duplicate alias (case-sensitive, matches unique index)
        if self.repository.exists_by_alias(db, request.alias):
            raise ValueError(f"Model configuration with alias '{request.alias}' already exists")

        # Auto-fill api_base for known providers if not provided
        api_base = request.api_base
        if not api_base and request.provider in _DEFAULT_API_BASES:
            api_base = _DEFAULT_API_BASES[request.provider]

        # Create new configuration
        db_config = ModelConfiguration(
            alias=request.alias,
            provider=request.provider,
            model_name=request.model_name,
            api_base=api_base,
            model_auth_type=request.auth_type,
            model_auth_config=request.auth_config or {},
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
    ) -> Optional[ModelConfigurationResponse]:
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
            ModelConfigurationResponse if found and updated, None if not found

        Raises:
            ValueError: If new alias already exists (case-sensitive)
        """
        db_config = self.repository.get_by_alias(db, alias)

        if not db_config:
            return None

        # If updating alias, check for case-sensitive collision with other configs
        if request.alias is not None and request.alias != alias:
            if self.repository.exists_by_alias(db, request.alias):
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
        elif request.provider is not None and request.provider in _DEFAULT_API_BASES:
            # Auto-fill api_base if provider changed to a known provider
            db_config.api_base = _DEFAULT_API_BASES[request.provider]
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

        self.repository.update(db, db_config)

        return self._to_response(db_config)

    def delete(self, db: Session, alias: str) -> bool:
        """
        Delete a model configuration by alias.

        Args:
            db: SQLAlchemy database session
            alias: Model alias to delete

        Returns:
            True if configuration was found and deleted, False otherwise
        """
        db_config = self.repository.get_by_alias(db, alias)

        if not db_config:
            return False

        self.repository.delete(db, db_config)

        return True

    def test_connection(
        self, db: Session, request: ModelConfigurationTestRequest
    ) -> Tuple[bool, str]:
        """
        Test a model configuration connection by making a minimal LLM call.

        Supports two scenarios:
        1. New configuration: Provide provider, model_name, and credentials
        2. Test existing model: Provide alias to load full config from database
           - Provider/model_name optional (loaded from database if not provided)
           - Credentials loaded from database as fallback

        Args:
            db: SQLAlchemy database session
            request: Test request with model configuration details

        Returns:
            Tuple of (success: bool, message: str) where message contains either
            the LLM response (on success) or error details (on failure)
        """
        try:
            if not litellm:
                return False, "litellm library not available"

            # Resolve configuration from alias or request
            provider = request.provider
            model_name = request.model_name
            auth_config = dict(request.auth_config or {})
            auth_type = request.auth_type
            api_base = request.api_base

            # Load stored config if alias provided
            if request.alias:
                stored_config = self.get_raw_config_by_alias(db, request.alias)
                if not stored_config:
                    return False, f"Model configuration with alias '{request.alias}' not found"

                # Use stored values as defaults if not provided in request
                if not provider:
                    provider = stored_config.provider
                if not model_name:
                    model_name = stored_config.model_name

                # Use stored auth_type if not explicitly provided in request
                if not request.auth_type or request.auth_type == "none":
                    auth_type = stored_config.model_auth_type or "none"

                # Use stored credentials as fallback for empty fields
                stored_auth = stored_config.model_auth_config or {}
                for key, stored_value in stored_auth.items():
                    if key not in auth_config or not auth_config[key]:
                        auth_config[key] = stored_value

                # Use stored api_base if not provided in request
                if not api_base and stored_config.api_base:
                    api_base = stored_config.api_base

            # Validate required fields
            if not provider:
                return False, "provider is required (either in request or via alias)"
            if not model_name:
                return False, "model_name is required (either in request or via alias)"

            # Resolve api_base: auto-fill from defaults if not provided
            if not api_base and provider in _DEFAULT_API_BASES:
                api_base = _DEFAULT_API_BASES[provider]

            # Build litellm call kwargs
            litellm_kwargs: Dict[str, Any] = {
                "model": model_name,
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 5,
            }

            # Add api_base if available
            if api_base:
                litellm_kwargs["api_base"] = api_base

            # Handle authentication based on auth_type
            if auth_type == "apikey":
                api_key = auth_config.get("api_key")
                if api_key:
                    litellm_kwargs["api_key"] = api_key
            elif auth_type == "oauth2":
                # Fetch OAuth2 token and pass as Bearer in Authorization header
                token = self._fetch_oauth2_token(auth_config)
                if token:
                    litellm_kwargs["api_key"] = token
                else:
                    return False, "Failed to fetch OAuth2 token"

            # Add model_params as top-level kwargs to allow provider validation
            if request.model_params:
                litellm_kwargs.update(request.model_params)

            # Make the test call
            response = litellm.completion(**litellm_kwargs)

            # Extract response message
            if response and response.choices and len(response.choices) > 0:
                message_content = response.choices[0].message.content
                return True, message_content or "Connection successful"
            else:
                return False, "No response from LLM"

        except Exception as e:
            # Return error message, but sanitize it to avoid exposing sensitive data
            error_msg = str(e)
            # Truncate very long errors
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            return False, error_msg

    @staticmethod
    def _fetch_oauth2_token(auth_config: Dict[str, Any]) -> Optional[str]:
        """
        Fetch an OAuth2 access token using client credentials flow.

        Args:
            auth_config: Auth config dict with oauth credentials

        Returns:
            Access token string if successful, None otherwise
        """
        try:
            client_id = auth_config.get("client_id")
            client_secret = auth_config.get("client_secret")
            token_url = auth_config.get("token_url")
            scope = auth_config.get("scope")
            ca_cert_path = auth_config.get("ca_cert")

            if not all([client_id, client_secret, token_url]):
                log.warning("Missing required OAuth2 fields: client_id, client_secret, token_url")
                return None

            # Fetch token using OAuth2Client
            response = OAuth2Client.fetch_client_credentials_token(
                token_url=token_url,
                client_id=client_id,
                client_secret=client_secret,
                scope=scope,
                verify=ca_cert_path or True,
                timeout=10.0,
            )

            return response.get("access_token") if response else None
        except Exception as e:
            log.error(f"Failed to fetch OAuth2 token: {e}")
            return None

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
