"""
Unit tests for the sanitize_tool_names_callback function.

This callback catches hallucinated tool names (like $FUNCTION_NAME, $ARTIFACT_TOOL)
that would cause BedrockException errors when sent to the LLM provider.
"""

import pytest
from unittest.mock import Mock, MagicMock
from google.genai import types as adk_types
from google.adk.models.llm_response import LlmResponse
from google.adk.agents.callback_context import CallbackContext

from solace_agent_mesh.agent.adk.callbacks import (
    sanitize_tool_names_callback,
    VALID_TOOL_NAME_PATTERN,
)


class TestValidToolNamePattern:
    """Test the VALID_TOOL_NAME_PATTERN regex."""

    def test_valid_simple_name(self):
        """Simple tool names should be valid."""
        assert VALID_TOOL_NAME_PATTERN.match("search") is not None
        assert VALID_TOOL_NAME_PATTERN.match("Search") is not None

    def test_valid_name_with_underscore(self):
        """Tool names with underscores should be valid."""
        assert VALID_TOOL_NAME_PATTERN.match("search_database") is not None
        assert VALID_TOOL_NAME_PATTERN.match("get_user_info") is not None

    def test_valid_name_with_hyphen(self):
        """Tool names with hyphens should be valid."""
        assert VALID_TOOL_NAME_PATTERN.match("search-database") is not None
        assert VALID_TOOL_NAME_PATTERN.match("get-user-info") is not None

    def test_valid_name_with_numbers(self):
        """Tool names with numbers should be valid."""
        assert VALID_TOOL_NAME_PATTERN.match("search2") is not None
        assert VALID_TOOL_NAME_PATTERN.match("v2_search") is not None

    def test_valid_mixed_name(self):
        """Tool names with mixed characters should be valid."""
        assert VALID_TOOL_NAME_PATTERN.match("peer_AgentName-tool_v2") is not None

    def test_valid_underscore_prefix(self):
        """Tool names starting with underscore should be valid (internal tools)."""
        assert VALID_TOOL_NAME_PATTERN.match("_notify_artifact_save") is not None
        assert VALID_TOOL_NAME_PATTERN.match("_internal_tool") is not None
        assert VALID_TOOL_NAME_PATTERN.match("_continue_generation") is not None

    def test_invalid_starts_with_dollar(self):
        """Tool names starting with $ should be invalid."""
        assert VALID_TOOL_NAME_PATTERN.match("$FUNCTION_NAME") is None
        assert VALID_TOOL_NAME_PATTERN.match("$ARTIFACT_TOOL") is None
        assert VALID_TOOL_NAME_PATTERN.match("$TOOL_NAME") is None

    def test_invalid_starts_with_number(self):
        """Tool names starting with a number should be invalid."""
        assert VALID_TOOL_NAME_PATTERN.match("2search") is None
        assert VALID_TOOL_NAME_PATTERN.match("123tool") is None

    def test_invalid_contains_spaces(self):
        """Tool names with spaces should be invalid."""
        assert VALID_TOOL_NAME_PATTERN.match("search database") is None
        assert VALID_TOOL_NAME_PATTERN.match("get user info") is None

    def test_invalid_special_characters(self):
        """Tool names with special characters should be invalid."""
        assert VALID_TOOL_NAME_PATTERN.match("search@database") is None
        assert VALID_TOOL_NAME_PATTERN.match("get.user.info") is None
        assert VALID_TOOL_NAME_PATTERN.match("tool#1") is None


