"""Integration tests for OAuth LLM authentication."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.adk.models.llm_request import LlmRequest

from solace_agent_mesh.agent.adk.models.lite_llm import LiteLlm
from solace_agent_mesh.common.utils.in_memory_cache import InMemoryCache


@pytest.fixture
def oauth_config():
    """OAuth configuration for testing."""
    return {
        "model": "test-model",
        "api_base": "https://api.example.com/v1",
        "oauth_token_url": "https://auth.example.com/oauth/token",
        "oauth_client_id": "test_client_id",
        "oauth_client_secret": "test_client_secret",
        "oauth_scope": "llm.read llm.write",
        "oauth_token_refresh_buffer_seconds": 300,
    }


@pytest.fixture
def api_key_config():
    """API key configuration for testing."""
    return {
        "model": "test-model",
        "api_base": "https://api.example.com/v1",
        "api_key": "test_api_key_12345",
    }


@pytest.fixture
def mock_token_response():
    """Mock OAuth token response."""
    return {
        "access_token": "oauth_access_token_12345",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "llm.read llm.write",
    }


@pytest.fixture
def sample_llm_request():
    """Sample LLM request for testing."""
    from google.genai.types import Content, Part

    content = Content(
        role="user",
        parts=[Part(text="Hello, how are you?")]
    )
    return LlmRequest(contents=[content])


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the cache before each test to ensure clean state."""
    cache = InMemoryCache()
    cache.clear()
    yield
    cache.clear()


