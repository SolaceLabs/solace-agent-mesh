"""
Unit tests for get_title_generation_service dependency.
"""
import pytest
from unittest.mock import MagicMock, patch

from solace_agent_mesh.gateway.http_sse.dependencies import get_title_generation_service


class TestGetTitleGenerationService:
    """Tests for get_title_generation_service dependency."""

    def test_creates_service_with_llm_from_component(self):
        """Test that service is created with llm from component.get_lite_llm_model()."""
        mock_llm = MagicMock()
        mock_component = MagicMock()
        mock_component.get_config.return_value = {"model": "gpt-4"}
        mock_component.get_lite_llm_model.return_value = mock_llm

        service = get_title_generation_service(component=mock_component)

        mock_component.get_config.assert_called_once_with("model", {})
        mock_component.get_lite_llm_model.assert_called_once()
        assert service.llm is mock_llm

    def test_passes_model_config_with_title_model(self):
        """Test that model_config with title model override creates a title-specific LiteLlm."""
        mock_llm = MagicMock()
        model_config = {
            "api_key": "test-key",
            "llm_service_title_model_name": "gpt-3.5-turbo",
        }
        mock_component = MagicMock()
        mock_component.get_config.return_value = model_config
        mock_component.get_lite_llm_model.return_value = mock_llm

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.title_generation_service.LiteLlm"
        ) as MockLiteLlm:
            title_llm = MagicMock()
            MockLiteLlm.return_value = title_llm
            service = get_title_generation_service(component=mock_component)

            # A new LiteLlm should be created for the title-specific model
            MockLiteLlm.assert_called_once_with(model="gpt-3.5-turbo", **model_config)
            assert service.llm is title_llm

    def test_creates_service_with_empty_config(self):
        """Test that service is created even with empty config."""
        mock_llm = MagicMock()
        mock_component = MagicMock()
        mock_component.get_config.return_value = {}
        mock_component.get_lite_llm_model.return_value = mock_llm

        service = get_title_generation_service(component=mock_component)

        assert service.llm is mock_llm