class TestSanitizeToolNamesCallback:
    """Test the sanitize_tool_names_callback function."""

    def _create_mock_callback_context(self):
        """Create a mock CallbackContext for testing."""
        mock_context = Mock(spec=CallbackContext)
        mock_context.state = {}
        return mock_context

    def _create_mock_host_component(self):
        """Create a mock SamAgentComponent for testing."""
        mock_host = Mock()
        mock_host.log_identifier = "[Test]"
        return mock_host

    def _create_llm_response(
        self, parts, partial=False, turn_complete=False
    ) -> LlmResponse:
        """Create an LlmResponse with the given parts."""
        return LlmResponse(
            content=adk_types.Content(role="model", parts=parts),
            partial=partial,
            turn_complete=turn_complete,
        )

    def _create_function_call_part(self, name, args=None, call_id=None):
        """Create a Part with a function_call."""
        fc = adk_types.FunctionCall(
            name=name,
            args=args or {},
            id=call_id or f"call-{name}",
        )
        return adk_types.Part(function_call=fc)

    def _create_text_part(self, text):
        """Create a Part with text."""
        return adk_types.Part(text=text)

    # =========================================================================
    # Tests for skipping conditions
    # =========================================================================

    def test_skips_partial_responses(self):
        """Partial responses should be skipped (return None)."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        # Create a partial response with an invalid tool name
        llm_response = self._create_llm_response(
            parts=[self._create_function_call_part("$FUNCTION_NAME")],
            partial=True,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is None

    def test_skips_empty_content(self):
        """Responses with no content should be skipped."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = LlmResponse(content=None, partial=False)

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is None

    def test_skips_empty_parts(self):
        """Responses with empty parts list should be skipped."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = LlmResponse(
            content=adk_types.Content(role="model", parts=[]),
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is None

    def test_skips_valid_tool_names(self):
        """Responses with only valid tool names should not be modified."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[
                self._create_function_call_part("search_database"),
                self._create_function_call_part("peer_AgentName-get_info"),
                self._create_function_call_part("_notify_artifact_save"),
            ],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is None

    def test_skips_text_only_responses(self):
        """Responses with only text parts should not be modified."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[
                self._create_text_part("Hello, how can I help you?"),
                self._create_text_part("Let me search for that."),
            ],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is None

    # =========================================================================
    # Tests for placeholder hallucination detection
    # =========================================================================

    def test_catches_dollar_function_name(self):
        """$FUNCTION_NAME should be caught as a placeholder hallucination."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[self._create_function_call_part("$FUNCTION_NAME", {"arg": "value"})],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is not None
        # Should have error content stored in callback state
        assert "sanitized_tool_error_content" in callback_context.state

    def test_catches_dollar_artifact_tool(self):
        """$ARTIFACT_TOOL should be caught as a placeholder hallucination."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[self._create_function_call_part("$ARTIFACT_TOOL")],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is not None
        assert "sanitized_tool_error_content" in callback_context.state

    def test_catches_dollar_tool_name(self):
        """$TOOL_NAME should be caught as a placeholder hallucination."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[self._create_function_call_part("$TOOL_NAME")],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is not None
        assert "sanitized_tool_error_content" in callback_context.state

    def test_catches_any_dollar_prefix(self):
        """Any tool name starting with $ should be caught."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[self._create_function_call_part("$RANDOM_PLACEHOLDER")],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is not None
        assert "sanitized_tool_error_content" in callback_context.state

    # =========================================================================
    # Tests for invalid format detection
    # =========================================================================

    def test_catches_tool_name_starting_with_number(self):
        """Tool names starting with a number should be caught."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[self._create_function_call_part("123_tool")],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is not None
        assert "sanitized_tool_error_content" in callback_context.state

    def test_catches_tool_name_with_spaces(self):
        """Tool names with spaces should be caught."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[self._create_function_call_part("search database")],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is not None
        assert "sanitized_tool_error_content" in callback_context.state

    def test_catches_tool_name_with_special_chars(self):
        """Tool names with special characters should be caught."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[self._create_function_call_part("search@database")],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is not None
        assert "sanitized_tool_error_content" in callback_context.state

    # =========================================================================
    # Tests for mixed valid/invalid calls
    # =========================================================================

    def test_preserves_valid_calls_removes_invalid(self):
        """Valid tool calls should be preserved while invalid ones are removed."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[
                self._create_function_call_part("valid_tool"),
                self._create_function_call_part("$FUNCTION_NAME"),
                self._create_function_call_part("another_valid_tool"),
            ],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is not None
        # Should have 2 valid parts remaining
        valid_function_calls = [
            p for p in result.content.parts if p.function_call
        ]
        assert len(valid_function_calls) == 2
        assert valid_function_calls[0].function_call.name == "valid_tool"
        assert valid_function_calls[1].function_call.name == "another_valid_tool"

    def test_preserves_text_parts(self):
        """Text parts should be preserved when removing invalid tool calls."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[
                self._create_text_part("Let me help you with that."),
                self._create_function_call_part("$FUNCTION_NAME"),
            ],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is not None
        # Should have the text part preserved
        text_parts = [p for p in result.content.parts if p.text]
        assert len(text_parts) == 1
        assert text_parts[0].text == "Let me help you with that."

    # =========================================================================
    # Tests for error response generation
    # =========================================================================

    def test_generates_error_response_for_placeholder(self):
        """Error response should mention placeholder hallucination."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[
                self._create_function_call_part(
                    "$FUNCTION_NAME", {"arg": "value"}, "call-123"
                )
            ],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is not None
        error_content = callback_context.state.get("sanitized_tool_error_content")
        assert error_content is not None
        assert error_content.role == "tool"
        assert len(error_content.parts) == 1

        error_response = error_content.parts[0].function_response
        assert error_response.name == "$FUNCTION_NAME"
        assert error_response.id == "call-123"
        assert "hallucinated" in error_response.response["message"].lower()

    def test_generates_error_response_for_invalid_format(self):
        """Error response should mention invalid format."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[
                self._create_function_call_part("123_invalid", {}, "call-456")
            ],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is not None
        error_content = callback_context.state.get("sanitized_tool_error_content")
        assert error_content is not None

        error_response = error_content.parts[0].function_response
        assert error_response.name == "123_invalid"
        assert error_response.id == "call-456"
        assert "format" in error_response.response["message"].lower()

    def test_multiple_invalid_calls_generate_multiple_errors(self):
        """Multiple invalid calls should generate multiple error responses."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[
                self._create_function_call_part("$FUNCTION_NAME", {}, "call-1"),
                self._create_function_call_part("$ARTIFACT_TOOL", {}, "call-2"),
                self._create_function_call_part("123_invalid", {}, "call-3"),
            ],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is not None
        error_content = callback_context.state.get("sanitized_tool_error_content")
        assert error_content is not None
        assert len(error_content.parts) == 3

    # =========================================================================
    # Tests for response modification
    # =========================================================================

    def test_sets_turn_complete_false(self):
        """Modified response should have turn_complete=False to force another turn."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[self._create_function_call_part("$FUNCTION_NAME")],
            partial=False,
            turn_complete=True,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is not None
        assert result.turn_complete is False

    def test_all_invalid_returns_modified_response(self):
        """When all calls are invalid, should return modified response with error content."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[
                self._create_function_call_part("$FUNCTION_NAME"),
                self._create_function_call_part("$ARTIFACT_TOOL"),
            ],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is not None
        # When all function calls are invalid, should return a response with placeholder text
        assert result.content is not None
        assert len(result.content.parts) >= 1
        # Should have turn_complete=False to allow error responses to be processed
        assert result.turn_complete is False
        # Error content should be stored in callback state
        assert "sanitized_tool_error_content" in callback_context.state

    # =========================================================================
    # Tests for edge cases
    # =========================================================================

    def test_handles_none_function_call_id(self):
        """Should handle function calls without an ID."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        # Create a function call without an ID
        fc = adk_types.FunctionCall(name="$FUNCTION_NAME", args={}, id=None)
        part = adk_types.Part(function_call=fc)

        llm_response = self._create_llm_response(parts=[part], partial=False)

        # Should not raise an exception
        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is not None

    def test_handles_empty_tool_name(self):
        """Should handle empty tool names."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        llm_response = self._create_llm_response(
            parts=[self._create_function_call_part("")],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        # Empty string doesn't match the pattern, so it should be caught
        assert result is not None

    def test_preserves_function_call_args(self):
        """Error response should preserve the original function call args context."""
        callback_context = self._create_mock_callback_context()
        host_component = self._create_mock_host_component()

        original_args = {"filename": "test.txt", "content": "Hello World"}
        llm_response = self._create_llm_response(
            parts=[
                self._create_function_call_part(
                    "$FUNCTION_NAME", original_args, "call-with-args"
                )
            ],
            partial=False,
        )

        result = sanitize_tool_names_callback(
            callback_context, llm_response, host_component
        )

        assert result is not None
        # The error response should be generated (args are logged but not in response)
        error_content = callback_context.state.get("sanitized_tool_error_content")
        assert error_content is not None
