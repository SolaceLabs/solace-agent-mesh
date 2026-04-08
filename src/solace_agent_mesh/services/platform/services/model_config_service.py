"""Service layer for model configuration business logic."""

import logging

from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session

try:
    import litellm
except ImportError:
    litellm = None


from solace_agent_mesh.services.platform.repositories import ModelConfigurationRepository
from solace_agent_mesh.services.platform.services.model_list_service import ModelListService
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
from solace_agent_mesh.shared.exceptions.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    ValidationErrorBuilder,
)
from solace_agent_mesh.common.oauth import OAuth2Client

log = logging.getLogger(__name__)

# LiteLLM uses model name prefixes to route calls to the correct backend.
# Without the correct prefix, LiteLLM may route to the wrong provider
# (e.g., a bare "gemini-pro" routes to Vertex AI instead of Google AI Studio).
_LITELLM_PROVIDER_PREFIXES = {
    "google_ai_studio": "gemini/",
    "vertex_ai": "vertex_ai/",
    "bedrock": "bedrock/",
    "ollama": "ollama/",
    "azure_openai": "azure/",
}

# Providers where LiteLLM resolves the endpoint internally via its prefix routing.
# For these, passing api_base to LiteLLM is unnecessary and can cause it to bypass
# its native auth handling (e.g., routing Google AI Studio calls to Vertex AI).
_LITELLM_MANAGES_ENDPOINT = frozenset({
    "google_ai_studio",
    "vertex_ai",
    "bedrock",
    "anthropic",
    "openai",
})


