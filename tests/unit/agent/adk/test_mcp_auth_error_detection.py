"""Tests for MCP authentication error detection in EmbedResolvingMCPTool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset import (
    EmbedResolvingMCPTool,
)


@pytest.fixture
def tool():
    """Create an EmbedResolvingMCPTool with minimal mocking for _is_auth_error testing."""
    # _is_auth_error is a pure function on the instance, no init dependencies needed
    instance = object.__new__(EmbedResolvingMCPTool)
    return instance


class TestIsAuthError:
    """Tests for _is_auth_error — pure logic, no mocks."""

    def test_401_json_code(self, tool):
        """Detect 401 from JSON with 'code' field."""
        result = {
            "content": [
                {"type": "text", "text": '{"code":401,"message":"Unauthorized"}'}
            ]
        }
        assert tool._is_auth_error(result) is True

    def test_403_json_code(self, tool):
        """Detect 403 from JSON with 'code' field."""
        result = {
            "content": [
                {"type": "text", "text": '{"code":403,"message":"Forbidden"}'}
            ]
        }
        assert tool._is_auth_error(result) is True

    def test_401_json_status_field(self, tool):
        """Detect 401 from JSON with 'status' field instead of 'code'."""
        result = {
            "content": [
                {"type": "text", "text": '{"status":401,"error":"Unauthorized"}'}
            ]
        }
        assert tool._is_auth_error(result) is True

    def test_401_string_fallback(self, tool):
        """Detect 401 from plain text containing '401' and 'unauthorized'."""
        result = {
            "content": [
                {"type": "text", "text": "Error 401 Unauthorized"}
            ]
        }
        assert tool._is_auth_error(result) is True

    def test_403_string_fallback(self, tool):
        """Detect 403 from plain text containing '403' and 'forbidden'."""
        result = {
            "content": [
                {"type": "text", "text": "Error 403 Forbidden"}
            ]
        }
        assert tool._is_auth_error(result) is True

    def test_200_not_auth_error(self, tool):
        """A 200 response is not an auth error."""
        result = {
            "content": [
                {"type": "text", "text": '{"code":200,"message":"OK"}'}
            ]
        }
        assert tool._is_auth_error(result) is False

    def test_500_not_auth_error(self, tool):
        """A 500 response is not an auth error."""
        result = {
            "content": [
                {"type": "text", "text": '{"code":500,"message":"Internal Server Error"}'}
            ]
        }
        assert tool._is_auth_error(result) is False

    def test_normal_text_response(self, tool):
        """Normal tool output text is not an auth error."""
        result = {
            "content": [
                {"type": "text", "text": "Here are your search results..."}
            ]
        }
        assert tool._is_auth_error(result) is False

    def test_non_dict_result(self, tool):
        """Non-dict result returns False."""
        assert tool._is_auth_error("not a dict") is False
        assert tool._is_auth_error(None) is False

    def test_empty_content(self, tool):
        """Empty content list returns False."""
        assert tool._is_auth_error({"content": []}) is False

    def test_non_text_content_type(self, tool):
        """Content items with non-text type are skipped."""
        result = {
            "content": [
                {"type": "image", "data": "..."}
            ]
        }
        assert tool._is_auth_error(result) is False

    def test_401_in_text_without_unauthorized_no_match(self, tool):
        """'401' alone in text without 'unauthorized' doesn't match string fallback."""
        result = {
            "content": [
                {"type": "text", "text": "Got error code 401 from server"}
            ]
        }
        assert tool._is_auth_error(result) is False

    def test_unauthorized_without_401_no_match(self, tool):
        """'unauthorized' alone without '401' doesn't match string fallback."""
        result = {
            "content": [
                {"type": "text", "text": "You are unauthorized to access this"}
            ]
        }
        assert tool._is_auth_error(result) is False

    def test_json_code_zero_not_falsy(self, tool):
        """JSON code of 0 should not fall through to 'status' field."""
        result = {
            "content": [
                {"type": "text", "text": '{"code":0,"status":401}'}
            ]
        }
        assert tool._is_auth_error(result) is False

    def test_multiple_content_items_second_is_auth_error(self, tool):
        """Auth error detected even if it's not in the first content item."""
        result = {
            "content": [
                {"type": "text", "text": "Some preamble"},
                {"type": "text", "text": '{"code":401,"message":"Unauthorized"}'},
            ]
        }
        assert tool._is_auth_error(result) is True

    def test_is_error_flag_irrelevant(self, tool):
        """Detection works regardless of isError field value."""
        result_false = {
            "content": [
                {"type": "text", "text": '{"code":401,"message":"Unauthorized"}'}
            ],
            "isError": False,
        }
        result_true = {
            "content": [
                {"type": "text", "text": '{"code":401,"message":"Unauthorized"}'}
            ],
            "isError": True,
        }
        assert tool._is_auth_error(result_false) is True
        assert tool._is_auth_error(result_true) is True