class TestOAuthLLMIntegration:
    """Integration tests for OAuth LLM authentication."""

    def test_litellm_oauth_initialization(self, oauth_config):
        """Test that LiteLlm properly initializes with OAuth configuration."""
        llm = LiteLlm(**oauth_config)
        
        # Verify OAuth token manager was created
        assert llm._oauth_token_manager is not None
        assert llm._oauth_token_manager.token_url == "https://auth.example.com/oauth/token"
        assert llm._oauth_token_manager.client_id == "test_client_id"
        assert llm._oauth_token_manager.client_secret == "test_client_secret"
        assert llm._oauth_token_manager.scope == "llm.read llm.write"
        
        # Verify OAuth parameters were removed from additional_args
        assert "oauth_token_url" not in llm._additional_args
        assert "oauth_client_id" not in llm._additional_args
        assert "oauth_client_secret" not in llm._additional_args

    def test_litellm_api_key_initialization(self, api_key_config):
        """Test that LiteLlm works normally with API key configuration."""
        llm = LiteLlm(**api_key_config)
        
        # Verify no OAuth token manager was created
        assert llm._oauth_token_manager is None
        
        # Verify API key is preserved
        assert llm._additional_args["api_key"] == "test_api_key_12345"

    @pytest.mark.asyncio
    async def test_oauth_token_injection_in_requests(
        self, oauth_config, mock_token_response, sample_llm_request
    ):
        """Test that OAuth tokens are properly injected into LLM requests."""
        llm = LiteLlm(**oauth_config)

        with patch("solace_agent_mesh.common.oauth.oauth_client.httpx.AsyncClient") as mock_oauth_client, \
             patch.object(llm.llm_client, "acompletion") as mock_completion:

            # Mock OAuth token response
            mock_oauth_response = MagicMock()
            mock_oauth_response.status_code = 200
            mock_oauth_response.json.return_value = mock_token_response
            mock_oauth_response.raise_for_status.return_value = None

            mock_oauth_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_oauth_response
            )

            # Mock LLM completion response
            mock_completion.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": "Hello! How can I help you today?",
                            "role": "assistant"
                        }
                    }
                ]
            }

            # Make LLM request
            async for response in llm.generate_content_async(sample_llm_request):
                break  # Just need to trigger the request

            # Verify OAuth token was injected
            mock_completion.assert_called_once()
            call_args = mock_completion.call_args[1]

            assert "extra_headers" in call_args
            assert "Authorization" in call_args["extra_headers"]
            assert call_args["extra_headers"]["Authorization"] == "Bearer oauth_access_token_12345"

    @pytest.mark.asyncio
    async def test_fallback_to_api_key_on_oauth_failure(
        self, sample_llm_request
    ):
        """Test graceful fallback to API key when OAuth fails."""
        # Configuration with both OAuth and API key
        config = {
            "model": "test-model",
            "api_base": "https://api.example.com/v1",
            "api_key": "fallback_api_key_12345",
            "oauth_token_url": "https://auth.example.com/oauth/token",
            "oauth_client_id": "test_client_id",
            "oauth_client_secret": "test_client_secret",
        }

        llm = LiteLlm(**config)

        with patch("solace_agent_mesh.common.oauth.oauth_client.httpx.AsyncClient") as mock_oauth_client, \
             patch.object(llm.llm_client, "acompletion") as mock_completion:

            # Mock OAuth failure
            mock_oauth_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("OAuth server unavailable")
            )

            # Mock LLM completion response
            mock_completion.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": "Hello! How can I help you today?",
                            "role": "assistant"
                        }
                    }
                ]
            }

            # Make LLM request - should fallback to API key
            async for response in llm.generate_content_async(sample_llm_request):
                break

            # Verify LLM was still called (with API key fallback)
            mock_completion.assert_called_once()
            call_args = mock_completion.call_args[1]

            # Should have API key but no OAuth Authorization header
            assert call_args.get("api_key") == "fallback_api_key_12345"
            extra_headers = call_args.get("extra_headers", {})
            assert "Authorization" not in extra_headers

    @pytest.mark.asyncio
    async def test_multiple_llm_requests_with_token_reuse(
        self, oauth_config, mock_token_response, sample_llm_request
    ):
        """Test that multiple LLM requests reuse cached OAuth tokens."""
        llm = LiteLlm(**oauth_config)

        with patch("solace_agent_mesh.common.oauth.oauth_client.httpx.AsyncClient") as mock_oauth_client, \
             patch.object(llm.llm_client, "acompletion") as mock_completion:

            # Mock OAuth token response
            mock_oauth_response = MagicMock()
            mock_oauth_response.status_code = 200
            mock_oauth_response.json.return_value = mock_token_response
            mock_oauth_response.raise_for_status.return_value = None

            mock_oauth_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_oauth_response
            )

            # Mock LLM completion response
            mock_completion.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": "Hello! How can I help you today?",
                            "role": "assistant"
                        }
                    }
                ]
            }

            # Make multiple LLM requests
            for i in range(3):
                async for response in llm.generate_content_async(sample_llm_request):
                    break

            # Verify OAuth token was fetched only once (cached for subsequent requests)
            assert mock_oauth_client.return_value.__aenter__.return_value.post.call_count == 1

            # Verify all LLM requests were made with the same token
            assert mock_completion.call_count == 3
            for call in mock_completion.call_args_list:
                call_args = call[1]
                assert call_args["extra_headers"]["Authorization"] == "Bearer oauth_access_token_12345"

    @pytest.mark.asyncio
    async def test_oauth_error_handling_without_fallback(
        self, sample_llm_request
    ):
        """Test error handling when OAuth fails and no API key fallback is available."""
        config = {
            "model": "test-model",
            "api_base": "https://api.example.com/v1",
            "oauth_token_url": "https://auth.example.com/oauth/token",
            "oauth_client_id": "test_client_id",
            "oauth_client_secret": "test_client_secret",
        }

        llm = LiteLlm(**config)

        with patch("solace_agent_mesh.common.oauth.oauth_client.httpx.AsyncClient") as mock_oauth_client:
            # Mock OAuth failure
            mock_oauth_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("OAuth server unavailable")
            )

            # Should raise exception when OAuth fails and no fallback
            with pytest.raises(Exception):
                async for response in llm.generate_content_async(sample_llm_request):
                    break

    def test_incomplete_oauth_configuration(self):
        """Test handling of incomplete OAuth configuration."""
        # Missing client_secret
        incomplete_config = {
            "model": "test-model",
            "api_base": "https://api.example.com/v1",
            "oauth_token_url": "https://auth.example.com/oauth/token",
            "oauth_client_id": "test_client_id",
            # oauth_client_secret missing
        }
        
        llm = LiteLlm(**incomplete_config)
        
        # Should not create OAuth token manager with incomplete config
        assert llm._oauth_token_manager is None
        
        # OAuth parameters should be removed from additional_args
        assert "oauth_token_url" not in llm._additional_args
        assert "oauth_client_id" not in llm._additional_args

    @pytest.mark.asyncio
    async def test_concurrent_oauth_requests(
        self, oauth_config, mock_token_response, sample_llm_request
    ):
        """Test thread safety with concurrent OAuth-authenticated LLM requests."""
        llm = LiteLlm(**oauth_config)

        with patch("solace_agent_mesh.common.oauth.oauth_client.httpx.AsyncClient") as mock_oauth_client, \
             patch.object(llm.llm_client, "acompletion") as mock_completion:

            # Mock OAuth token response
            mock_oauth_response = MagicMock()
            mock_oauth_response.status_code = 200
            mock_oauth_response.json.return_value = mock_token_response
            mock_oauth_response.raise_for_status.return_value = None

            mock_oauth_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_oauth_response
            )

            # Mock LLM completion response
            mock_completion.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": "Hello! How can I help you today?",
                            "role": "assistant"
                        }
                    }
                ]
            }

            # Make concurrent LLM requests
            async def make_request():
                async for response in llm.generate_content_async(sample_llm_request):
                    break
                return "completed"

            tasks = [make_request() for _ in range(5)]
            results = await asyncio.gather(*tasks)

            # All requests should complete successfully
            assert all(result == "completed" for result in results)

            # OAuth token should be fetched only once due to caching and locking
            assert mock_oauth_client.return_value.__aenter__.return_value.post.call_count == 1

            # All LLM requests should be made
            assert mock_completion.call_count == 5
