"""Service for seeding model configurations from YAML config or environment variables.

This module separates data initialization (DML) from schema creation (DDL).
Seeding runs during application startup after migrations complete, not during
migration execution. This ensures:

- Clear separation of concerns (schema vs data)
- Proper lifecycle management (migrations are idempotent; seeding can use upsert)
- Access to component configuration (shared_config from YAML)
- Transaction ownership in the appropriate layer (enterprise startup tasks)
"""

import logging
import os
from typing import Optional
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from sqlalchemy import func

from solace_agent_mesh.shared.database.id_generators import generate_uuidv7

log = logging.getLogger(__name__)


def _infer_provider(api_base: str, model_name: str = "") -> str:
    """
    Infer provider type from api_base URL and model name.

    Phase 1: Check api_base for known provider-specific domains using exact hostname matching.
    Phase 2: Check path patterns for OpenAI-style endpoints.
    Phase 3: Check model name routing prefixes.

    Args:
        api_base: API base URL
        model_name: Model name for provider detection

    Returns:
        Provider type string (e.g., 'openai', 'anthropic', 'custom')
    """
    # Phase 1: Check api_base for well-known provider domains
    if api_base:
        try:
            parsed = urlparse(api_base)
            hostname = (parsed.hostname or "").lower()
            path = (parsed.path or "").lower()
        except Exception:
            hostname = ""
            path = ""

        # Exact hostname matches
        if hostname == "api.openai.com":
            return "openai"
        elif hostname == "api.anthropic.com":
            return "anthropic"
        elif ".openai.azure.com" in hostname:
            return "azure_openai"
        elif ("bedrock" in hostname) or (".amazonaws.com" in hostname and "bedrock" in path):
            return "bedrock"
        elif "aiplatform.googleapis.com" in hostname or "vertex.googleapis.com" in hostname:
            return "vertex_ai"
        elif "generativelanguage.googleapis.com" in hostname or "makersuite.google.com" in hostname:
            return "google_ai_studio"

        # Phase 2: Check for OpenAI-style endpoint paths
        if "/v1/" in path:
            return "custom"

    # Phase 3: Check model name routing prefixes
    if model_name:
        model_lower = model_name.lower()

        if model_lower.startswith("openai/"):
            return "custom"
        elif "gemini" in model_lower:
            return "google_ai_studio"
        elif model_lower.startswith("claude"):
            return "anthropic"
        elif "gpt" in model_lower:
            return "openai"

    return "custom"


def _get_default_api_base(provider: str) -> Optional[str]:
    """
    Get the default API base URL for a known provider.

    For providers with a standard API endpoint, returns that URL.
    For providers where the endpoint is region-specific or requires configuration,
    returns None.

    Args:
        provider: Provider type (e.g., 'openai', 'google_ai_studio')

    Returns:
        Default API base URL, or None if not applicable
    """
    provider_lower = provider.lower()

    # Providers with standard endpoints
    if provider_lower == "openai":
        return "https://api.openai.com/v1"
    elif provider_lower == "anthropic":
        return "https://api.anthropic.com/v1"
    elif provider_lower == "google_ai_studio":
        return "https://generativelanguage.googleapis.com/v1"
    elif provider_lower == "vertex_ai":
        # Default to us-central1; users can override with api_base if needed
        return "https://us-central1-aiplatform.googleapis.com/v1"

    # Providers that require explicit configuration (region-specific, custom, etc.)
    # bedrock, azure_openai, custom
    return None


def _extract_auth_type_and_config(config_data: dict) -> tuple[str, dict]:
    """
    Extract authentication type and configuration from model config dict.

    Supports API key and OAuth2. Auth types follow enterprise convention:
    - "apikey" (for API key authentication, matches AUTH_SECRET_FIELDS in secret_redactor.py)
    - "oauth2" (for OAuth2 authentication)
    - "none" (for no authentication)

    Returns:
        Tuple of (auth_type, auth_config) where auth_type is one of the above
    """
    # Check for API key auth
    if "api_key" in config_data:
        return "apikey", {
            "api_key": config_data["api_key"]
        }

    # Check for OAuth2
    if "oauth_client_id" in config_data or "oauth_token_url" in config_data:
        oauth_config = {}

        if "oauth_client_id" in config_data:
            oauth_config["client_id"] = config_data["oauth_client_id"]
        if "oauth_client_secret" in config_data:
            oauth_config["client_secret"] = config_data["oauth_client_secret"]
        if "oauth_token_url" in config_data:
            oauth_config["token_url"] = config_data["oauth_token_url"]
        if "oauth_scope" in config_data:
            oauth_config["scope"] = config_data["oauth_scope"]
        if "oauth_ca_cert" in config_data:
            oauth_config["ca_cert"] = config_data["oauth_ca_cert"]
        if "oauth_token_refresh_buffer_seconds" in config_data:
            oauth_config["token_refresh_buffer_seconds"] = config_data["oauth_token_refresh_buffer_seconds"]

        return "oauth2", oauth_config

    # No auth
    return "none", {}