class TestClearCachedCredentials:
    """Tests for _clear_cached_credentials."""

    @pytest.mark.asyncio
    async def test_clears_wrapper_and_original_credentials(self):
        """Clears exchanged_auth_credential on both wrapper and original tool."""
        instance = object.__new__(EmbedResolvingMCPTool)

        # Set up wrapper credential manager
        wrapper_auth_config = MagicMock()
        wrapper_auth_config.exchanged_auth_credential = "stale-token"
        wrapper_cm = MagicMock()
        wrapper_cm._auth_config = wrapper_auth_config
        instance._credentials_manager = wrapper_cm

        # Set up original tool's credential manager
        original_auth_config = MagicMock()
        original_auth_config.exchanged_auth_credential = "stale-token"
        original_cm = MagicMock()
        original_cm._auth_config = original_auth_config
        original_tool = MagicMock()
        original_tool._credentials_manager = original_cm
        instance._original_mcp_tool = original_tool

        # Mock tool_context.save_credential
        tool_context = MagicMock()
        tool_context.save_credential = AsyncMock()

        await instance._clear_cached_credentials(tool_context)

        assert wrapper_auth_config.exchanged_auth_credential is None
        assert original_auth_config.exchanged_auth_credential is None
        tool_context.save_credential.assert_awaited_once_with(wrapper_auth_config)

    @pytest.mark.asyncio
    async def test_no_credential_manager_returns_early(self):
        """Does nothing when no credential manager is set."""
        instance = object.__new__(EmbedResolvingMCPTool)
        instance._credentials_manager = None

        tool_context = MagicMock()
        tool_context.save_credential = AsyncMock()

        await instance._clear_cached_credentials(tool_context)

        tool_context.save_credential.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handles_no_credential_service(self):
        """Handles ValueError from save_credential when no credential service exists."""
        instance = object.__new__(EmbedResolvingMCPTool)

        auth_config = MagicMock()
        auth_config.exchanged_auth_credential = "token"
        cm = MagicMock()
        cm._auth_config = auth_config
        instance._credentials_manager = cm

        original_tool = MagicMock(spec=[])  # no _credentials_manager attr
        instance._original_mcp_tool = original_tool

        tool_context = MagicMock()
        tool_context.save_credential = AsyncMock(side_effect=ValueError("no service"))

        # Should not raise
        await instance._clear_cached_credentials(tool_context)
        assert auth_config.exchanged_auth_credential is None


class TestRunAsyncImplAuthErrorHandling:
    """Tests for auth error detection and re-auth in _run_async_impl."""

    @pytest.mark.asyncio
    async def test_auth_error_triggers_reauth(self):
        """When MCP returns 401, clears credentials and requests re-auth."""
        instance = object.__new__(EmbedResolvingMCPTool)
        instance.name = "test-tool"
        instance._tool_config = {}

        auth_error_result = {
            "content": [
                {"type": "text", "text": '{"code":401,"message":"Unauthorized"}'}
            ]
        }

        # Mock _execute_tool_with_audit_logs to return auth error
        instance._execute_tool_with_audit_logs = AsyncMock(return_value=auth_error_result)

        # Mock credential manager
        cm = MagicMock()
        cm._auth_config = MagicMock()
        cm._auth_config.exchanged_auth_credential = "stale"
        cm.request_credential = AsyncMock()
        instance._credentials_manager = cm

        # Mock original tool
        original_tool = MagicMock(spec=[])
        instance._original_mcp_tool = original_tool

        # Mock tool_context
        tool_context = MagicMock()
        tool_context.save_credential = AsyncMock()

        with patch.object(instance, "_clear_cached_credentials", new_callable=AsyncMock) as mock_clear:
            result = await instance._run_async_impl(
                args={}, tool_context=tool_context, credential=None
            )

        mock_clear.assert_awaited_once_with(tool_context)
        cm.request_credential.assert_awaited_once_with(tool_context)
        assert result == {"error": "Pending user authorization."}

    @pytest.mark.asyncio
    async def test_auth_error_without_credential_manager(self):
        """When MCP returns 401 but no credential manager, returns retry message."""
        instance = object.__new__(EmbedResolvingMCPTool)
        instance.name = "test-tool"
        instance._tool_config = {}
        instance._credentials_manager = None

        auth_error_result = {
            "content": [
                {"type": "text", "text": '{"code":401,"message":"Unauthorized"}'}
            ]
        }

        instance._execute_tool_with_audit_logs = AsyncMock(return_value=auth_error_result)
        instance._original_mcp_tool = MagicMock(spec=[])

        tool_context = MagicMock()
        tool_context.save_credential = AsyncMock()

        with patch.object(instance, "_clear_cached_credentials", new_callable=AsyncMock):
            result = await instance._run_async_impl(
                args={}, tool_context=tool_context, credential=None
            )

        assert "expired or been revoked" in result["error"]
