"""
Service for managing supported LLM models per provider.
This service uses the LiteLLM library to fetch available models for each provider.
For dynamic providers like OpenAI-compatible, the platform service acts as a proxy
to fetch available models at runtime via the provider's API.
"""
import logging
import re
from typing import List, Dict, Optional
import httpx

try:
    import litellm
except ImportError:
    litellm = None

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
    """Service for managing supported LLM models using LiteLLM."""

    def get_all_models(self) -> List[Dict[str, str]]:
        """
        Get all supported models for our known providers only.
        Returns models from these providers only:
        - OpenAI, Anthropic, Google AI Studio, Vertex AI, Azure OpenAI, Bedrock, Ollama
        Returns:
            List of supported models with id, label, and provider.
        """
        if not litellm:
            log.warning("LiteLLM not available, returning empty model list")
            return []

        try:
            models = []

            # Our known providers
            known_providers = [
                ModelProviders.OPENAI,
                ModelProviders.ANTHROPIC,
                ModelProviders.GOOGLE_AI_STUDIO,
                ModelProviders.VERTEX_AI,
                ModelProviders.AZURE_OPENAI,
                ModelProviders.BEDROCK,
                ModelProviders.OLLAMA,
            ]

            # Fetch models for each known provider
            for provider in known_providers:
                provider_models = self.get_models_by_provider(provider)
                models.extend(provider_models)

            log.info(f"Fetched {len(models)} models from {len(known_providers)} known providers")
            return models
        except Exception as e:
            log.error(f"Error fetching models from LiteLLM: {e}")
            return []

    def get_models_by_provider(self, provider: str) -> List[Dict[str, str]]:
        """
        Get supported models for a specific provider.
        Uses litellm.models_by_provider which organizes models by provider type.
        Args:
            provider: Provider type (e.g., "openai", "anthropic")
        Returns:
            List of supported models for the provider with id, label, and provider.
        """
        if not litellm:
            log.warning("LiteLLM not available, returning empty model list")
            return []

        try:
            # Map our provider names to LiteLLM provider keys
            litellm_provider = self._map_provider_to_litellm_key(provider)

            # Get models for this provider from litellm.models_by_provider
            models_by_provider = litellm.models_by_provider
            provider_models = models_by_provider.get(litellm_provider, [])

            # Convert to list of dicts with id, label, and provider
            filtered_models = []
            for model in provider_models:
                filtered_models.append({
                    "id": model,
                    "label": self._format_model_label(model),
                    "provider": provider
                })

            log.info(f"Fetched {len(filtered_models)} models for provider {provider}")
            return filtered_models
        except Exception as e:
            log.error(f"Error fetching models for provider {provider}: {e}")
            return []

    def _map_provider_to_litellm_key(self, provider: str) -> str:
        """
        Map our provider names to LiteLLM's provider keys.
        Args:
            provider: Our provider type
        Returns:
            LiteLLM provider key (e.g., "openai", "anthropic")
        """
        mapping = {
            ModelProviders.OPENAI: "openai",
            ModelProviders.ANTHROPIC: "anthropic",
            ModelProviders.GOOGLE_AI_STUDIO: "gemini",
            ModelProviders.VERTEX_AI: "vertex_ai",
            ModelProviders.AZURE_OPENAI: "azure",
            ModelProviders.BEDROCK: "bedrock",
            ModelProviders.OLLAMA: "ollama",
        }
        return mapping.get(provider, provider)

    def _format_model_label(self, model: str) -> str:
        """
        Format a model ID into a human-readable label.
        Preserves variant information (quality, resolution, dates) to avoid duplicates.
        Args:
            model: Model ID (e.g., "gpt-4", "medium/1024-x-1536/gpt-image-1.5-2025-12-16")
        Returns:
            Formatted label (e.g., "GPT-4", "GPT-image-1.5 (Medium, 1024x1536)")
        """
        original_model = model
        variant_info = []

        # Extract quality/resolution prefix (e.g., "low/", "medium/", "high/", "hd/", "standard/")
        quality_prefixes = ["low", "medium", "high", "hd", "standard"]
        for prefix in quality_prefixes:
            if model.startswith(f"{prefix}/"):
                variant_info.append(prefix.title())
                model = model[len(prefix) + 1:]
                break

        # Extract resolution dimensions if present (e.g., "1024-x-1536/")
        resolution_match = re.match(r"(\d+)[_-]x[_-](\d+)/", model)
        if resolution_match:
            width, height = resolution_match.groups()
            variant_info.append(f"{width}x{height}")
            model = model[resolution_match.end():]

        # Handle models with provider prefixes (e.g., "openai/gpt-4")
        if "/" in model:
            parts = model.split("/")
            model = parts[-1]

        # Handle AWS/Bedrock provider prefixes (e.g., "us.anthropic.claude-3-haiku...")
        if "." in model and not model[0].isalpha():
            # Looks like an AWS ARN, skip the provider prefix
            pass
        elif "." in model:
            # Model ID like "eu.anthropic.claude-3-haiku-..."
            # Extract the part after the last dot if it looks like a model name
            parts = model.split(".")
            for part in reversed(parts):
                if any(keyword in part.lower() for keyword in ["claude", "gpt", "gemini", "llama", "mistral"]):
                    model = part
                    break

        # Extract version/date suffix before removing it (preserves distinction)
        # e.g., "gpt-image-1.5-2025-12-16" → keep "2025-12-16" as variant
        version_date = None
        date_match = re.search(r"-(\d{4}-\d{2}-\d{2})$", model)
        if date_match:
            version_date = date_match.group(1)
            variant_info.append(f"v{version_date}")

        # Remove AWS/Bedrock ARN-like suffixes (e.g., ":0")
        if ":" in model:
            model = model.split(":")[0]

        # Common model name patterns - apply specific formatting
        if model.startswith("gpt-"):
            label = "GPT-" + model[4:]
        elif model.startswith("claude-"):
            label = "Claude " + model[7:].replace("-", " ").title()
        elif model.startswith("gemini-"):
            label = "Gemini " + model[7:].replace("-", " ").title()
        elif model.startswith("mistral-"):
            label = "Mistral " + model[8:].replace("-", " ").title()
        elif model.lower().startswith("llama"):
            rest = model[5:].lstrip("-_")
            label = "Llama " + rest.replace("-", " ").replace("_", " ").title()
        else:
            # Generic formatting for other models
            label = model.replace("-", " ").replace("_", " ").title()

        # Append variant information to avoid duplicates
        if variant_info:
            label += f" ({', '.join(variant_info)})"

        return label.strip()

    def is_dynamic_provider(self, provider: str) -> bool:
        """
        Check if a provider requires dynamic model fetching.
        Some providers like OpenAI-compatible need API credentials and base URL
        to fetch available models at runtime.
        Args:
            provider: Provider type
        Returns:
            True if provider requires dynamic model fetching, False if static list is used.
        """
        return provider in [ModelProviders.OPENAI_COMPATIBLE, ModelProviders.CUSTOM]

    def get_models_by_provider_with_config(
        self,
        provider: str,
        api_base: Optional[str],
        auth_type: str,
        auth_config: Dict[str, any],
    ) -> List[Dict[str, str]]:
        """
        Fetch models from an OpenAI-compatible provider using stored credentials.
        Acts as a proxy to fetch models securely server-to-server.

        Args:
            provider: Provider type (should be "openai_compatible")
            api_base: API base URL for the provider
            auth_type: Authentication type ("apikey", "oauth2", or "none")
            auth_config: Authentication configuration dict

        Returns:
            List of models with id, label, and provider
        """
        if provider != ModelProviders.OPENAI_COMPATIBLE:
            log.warning(f"get_models_by_provider_with_config called with non-openai_compatible provider: {provider}")
            return []

        if not api_base:
            log.warning("API base URL required for openai_compatible provider")
            return []

        try:
            # Normalize the base URL
            base_url = api_base.rstrip("/")

            # Prepare headers based on auth type
            headers = {"Content-Type": "application/json"}

            if auth_type == "apikey" and auth_config:
                api_key = auth_config.get("api_key") or auth_config.get("apiKey")
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

            # Make request to the models endpoint
            with httpx.Client() as client:
                response = client.get(
                    f"{base_url}/v1/models",
                    headers=headers,
                    timeout=10.0,
                )

                if not response.is_success:
                    log.error(f"Failed to fetch models from {api_base}: {response.status_code}")
                    return []

                data = response.json()

                # Handle different response formats
                models = []
                if isinstance(data, dict):
                    if "data" in data and isinstance(data["data"], list):
                        models = [m.get("id") for m in data["data"] if m.get("id")]
                    elif "models" in data and isinstance(data["models"], list):
                        models = [m.get("id") or m.get("name") for m in data["models"] if m.get("id") or m.get("name")]
                elif isinstance(data, list):
                    models = [m.get("id") or m.get("name") for m in data if m.get("id") or m.get("name")]

                # Convert to response format
                result = []
                for model_id in models:
                    if model_id:
                        result.append({
                            "id": model_id,
                            "label": self._format_model_label(model_id),
                            "provider": provider,
                        })

                log.info(f"Fetched {len(result)} models from {api_base}")
                return result

        except httpx.RequestError as e:
            log.error(f"Network error fetching models from {api_base}: {e}")
            return []
        except Exception as e:
            log.error(f"Error fetching models from {api_base}: {e}")
            return []