def _extract_model_params(config_data: dict) -> dict:
    """Extract model parameters (everything except core fields)."""
    core_fields = {
        "model", "api_base", "api_key",
        "oauth_token_url", "oauth_client_id", "oauth_client_secret",
        "oauth_scope", "oauth_ca_cert", "oauth_token_refresh_buffer_seconds"
    }

    return {
        k: v for k, v in config_data.items()
        if k not in core_fields
    }


def seed_model_configurations(
    db: Session,
    models_config: Optional[dict] = None
) -> int:
    """
    Seed model configurations from YAML config or environment variables.

    This is a DML operation (data initialization) that runs during application
    startup, separate from schema creation in migrations.

    Args:
        db: SQLAlchemy database session
        models_config: Models configuration dict from shared_config (optional)

    Returns:
        Number of model configurations in the table (seeded or already existing)
    """
    from solace_agent_mesh.services.platform.models import ModelConfiguration

    existing_count = db.query(func.count(ModelConfiguration.id)).scalar()

    seeded_aliases = set()

    if existing_count == 0:
        # Try seeding from models_config if provided
        if models_config:
            log.info("[Model Seed] Seeding from config with %d entries", len(models_config))
            seeded_aliases = _seed_from_models_config(db, models_config)

        # If no models_config provided or empty, seed from environment variables
        if not seeded_aliases:
            log.info("[Model Seed] No models_config provided, seeding from environment variables")
            seeded_aliases = _seed_from_env_vars(db)

        if seeded_aliases:
            log.info("[Model Seed] Successfully seeded %d model configurations", len(seeded_aliases))
        else:
            log.warning("[Model Seed] No model configurations seeded from config or env vars")
    else:
        log.info("[Model Seed] Table has %d existing configurations, skipping bulk seed", existing_count)

    # Always ensure general and planning placeholder records exist
    defaults_created = _ensure_default_aliases(db, seeded_aliases)
    seeded_aliases.update(defaults_created)

    return existing_count + len(seeded_aliases)


def _ensure_default_aliases(db: Session, seeded_aliases: set = None) -> set:
    """
    Ensure 'general' and 'planning' model aliases exist in the DB.

    Creates placeholder records for any missing default aliases so the UI
    always has these entries to display. Placeholders use PLACEHOLDER_VALUE
    for provider and model_name, which the service layer strips to None
    before returning to clients.

    Args:
        db: SQLAlchemy database session
        seeded_aliases: Set of alias names already seeded in this session
            (used to avoid querying uncommitted records when autoflush is off)

    Returns:
        Set of alias names that were created as placeholders.
    """
    from solace_agent_mesh.services.platform.models import ModelConfiguration
    from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
    from solace_agent_mesh.services.platform.constants import PLACEHOLDER_VALUE, DEFAULT_MODEL_ALIASES

    if seeded_aliases is None:
        seeded_aliases = set()

    created = set()

    for alias in DEFAULT_MODEL_ALIASES:
        # Skip if already seeded in this session (avoids uncommitted query issue)
        if alias in seeded_aliases:
            log.debug("[Model Seed] Default alias '%s' already seeded this session, skipping", alias)
            continue

        existing = db.query(ModelConfiguration).filter(
            ModelConfiguration.alias == alias
        ).first()

        if existing:
            log.debug("[Model Seed] Default alias '%s' already exists, skipping", alias)
            continue

        model_config = ModelConfiguration(
            id=generate_uuidv7(),
            alias=alias,
            provider=PLACEHOLDER_VALUE,
            model_name=PLACEHOLDER_VALUE,
            api_base=None,
            model_auth_type="none",
            model_auth_config={"type": "none"},
            model_params={},
            description="Default model configuration created by the system",
            created_by="system",
            updated_by="system",
            created_time=now_epoch_ms(),
            updated_time=now_epoch_ms(),
        )
        db.add(model_config)
        created.add(alias)
        log.info("[Model Seed] Created placeholder for default alias '%s'", alias)

    return created


