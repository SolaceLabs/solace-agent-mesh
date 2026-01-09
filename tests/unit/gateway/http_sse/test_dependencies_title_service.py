"""
Unit tests for get_title_generation_service dependency.
"""
import pytest
from unittest.mock import MagicMock

from solace_agent_mesh.gateway.http_sse.dependencies import get_title_generation_service


class TestGetTitleGenerationService:
    """Tests for get_title_generation_service dependency."""

    def test_creates_service_with_model_config(self):
        """Test that service is created with model config from component."""
        mock_component = MagicMock()
        mock_component.get_config.return_value = {
            "model": "gpt-4",
            "api_base": "https://api.openai.com/v1",
            "api_key": "test-key",
        }
        
        service = get_title_generation_service(component=mock_component)
        
        mock_component.get_config.assert_called_once_with("model", {})
        assert service.model == "gpt-4"
        assert service.api_base == "https://api.openai.com/v1"
        assert service.api_key == "test-key"

    def test_creates_service_with_empty_config(self):
        """Test that service is created even with empty config."""
        mock_component = MagicMock()
        mock_component.get_config.return_value = {}
        
        service = get_title_generation_service(component=mock_component)
        
        assert service.model is None
        assert service.api_key == "dummy"
