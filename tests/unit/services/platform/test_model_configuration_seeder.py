"""Unit tests for model configuration seeder.

Tests the provider inference logic to ensure:
- Known provider detection (OpenAI, Anthropic, Azure, Bedrock, Vertex, Google AI Studio)
- OpenAI-compatible provider detection
- Fallback to custom provider

Also tests seeding from YAML config and environment variables.
"""

import os
from unittest.mock import Mock
from solace_agent_mesh.services.platform.services.model_configuration_seeder import (
    _infer_provider,
    _seed_from_models_config,
    _seed_from_env_vars,
)


class TestInferProvider:
    """Tests for provider inference from API base URL."""

    # Known Providers
    def test_known_provider_openai(self):
        """Detect OpenAI from api.openai.com hostname."""
        assert _infer_provider("https://api.openai.com/v1") == "openai"
        assert _infer_provider("https://api.openai.com/v1/chat/completions") == "openai"

    def test_known_provider_anthropic(self):
        """Detect Anthropic from api.anthropic.com hostname."""
        assert _infer_provider("https://api.anthropic.com/v1") == "anthropic"
        assert _infer_provider("https://api.anthropic.com") == "anthropic"

    def test_known_provider_azure_openai(self):
        """Detect Azure OpenAI from *.openai.azure.com hostname."""
        assert _infer_provider("https://my-resource.openai.azure.com/v1") == "azure_openai"
        assert (
            _infer_provider("https://another-azure-instance.openai.azure.com/v1")
            == "azure_openai"
        )

    def test_known_provider_bedrock(self):
        """Detect AWS Bedrock from bedrock in hostname or path."""
        assert _infer_provider("https://bedrock.us-east-1.amazonaws.com/v1") == "bedrock"
        assert _infer_provider("https://bedrock-runtime.us-west-2.amazonaws.com") == "bedrock"

    def test_known_provider_vertex_ai(self):
        """Detect Google Vertex AI from hostname."""
        assert (
            _infer_provider("https://us-central1-aiplatform.googleapis.com/v1")
            == "vertex_ai"
        )
        assert _infer_provider("https://aiplatform.googleapis.com/v1") == "vertex_ai"
        assert (
            _infer_provider("https://vertex.googleapis.com/v1")
            == "vertex_ai"
        )

    def test_known_provider_google_ai_studio(self):
        """Detect Google AI Studio from hostname."""
        assert (
            _infer_provider("https://generativelanguage.googleapis.com/v1")
            == "google_ai_studio"
        )
        assert _infer_provider("https://makersuite.google.com/api") == "google_ai_studio"


    # Custom Provider (Fallback)
    def test_custom_provider_no_url(self):
        """Return custom when no api_base provided."""
        assert _infer_provider("") == "custom"
        assert _infer_provider(None) == "custom"

    def test_custom_provider_generic_url(self):
        """Return custom for generic URLs without known patterns."""
        assert _infer_provider("https://example.com/api") == "custom"
        assert _infer_provider("https://my-llm-service.internal:5000") == "custom"
        assert _infer_provider("https://localhost:8000") == "custom"

    def test_custom_provider_invalid_url(self):
        """Return custom for invalid or unparseable URLs."""
        # Should handle gracefully without raising exceptions
        assert _infer_provider("not-a-valid-url") == "custom"
        assert _infer_provider("::invalid::") == "custom"

    # Case Insensitivity
    def test_case_insensitive_hostname_matching(self):
        """Test that hostname matching is case-insensitive."""
        assert _infer_provider("https://API.OPENAI.COM/v1") == "openai"
        assert (
            _infer_provider("https://API.ANTHROPIC.COM/v1")
            == "anthropic"
        )

    # Edge Cases
    def test_bedrock_in_path(self):
        """Detect Bedrock from path when not in hostname prefix."""
        assert (
            _infer_provider(
                "https://my-service.amazonaws.com/bedrock/models",
                model_name="claude-3"
            )
            == "bedrock"
        )

    def test_no_api_base_with_model_name(self):
        """Handle missing api_base but infer provider from model name."""
        # Gemini models are detected as Google AI Studio
        assert _infer_provider("", model_name="gemini-2.5-flash") == "google_ai_studio"
        # Custom-prefixed models are detected as custom
        assert (
            _infer_provider(
                None,
                model_name="openai/gpt-4"
            )
            == "custom"
        )
        # GPT models are detected as OpenAI
        assert _infer_provider("", model_name="gpt-4") == "openai"
        # Claude models are detected as Anthropic
        assert _infer_provider("", model_name="claude-3-opus") == "anthropic"
        # Unknown models default to custom
        assert _infer_provider("", model_name="my-custom-model") == "custom"