def _seed_from_models_config(db: Session, models_config: dict) -> set:
    """Seed model aliases from models_config dict.

    Returns:
        Set of alias names that were successfully seeded.
    """
    seeded = set()

    if not models_config:
        log.info("[Model Seed] No models_config provided")
        return seeded

    from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
    from solace_agent_mesh.services.platform.models import ModelConfiguration

    for alias, config_data in models_config.items():
        try:
            # Check if already exists before processing
            existing = db.query(ModelConfiguration).filter(
                ModelConfiguration.alias == alias
            ).first()

            if existing:
                log.debug("[Model Seed] Model configuration '%s' already exists, skipping", alias)
                continue

            if isinstance(config_data, dict):
                model_name = config_data.get("model")
                if not model_name:
                    log.debug("[Model Seed] Skipping model '%s' without model_name", alias)
                    continue

                api_base = config_data.get("api_base")
                auth_type, model_auth_config = _extract_auth_type_and_config(config_data)
                model_auth_config["type"] = auth_type
                model_params = _extract_model_params(config_data)
                provider = _infer_provider(api_base, model_name)

            elif isinstance(config_data, str):
                model_name = config_data
                provider = _infer_provider(None, model_name)
                api_base = _get_default_api_base(provider)
                auth_type = "none"
                model_auth_config = {"type": "none"}
                model_params = {}

            else:
                log.debug("[Model Seed] Skipping invalid entry '%s': %s", alias, type(config_data))
                continue

            # Insert model configuration
            model_config = ModelConfiguration(
                id=generate_uuidv7(),
                alias=alias,
                provider=provider,
                model_name=model_name,
                api_base=api_base,
                model_auth_type=auth_type,
                model_auth_config=model_auth_config,
                model_params=model_params,
                description="Model configuration imported by the system",
                created_by="system",
                updated_by="system",
                created_time=now_epoch_ms(),
                updated_time=now_epoch_ms(),
            )
            db.add(model_config)
            seeded.add(alias)
            log.debug("[Model Seed] Seeded model configuration: %s", alias)

        except Exception as e:
            log.error("[Model Seed] Failed to seed model '%s': %s", alias, e, exc_info=True)
            # Continue with next model instead of failing the entire seeding process

    return seeded


def _seed_from_env_vars(db: Session) -> set:
    """Seed model aliases from environment variables.

    Returns:
        Set of alias names that were successfully seeded.
    """
    seeded = set()

    from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
    from solace_agent_mesh.services.platform.models import ModelConfiguration

    # Define env var mappings: (alias, model_env, endpoint_env, key_env)
    env_mappings = [
        ("planning", "LLM_SERVICE_PLANNING_MODEL_NAME", "LLM_SERVICE_ENDPOINT", "LLM_SERVICE_API_KEY"),
        ("general", "LLM_SERVICE_GENERAL_MODEL_NAME", "LLM_SERVICE_ENDPOINT", "LLM_SERVICE_API_KEY"),
        ("image_gen", "IMAGE_MODEL_NAME", "IMAGE_SERVICE_ENDPOINT", "IMAGE_SERVICE_API_KEY"),
        ("report_gen", "LLM_REPORT_MODEL_NAME", "LLM_SERVICE_ENDPOINT", "LLM_SERVICE_API_KEY"),
    ]

    for alias, model_env, endpoint_env, key_env in env_mappings:
        try:
            model_name = os.getenv(model_env, "").strip()
            if not model_name:
                log.debug("[Model Seed] Skipping '%s': %s not set", alias, model_env)
                continue

            api_base = os.getenv(endpoint_env, "").strip()
            api_key = os.getenv(key_env, "").strip()

            # Determine auth type and config
            auth_type = "none"
            model_auth_config = {}
            if api_key:
                auth_type = "apikey"
                model_auth_config = {"api_key": api_key}
            # Add type field to auth config for redaction logic
            model_auth_config["type"] = auth_type

            provider = _infer_provider(api_base, model_name)

            # Insert model configuration
            model_config = ModelConfiguration(
                id=generate_uuidv7(),
                alias=alias,
                provider=provider,
                model_name=model_name,
                api_base=api_base if api_base else None,
                model_auth_type=auth_type,
                model_auth_config=model_auth_config,
                model_params={},
                description="Model configuration imported by the system",
                created_by="system",
                updated_by="system",
                created_time=now_epoch_ms(),
                updated_time=now_epoch_ms(),
            )
            db.add(model_config)
            seeded.add(alias)
            log.info("[Model Seed] Seeded model configuration from env vars: %s", alias)

        except Exception as e:
            log.error("[Model Seed] Failed to seed model '%s' from env vars: %s", alias, e, exc_info=True)
            # Continue with next model instead of failing the entire seeding process

    return seeded
