"""
Unit tests for TitleGenerationService.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from solace_agent_mesh.gateway.http_sse.services.title_generation_service import (
    TitleGenerationService,
)
from solace_agent_mesh.gateway.http_sse.services.title_generation_constants import (
    TITLE_CHAR_LIMIT,
)


class TestTitleGenerationService:
    """Tests for TitleGenerationService."""

    def test_init_with_model_config(self):
        """Test initialization with basic model config."""
        model_config = {
            "model": "gpt-4",
            "api_base": "https://api.openai.com/v1",
            "api_key": "test-key",
        }
        service = TitleGenerationService(model_config=model_config)
        
        assert service.model == "gpt-4"
        assert service.api_base == "https://api.openai.com/v1"
        assert service.api_key == "test-key"

    def test_init_with_title_specific_model(self):
        """Test initialization with title-specific model override."""
        model_config = {
            "model": "gpt-4",
            "llm_service_title_model_name": "gpt-3.5-turbo",
        }
        service = TitleGenerationService(model_config=model_config)
        
        assert service.model == "gpt-3.5-turbo"

    def test_truncate_text(self):
        """Test text truncation."""
        service = TitleGenerationService(model_config={"model": "test"})
        
        assert service._truncate_text("Hello", 50) == "Hello"
        assert service._truncate_text("A" * 100, 50) == "A" * 50 + "..."
        assert service._truncate_text("", 50) == ""
        assert service._truncate_text(None, 50) == ""

    def test_fallback_title(self):
        """Test fallback title generation."""
        service = TitleGenerationService(model_config={"model": "test"})
        
        assert service._fallback_title("Hello") == "Hello"
        assert service._fallback_title("A" * 100) == "A" * TITLE_CHAR_LIMIT + "..."
        assert service._fallback_title("") == "New Chat"
        assert service._fallback_title(None) == "New Chat"

    @pytest.mark.asyncio
    async def test_call_litellm_success(self):
        """Test successful LiteLLM call."""
        service = TitleGenerationService(model_config={
            "model": "gpt-4",
            "api_key": "test-key",
        })
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test Title"
        
        with patch("solace_agent_mesh.gateway.http_sse.services.title_generation_service.acompletion", 
                   new_callable=AsyncMock, return_value=mock_response):
            result = await service._call_litellm("Hello", "Hi there!")
            
        assert result == "Test Title"

    @pytest.mark.asyncio
    async def test_call_litellm_strips_quotes(self):
        """Test LiteLLM strips quotes from title."""
        service = TitleGenerationService(model_config={"model": "gpt-4"})
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '"Test Title"'
        
        with patch("solace_agent_mesh.gateway.http_sse.services.title_generation_service.acompletion", 
                   new_callable=AsyncMock, return_value=mock_response):
            result = await service._call_litellm("Hello", "Hi")
            
        assert result == "Test Title"

    @pytest.mark.asyncio
    async def test_call_litellm_fallback_on_error(self):
        """Test LiteLLM uses fallback on error."""
        service = TitleGenerationService(model_config={"model": "gpt-4"})
        
        with patch("solace_agent_mesh.gateway.http_sse.services.title_generation_service.acompletion", 
                   new_callable=AsyncMock, side_effect=Exception("API Error")):
            result = await service._call_litellm("Hello world", "Hi")
            
        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_generate_and_update_title_success(self):
        """Test successful title generation and update."""
        service = TitleGenerationService(model_config={"model": "gpt-4"})
        mock_callback = AsyncMock()
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated Title"
        
        with patch("solace_agent_mesh.gateway.http_sse.services.title_generation_service.acompletion", 
                   new_callable=AsyncMock, return_value=mock_response):
            await service._generate_and_update_title(
                session_id="test-session",
                user_message="Hello",
                agent_response="Hi there!",
                update_callback=mock_callback,
            )
        
        mock_callback.assert_called_once_with("Generated Title")

    @pytest.mark.asyncio
    async def test_generate_title_async(self):
        """Test async title generation creates background task."""
        service = TitleGenerationService(model_config={"model": "gpt-4"})
        mock_callback = AsyncMock()
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated Title"
        
        with patch("solace_agent_mesh.gateway.http_sse.services.title_generation_service.acompletion", 
                   new_callable=AsyncMock, return_value=mock_response):
            await service.generate_title_async(
                session_id="test-session",
                user_message="Hello",
                agent_response="Hi there!",
                user_id="test-user",
                update_callback=mock_callback,
            )
            await asyncio.sleep(0.1)
        
        mock_callback.assert_called_once_with("Generated Title")
