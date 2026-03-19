"""
Service for managing supported LLM models per provider.
Queries provider APIs directly to fetch available models at runtime.
Supports both stored credentials (from database) and request-provided credentials.
"""
import logging
from typing import List, Dict, Optional
import httpx

log = logging.getLogger(__name__)


# Provider ID constants
class ModelProviders:
    """Provider ID constants."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE_AI_STUDIO = "google_ai_studio"
    VERTEX_AI = "vertex_ai"
    AZURE_OPENAI = "azure_openai"
    BEDROCK = "bedrock"
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"
    CUSTOM = "custom"


class ModelListService:
    """Service for managing supported LLM models by querying provider APIs directly."""

    def get_models_by_provider_with_config(
        self,
        provider: str,
        api_base: Optional[str],
        auth_type: str,
        auth_config: Dict[str, any],
    ) -> List[Dict[str, str]]:
        """
        Fetch models from a provider by querying their API directly.
        Supports all provider types with appropriate authentication headers.

        Args:
            provider: Provider type (e.g., 'openai', 'anthropic', 'openai_compatible')
            api_base: API base URL (required for openai_compatible, optional for others)
            auth_type: Authentication type ('apikey', 'oauth2', or 'none')
            auth_config: Authentication configuration dict with provider-specific credentials

        Returns:
            List of models with id, label, and provider

        Raises:
            RuntimeError: Provider API errors, authentication errors, network issues
        """
        # Determine the API base URL and extract credentials
        if not api_base:
            api_base = self._get_provider_api_base(provider)

        try:
            # Set up headers with authentication
            headers = self._build_auth_headers(provider, auth_type, auth_config)

            # Make the API call to fetch models
            models_response = self._fetch_models_from_provider(provider, api_base, headers, auth_type, auth_config)

            # Convert to our format
            models = []
            for model_id in models_response:
                models.append({
                    "id": model_id,
                    "label": model_id,
                    "provider": provider,
                })

            log.info(f"Fetched {len(models)} models from {provider}")
            return models

        except Exception as e:
            log.error(f"Failed to fetch models from {provider}: {str(e)}", exc_info=True)
            raise RuntimeError(f"Failed to fetch models from {provider}: {str(e)}")

    def _get_provider_api_base(self, provider: str) -> str:
        """Get the default API base URL for a provider."""
        api_bases = {
            ModelProviders.OPENAI: "https://api.openai.com/v1",
            ModelProviders.ANTHROPIC: "https://api.anthropic.com",
            ModelProviders.GOOGLE_AI_STUDIO: "https://generativelanguage.googleapis.com/v1beta/models",
            ModelProviders.AZURE_OPENAI: None,  # Requires custom api_base
            ModelProviders.OLLAMA: "http://localhost:11434/api",
        }
        return api_bases.get(provider)

    def _build_auth_headers(self, provider: str, auth_type: str, auth_config: Dict) -> Dict[str, str]:
        """Build HTTP headers with authentication and provider-specific requirements."""
        headers = {}

        if auth_type == "apikey":
            api_key = auth_config.get("api_key")
            if api_key:
                # Provider-specific header formats
                if provider == ModelProviders.ANTHROPIC:
                    headers["X-API-Key"] = api_key
                elif provider != ModelProviders.GOOGLE_AI_STUDIO:
                    # Google AI Studio uses query params, not headers
                    # OpenAI, Azure, Ollama, etc. use Bearer token
                    headers["Authorization"] = f"Bearer {api_key}"

        # Add provider-specific headers
        if provider == ModelProviders.ANTHROPIC:
            headers["anthropic-version"] = "2023-06-01"

        return headers

    def _fetch_models_from_provider(self, provider: str, api_base: str, headers: Dict, auth_type: str, auth_config: Dict) -> List[str]:
        """
        Fetch the list of models from the provider's API.

        Args:
            provider: Provider type
            api_base: API base URL
            headers: Authentication headers
            auth_type: Authentication type
            auth_config: Authentication configuration

        Returns:
            List of model IDs

        Raises:
            RuntimeError: If API call fails
        """
        if not api_base:
            raise RuntimeError(f"API base URL not configured for provider {provider}")

        # Build endpoint URL and prepare query params based on provider
        query_params = {}
        if provider == ModelProviders.OPENAI or provider == ModelProviders.OPENAI_COMPATIBLE:
            endpoint = f"{api_base}/models"
        elif provider == ModelProviders.ANTHROPIC:
            endpoint = f"{api_base}/v1/models"
        elif provider == ModelProviders.GOOGLE_AI_STUDIO:
            # Google AI Studio endpoint - api_key goes in query params
            endpoint = f"{api_base}"
            if auth_type == "apikey":
                api_key = auth_config.get("api_key")
                if api_key:
                    query_params["key"] = api_key
                else:
                    raise RuntimeError("API key required for Google AI Studio")
        elif provider == ModelProviders.OLLAMA:
            endpoint = f"{api_base}/tags"
        else:
            raise RuntimeError(f"Unsupported provider for model listing: {provider}")

        try:
            with httpx.Client() as client:
                response = client.get(endpoint, headers=headers, params=query_params, timeout=10.0)
                response.raise_for_status()

                # Parse response based on provider format
                if provider == ModelProviders.OPENAI or provider == ModelProviders.OPENAI_COMPATIBLE:
                    data = response.json()
                    return [model["id"] for model in data.get("data", [])]

                elif provider == ModelProviders.ANTHROPIC:
                    data = response.json()
                    # Anthropic returns models under "data" key
                    models = []
                    for item in data.get("data", []):
                        if item.get("type") == "model":
                            models.append(item["id"])
                    return models

                elif provider == ModelProviders.GOOGLE_AI_STUDIO:
                    data = response.json()
                    # Google returns models in "models" array
                    models = []
                    for model in data.get("models", []):
                        model_id = model.get("name", "")
                        # Model name is like "models/gemini-pro", extract the model name part
                        if "/" in model_id:
                            model_id = model_id.split("/")[-1]
                        if model_id:
                            models.append(model_id)
                    return models

                elif provider == ModelProviders.OLLAMA:
                    data = response.json()
                    return [model["name"].split(":")[0] for model in data.get("models", [])]

        except httpx.HTTPError as e:
            raise RuntimeError(f"HTTP error fetching models from {provider}: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error fetching models from {provider}: {str(e)}")
