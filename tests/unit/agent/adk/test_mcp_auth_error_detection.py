"""Tests for MCP authentication error detection in EmbedResolvingMCPTool."""

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