class TestSeedFromModelsConfig:
    """Tests for seeding model configurations from YAML config dict."""

    def test_seed_from_yaml_config(self):
        """Seed models from YAML config covering known, compatible, and custom providers."""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        models_config = {
            "gpt-4": {
                "model": "gpt-4",
                "api_base": "https://api.openai.com/v1",
                "api_key": "sk-test-key",
            },
            "local-llm": {
                "model": "llama-2-7b",
                "api_base": "https://localhost:8000/v1/",
                "temperature": 0.7,
            },
            "my-api": {
                "model": "custom-model-v1",
                "api_base": "https://my-service.internal/api",
                "max_tokens": 2048,
            },
        }

        count = _seed_from_models_config(mock_db, models_config)

        assert count == 3
        assert mock_db.add.call_count == 3
        # Note: Transaction ownership is with the caller (component startup)
        # The seeding function only adds models, caller is responsible for commit

        # Verify each model type was seeded correctly
        added_models = [call[0][0] for call in mock_db.add.call_args_list]

        # Known provider (OpenAI)
        gpt4 = next(m for m in added_models if m.alias == "gpt-4")
        assert gpt4.provider == "openai"
        assert gpt4.model_auth_type == "apikey"
        assert gpt4.description  # Verify description is set (not null/empty)

        # Custom provider (local LLM with /v1/ path)
        local = next(m for m in added_models if m.alias == "local-llm")
        assert local.provider == "custom"
        assert local.model_params == {"temperature": 0.7}
        assert local.description  # Verify description is set (not null/empty)

        # Custom provider
        custom = next(m for m in added_models if m.alias == "my-api")
        assert custom.provider == "custom"
        assert custom.model_params == {"max_tokens": 2048}
        assert custom.description  # Verify description is set (not null/empty)

    def test_seed_from_yaml_config_with_string_entries(self):
        """Seed models from YAML config with simple string model names."""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        models_config = {
            "multimodal": "gemini-2.5-flash",
            "gemini_pro": "gemini-2.5-pro",
            "gpt4": {
                "model": "gpt-4",
                "api_base": "https://api.openai.com/v1",
            },
        }

        count = _seed_from_models_config(mock_db, models_config)

        assert count == 3
        assert mock_db.add.call_count == 3
        # Note: Transaction ownership is with the caller (component startup)
        # The seeding function only adds models, caller is responsible for commit

        added_models = [call[0][0] for call in mock_db.add.call_args_list]

        # String entry - infers Google AI Studio provider
        multimodal = next(m for m in added_models if m.alias == "multimodal")
        assert multimodal.model_name == "gemini-2.5-flash"
        assert multimodal.provider == "google_ai_studio"
        assert multimodal.api_base == "https://generativelanguage.googleapis.com/v1"
        assert multimodal.model_auth_type == "none"
        assert multimodal.model_auth_config == {"type": "none"}
        assert multimodal.model_params == {}
        assert multimodal.description  # Verify description is set (not null/empty)

        # Another string entry
        gemini_pro = next(m for m in added_models if m.alias == "gemini_pro")
        assert gemini_pro.model_name == "gemini-2.5-pro"
        assert gemini_pro.provider == "google_ai_studio"
        assert gemini_pro.api_base == "https://generativelanguage.googleapis.com/v1"
        assert gemini_pro.description  # Verify description is set (not null/empty)

        # Dictionary entry still works
        gpt4_model = next(m for m in added_models if m.alias == "gpt4")
        assert gpt4_model.provider == "openai"
        assert gpt4_model.description  # Verify description is set (not null/empty)


class TestSeedFromEnvVars:
    """Tests for seeding model configurations from environment variables."""

    def test_seed_from_environment_variables(self):
        """Seed models from environment variables."""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Set env vars for multiple models (some complete, some partial)
        os.environ["LLM_SERVICE_PLANNING_MODEL_NAME"] = "gpt-4"
        os.environ["LLM_SERVICE_ENDPOINT"] = "https://api.openai.com/v1"
        os.environ["LLM_SERVICE_API_KEY"] = "sk-planning-key"

        os.environ["LLM_SERVICE_GENERAL_MODEL_NAME"] = "gpt-3.5-turbo"
        os.environ["IMAGE_MODEL_NAME"] = "dall-e-3"
        os.environ["IMAGE_SERVICE_ENDPOINT"] = "https://api.openai.com/v1"
        os.environ["IMAGE_SERVICE_API_KEY"] = "sk-image-key"

        os.environ["LLM_REPORT_MODEL_NAME"] = "gpt-4-turbo"

        try:
            count = _seed_from_env_vars(mock_db)

            # Should seed 4 models (planning, general, image_gen, report_gen)
            assert count == 4
            assert mock_db.add.call_count == 4
            # Note: Transaction ownership is with the caller (component startup)
        # The seeding function only adds models, caller is responsible for commit

            added_models = [call[0][0] for call in mock_db.add.call_args_list]

            # Verify models were seeded with correct data
            planning = next(m for m in added_models if m.alias == "planning")
            assert planning.model_name == "gpt-4"
            assert planning.model_auth_type == "apikey"
            assert planning.model_auth_config["api_key"] == "sk-planning-key"
            assert planning.description  # Verify description is set (not null/empty)

            general = next(m for m in added_models if m.alias == "general")
            assert general.model_name == "gpt-3.5-turbo"
            assert general.description  # Verify description is set (not null/empty)

            image = next(m for m in added_models if m.alias == "image_gen")
            assert image.model_name == "dall-e-3"
            assert image.description  # Verify description is set (not null/empty)

            report = next(m for m in added_models if m.alias == "report_gen")
            assert report.model_name == "gpt-4-turbo"
            assert report.description  # Verify description is set (not null/empty)
        finally:
            # Clean up env vars
            for key in [
                "LLM_SERVICE_PLANNING_MODEL_NAME",
                "LLM_SERVICE_ENDPOINT",
                "LLM_SERVICE_API_KEY",
                "LLM_SERVICE_GENERAL_MODEL_NAME",
                "IMAGE_MODEL_NAME",
                "IMAGE_SERVICE_ENDPOINT",
                "IMAGE_SERVICE_API_KEY",
                "LLM_REPORT_MODEL_NAME",
            ]:
                os.environ.pop(key, None)