def _resolve_litellm_model_name(provider: Optional[str], model_name: str) -> str:
    """Prepend the LiteLLM provider prefix to a model name if it doesn't already have one."""
    if not provider or not model_name:
        return model_name
    required_prefix = _LITELLM_PROVIDER_PREFIXES.get(provider)
    if required_prefix and not model_name.startswith(required_prefix) and "/" not in model_name:
        return f"{required_prefix}{model_name}"
    return model_name


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

    def get_models_from_provider_by_id(
        self,
        db: Session,
        model_id: str,
        model_list_service: ModelListService,
        provider_override: Optional[str] = None,
        auth_config_overrides: Optional[Dict[str, Any]] = None,
        api_base_override: Optional[str] = None,
    ) -> List[Dict]:
        """
        Fetch supported models using a stored model configuration as a base.

        Retrieves the configuration by ID, then resolves the final provider,
        credentials, and API base based on what the user changed in the form:

        - **Same provider, no overrides**: Uses stored credentials as-is.
        - **Same provider, with overrides**: Merges — stored credentials fill in
          any missing fields (e.g., user changed API key but not secret key).
        - **Different provider**: Discards stored credentials entirely and uses
          only the overrides. Only model_params carry over (provider-agnostic).

        Args:
            db: SQLAlchemy database session
            model_id: Model configuration UUID to look up
            model_list_service: ModelListService instance for fetching provider models
            provider_override: Provider from the request. When different from stored,
                stored credentials are discarded (cross-provider leak prevention).
            auth_config_overrides: Auth config from the request to merge or replace.
            api_base_override: API base URL override from the request.

        Returns:
            List of available models from the provider

        Raises:
            EntityNotFoundError: If no configuration found with the given ID
            RuntimeError: If provider API query fails
        """
        raw_config = self.repository.get_by_id(db, model_id)
        if not raw_config:
            raise EntityNotFoundError("ModelConfiguration", model_id)

        provider_changed = provider_override and provider_override != raw_config.provider

        if provider_changed:
            # Provider switched — use overrides only, carry over model_params
            return model_list_service.get_models_by_provider_with_config(
                provider=provider_override,
                api_base=api_base_override,
                auth_type=(auth_config_overrides or {}).get("type"),
                auth_config=auth_config_overrides or {},
                model_params=raw_config.model_params or {},
            )

        # Same provider — start from stored config
        auth_config = raw_config.model_auth_config or {}
        auth_type = raw_config.model_auth_type
        api_base = raw_config.api_base

        if auth_config_overrides:
            override_auth_type = auth_config_overrides.get("type")

            if override_auth_type == auth_type:
                # Same auth type — stored credentials fill in missing override fields
                merged = dict(auth_config)
                for key, value in auth_config_overrides.items():
                    if value:
                        merged[key] = value
                auth_config = merged
            else:
                # Auth type changed within same provider — use overrides only
                auth_config = auth_config_overrides
                auth_type = override_auth_type

        if api_base_override:
            api_base = api_base_override

        return model_list_service.get_models_by_provider_with_config(
            provider=raw_config.provider,
            api_base=api_base,
            auth_type=auth_type,
            auth_config=auth_config,
            model_params=raw_config.model_params or {},
        )
    
    def get_by_id(self, db: Session, model_id: str, raw=False) -> ModelConfigurationResponse:
        """
        Retrieve a model configuration by ID.

        Args:
            db: SQLAlchemy database session
            model_id: Model UUID to look up
            raw: If True, return unredacted LiteLlm config dict instead of response model

        Returns:
            ModelConfigurationResponse if found, or dict if raw=True

        Raises:
            EntityNotFoundError: If no configuration found with the given ID
        """
        db_config = self.repository.get_by_id(db, model_id)

        if not db_config:
            raise EntityNotFoundError("ModelConfiguration", model_id)

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
        alias = request.alias.strip() if request.alias else None
        if alias is not None and not alias:
            raise ValidationErrorBuilder().message("Alias cannot be empty or contain only whitespace").build()
        if self.repository.exists_by_alias(db, alias):
            raise EntityAlreadyExistsError("ModelConfiguration", "alias", alias)

        # Auto-fill api_base for known providers if not provided
        api_base = request.api_base
        if not api_base and request.provider in _DEFAULT_API_BASES:
            api_base = _DEFAULT_API_BASES[request.provider]

        # Extract auth_type from auth_config['type'], default to 'none'
        auth_config = request.auth_config or {}
        auth_type = auth_config.get("type", "none")

        # Create new configuration
        db_config = ModelConfiguration(
            alias=alias,
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
        model_id: str,
        request: ModelConfigurationUpdateRequest,
        updated_by: str,
    ) -> ModelConfigurationResponse:
        """
        Update an existing model configuration by ID.

        Only provided (non-None) fields are updated.
        For auth_config: if provided, it's merged with existing secrets (preserving
        secrets for fields not in the update request).

        Args:
            db: SQLAlchemy database session
            model_id: Model UUID to update
            request: Update request with new values
            updated_by: User or system identifier performing the update

        Returns:
            ModelConfigurationResponse for the updated configuration

        Raises:
            EntityNotFoundError: If no configuration found with the given ID
            EntityAlreadyExistsError: If new alias already exists (case-sensitive)
        """
        db_config = self.repository.get_by_id(db, model_id)

        if not db_config:
            raise EntityNotFoundError("ModelConfiguration", model_id)

        alias = request.alias.strip() if request.alias else None
        if alias is not None and not alias:
            raise ValidationErrorBuilder().message("Alias cannot be empty or contain only whitespace").build()
        # If updating alias, check for case-sensitive collision with other configs
        if alias is not None and alias != db_config.alias:
            if self.repository.exists_by_alias(db, alias):
                raise EntityAlreadyExistsError("ModelConfiguration", "alias", alias)

        # Update only provided fields
        if alias is not None:
            db_config.alias = alias
        if request.provider is not None:
            db_config.provider = request.provider
        if request.model_name is not None:
            db_config.model_name = request.model_name
        if request.api_base is not None:
            # Empty string means "clear this field" — store as None
            db_config.api_base = request.api_base or None
        elif request.provider is not None and request.provider in _DEFAULT_API_BASES:
            # Auto-fill api_base if provider changed to a known provider
            db_config.api_base = _DEFAULT_API_BASES[request.provider]
        if request.auth_config is not None:
            existing_config = db_config.model_auth_config or {}
            new_auth_type = request.auth_config.get("type")
            old_auth_type = existing_config.get("type")

            if new_auth_type != old_auth_type:
                # Auth type changed (e.g., provider switch) — replace entirely.
                # Old credentials are for a different auth scheme and must not leak.
                db_config.model_auth_config = request.auth_config
            else:
                # Same auth type — merge to preserve stored secrets the user didn't re-enter
                merged_config = {**existing_config, **request.auth_config}
                db_config.model_auth_config = merged_config

            # Update auth_type from the config's 'type' field
            final_config = db_config.model_auth_config or {}
            if "type" in final_config:
                db_config.model_auth_type = final_config["type"]
        if request.model_params is not None:
            db_config.model_params = request.model_params
        if request.description is not None:
            db_config.description = request.description

        db_config.updated_by = updated_by
        db_config.updated_time = now_epoch_ms()

        self.repository.update(db, db_config)

        return self._to_response(db_config)

    def delete(self, db: Session, model_id: str) -> None:
        """
        Delete a model configuration by ID.

        Args:
            db: SQLAlchemy database session
            model_id: Model UUID to delete

        Raises:
            EntityNotFoundError: If no configuration found with the given ID
        """
        db_config = self.repository.get_by_id(db, model_id)

        if not db_config:
            raise EntityNotFoundError("ModelConfiguration", model_id)

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
        """
        Format a model configuration as a LiteLlm config dict.

        Extracts model name, api_base, unredacted auth credentials, and model params
        into a format suitable for LiteLlm library calls.

        Args:
            db_model: ModelConfiguration ORM model

        Returns:
            Dict with keys: model, api_base (optional), auth credentials, model params
        """
        config = {"model": _resolve_litellm_model_name(db_model.provider, db_model.model_name)}
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

    def test_connection(self, db: Session, request: ModelConfigurationTestRequest) -> Tuple[bool, str]:
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
                return False, "Test connection failed. litellm library not available"

            # Resolve configuration from alias or request
            provider = request.provider
            model_name = request.model_name
            auth_config = dict(request.auth_config or {})
            api_base = request.api_base

            # Load stored config if model_id provided
            if request.model_id:
                stored_config = self.repository.get_by_id(db, request.model_id)
                if not stored_config:
                    return False, f"Test connection failed. Model configuration with ID '{request.model_id}' not found"

                # Use stored values as defaults if not provided in request
                if not provider:
                    provider = stored_config.provider
                if not model_name:
                    model_name = stored_config.model_name

                # Use stored credentials as fallback for empty fields
                stored_auth = stored_config.model_auth_config or {}
                for key, stored_value in stored_auth.items():
                    if key not in auth_config or not auth_config[key]:
                        auth_config[key] = stored_value

                # Use stored api_base if not provided in request
                if not api_base and stored_config.api_base:
                    api_base = stored_config.api_base

            # Derive auth_type from auth_config
            auth_type = auth_config.get("type", "none")

            # Validate required fields
            if not provider:
                return False, "Test connection failed. provider is required (either in request or via alias)"
            if not model_name:
                return False, "Test connection failed. model_name is required (either in request or via alias)"

            # Resolve api_base: auto-fill from defaults if not provided
            if not api_base and provider in _DEFAULT_API_BASES:
                api_base = _DEFAULT_API_BASES[provider]

            # Build litellm call kwargs
            litellm_kwargs: Dict[str, Any] = {
                "model": _resolve_litellm_model_name(provider, model_name),
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 5,
            }

            # Only pass api_base for providers that need a custom endpoint (e.g., Ollama, Azure,
            # custom). For providers where LiteLLM handles the endpoint via its prefix routing
            # (Google AI Studio, Vertex AI, Bedrock, etc.), passing api_base can cause LiteLLM
            # to bypass its native auth handling.
            if api_base and provider not in _LITELLM_MANAGES_ENDPOINT:
                litellm_kwargs["api_base"] = api_base

            # Flatten auth_config into litellm kwargs — same approach as _to_raw_litellm_config().
            # OAuth2 is the only special case: exchange credentials for a bearer token first.
            auth_kwargs = dict(auth_config)
            auth_kwargs.pop("type", None)
            if auth_type == "oauth2":
                token = self._fetch_oauth2_token(auth_kwargs)
                if token:
                    litellm_kwargs["api_key"] = token
                else:
                    return False, "Test connection failed. Failed to fetch OAuth2 token"
            else:
                litellm_kwargs.update(auth_kwargs)

            # For connection testing, do NOT include model_params.
            # The test is purely to verify connectivity and authentication work.
            # Custom parameters are validated during actual model usage, not in the test.

            # Make the test call
            response = litellm.completion(**litellm_kwargs)

            # Extract response message
            if response and response.choices and len(response.choices) > 0:
                return True, "Connection test successful"
            else:
                return False, "Test connection failed. No response from LLM"

        except Exception as e:
            # Return error message, but sanitize it to avoid exposing sensitive data
            error_msg = str(e)
            # Truncate very long errors
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            return False, f"Test connection failed. {error_msg}"

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

