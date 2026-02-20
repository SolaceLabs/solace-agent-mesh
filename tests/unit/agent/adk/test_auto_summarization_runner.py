"""
Unit tests for auto-summarization functionality in runner.py
"""
import pytest
import time
from unittest.mock import AsyncMock, Mock, patch
from google.adk.events import Event as ADKEvent
from google.adk.events.event_actions import EventActions, EventCompaction
from google.adk.sessions import Session as ADKSession
from google.genai import types as adk_types
from litellm.exceptions import BadRequestError
from solace_agent_mesh.agent.adk.runner import (
    _calculate_total_char_count,
    _find_compaction_cutoff,
    _is_context_limit_error,
    _is_background_task,
    _send_truncation_notification,
)


class TestCalculateTotalCharCount:
    """Tests for _calculate_total_char_count function."""

    def test_empty_events_list_returns_zero(self):
        """Empty events list should return 0 characters."""
        result = _calculate_total_char_count([])
        assert result == 0

    def test_events_with_no_content_returns_zero(self):
        """Events with no content should return 0 characters."""
        events = [
            ADKEvent(invocation_id="test1", author="user"),
            ADKEvent(invocation_id="test2", author="model"),
        ]
        result = _calculate_total_char_count(events)
        assert result == 0

    def test_single_event_single_part_counts_correctly(self):
        """Single event with single text part should count characters."""
        events = [
            ADKEvent(
                invocation_id="test1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(text="Hello world")]
                )
            )
        ]
        result = _calculate_total_char_count(events)
        assert result == 11  # len("Hello world")

    def test_multiple_events_multiple_parts_sums_correctly(self):
        """Multiple events with multiple parts should sum all characters."""
        events = [
            ADKEvent(
                invocation_id="test1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[
                        adk_types.Part(text="Hello"),
                        adk_types.Part(text="world"),
                    ]
                )
            ),
            ADKEvent(
                invocation_id="test2",
                author="model",
                content=adk_types.Content(
                    role="model",
                    parts=[adk_types.Part(text="Hi there!")]
                )
            )
        ]
        result = _calculate_total_char_count(events)
        # "Hello" (5) + "world" (5) + "Hi there!" (9) = 19
        assert result == 19

    def test_mixed_events_with_and_without_content(self):
        """Mixed events should only count those with content."""
        events = [
            ADKEvent(
                invocation_id="test1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(text="Test")]
                )
            ),
            ADKEvent(invocation_id="test2", author="model"),  # No content
            ADKEvent(
                invocation_id="test3",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(text="Message")]
                )
            ),
        ]
        result = _calculate_total_char_count(events)
        # "Test" (4) + "Message" (7) = 11
        assert result == 11

    def test_events_with_empty_text_parts(self):
        """Events with empty text parts should not contribute to count."""
        events = [
            ADKEvent(
                invocation_id="test1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[
                        adk_types.Part(text=""),
                        adk_types.Part(text="Valid text"),
                    ]
                )
            )
        ]
        result = _calculate_total_char_count(events)
        assert result == 10  # len("Valid text")


class TestFindCompactionCutoff:
    """Tests for _find_compaction_cutoff function."""

    def test_empty_events_returns_zero(self):
        """Empty events list should return (0, 0)."""
        cutoff_idx, actual_chars = _find_compaction_cutoff([], 100)
        assert cutoff_idx == 0
        assert actual_chars == 0

    def test_insufficient_user_turns_returns_zero(self):
        """Less than 2 user turns should return (0, 0)."""
        events = [
            ADKEvent(
                invocation_id="test1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(text="Single user message")]
                )
            ),
            ADKEvent(
                invocation_id="test2",
                author="model",
                content=adk_types.Content(
                    role="model",
                    parts=[adk_types.Part(text="Response")]
                )
            ),
        ]
        cutoff_idx, actual_chars = _find_compaction_cutoff(events, 10)
        assert cutoff_idx == 0
        assert actual_chars == 0

    def test_finds_cutoff_at_nearest_user_turn_boundary(self):
        """Should find user turn boundary closest to target character count."""
        events = [
            # Turn 1 (user): 20 chars
            ADKEvent(
                invocation_id="u1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(text="First user message!!")]  # 20 chars
                )
            ),
            ADKEvent(
                invocation_id="m1",
                author="model",
                content=adk_types.Content(
                    role="model",
                    parts=[adk_types.Part(text="Response one")]  # 12 chars
                )
            ),
            # Turn 2 (user): cumulative 52 chars
            ADKEvent(
                invocation_id="u2",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(text="Second user message!")]  # 20 chars
                )
            ),
            ADKEvent(
                invocation_id="m2",
                author="model",
                content=adk_types.Content(
                    role="model",
                    parts=[adk_types.Part(text="Response two")]  # 12 chars
                )
            ),
            # Turn 3 (user): cumulative 84 chars (should not be compacted - always leave 1)
            ADKEvent(
                invocation_id="u3",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(text="Third user message!!")]  # 20 chars
                )
            ),
            ADKEvent(
                invocation_id="m3",
                author="model",
                content=adk_types.Content(
                    role="model",
                    parts=[adk_types.Part(text="Response three")]  # 14 chars
                )
            ),
        ]

        # Target 50 chars: closest is turn 2 boundary (64 chars, index 4)
        cutoff_idx, actual_chars = _find_compaction_cutoff(events, 50)
        assert cutoff_idx == 4  # Index of u3 (start of turn 3)
        assert actual_chars == 64  # First 2 turns: 20+12+20+12 = 64

    def test_always_leaves_at_least_one_user_turn_uncompacted(self):
        """Last user turn should never be compacted."""
        events = [
            ADKEvent(
                invocation_id="u1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(text="A" * 100)]
                )
            ),
            ADKEvent(
                invocation_id="m1",
                author="model",
                content=adk_types.Content(
                    role="model",
                    parts=[adk_types.Part(text="B" * 100)]
                )
            ),
            ADKEvent(
                invocation_id="u2",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(text="C" * 100)]
                )
            ),
        ]

        # Even with high target, should stop before last turn
        cutoff_idx, actual_chars = _find_compaction_cutoff(events, 500)
        assert cutoff_idx == 2  # Start of u2
        assert actual_chars == 200  # u1 + m1


class TestIsContextLimitError:
    """Tests for _is_context_limit_error function."""

    def test_detects_too_many_tokens_error(self):
        """Should detect 'too many tokens' error."""
        error = BadRequestError(
            message="Request failed: too many tokens in prompt",
            model="test-model",
            llm_provider="test"
        )
        assert _is_context_limit_error(error) is True

    def test_detects_maximum_context_length_error(self):
        """Should detect 'maximum context length' error."""
        error = BadRequestError(
            message="Error: maximum context length exceeded",
            model="test-model",
            llm_provider="test"
        )
        assert _is_context_limit_error(error) is True

    def test_detects_context_length_exceeded_error(self):
        """Should detect 'context length exceeded' error."""
        error = BadRequestError(
            message="context_length_exceeded: The request was too long",
            model="test-model",
            llm_provider="test"
        )
        assert _is_context_limit_error(error) is True

    def test_detects_input_too_long_error(self):
        """Should detect 'input is too long' error."""
        error = BadRequestError(
            message="The input is too long for this model",
            model="test-model",
            llm_provider="test"
        )
        assert _is_context_limit_error(error) is True

    def test_detects_prompt_too_long_error(self):
        """Should detect 'prompt is too long' error."""
        error = BadRequestError(
            message="Error: prompt is too long",
            model="test-model",
            llm_provider="test"
        )
        assert _is_context_limit_error(error) is True

    def test_detects_token_limit_error(self):
        """Should detect 'token limit' error."""
        error = BadRequestError(
            message="Request exceeds token limit",
            model="test-model",
            llm_provider="test"
        )
        assert _is_context_limit_error(error) is True

    def test_case_insensitive_detection(self):
        """Detection should be case insensitive."""
        error = BadRequestError(
            message="TOO MANY TOKENS IN REQUEST",
            model="test-model",
            llm_provider="test"
        )
        assert _is_context_limit_error(error) is True

    def test_rejects_non_context_limit_errors(self):
        """Should reject errors not related to context limits."""
        errors = [
            BadRequestError(message="Invalid API key", model="test", llm_provider="test"),
            BadRequestError(message="Rate limit exceeded", model="test", llm_provider="test"),
            BadRequestError(message="Model not found", model="test", llm_provider="test"),
            BadRequestError(message="Internal server error", model="test", llm_provider="test"),
        ]
        for error in errors:
            assert _is_context_limit_error(error) is False


class TestIsBackgroundTask:
    """Tests for _is_background_task function."""

    def test_detects_background_via_metadata_flag(self):
        """Should detect background task via metadata.backgroundExecutionEnabled."""
        a2a_context = {
            "metadata": {
                "backgroundExecutionEnabled": True
            }
        }
        assert _is_background_task(a2a_context) is True

    def test_detects_interactive_when_background_flag_false(self):
        """Should detect interactive task when backgroundExecutionEnabled is False."""
        a2a_context = {
            "metadata": {
                "backgroundExecutionEnabled": False
            },
            "client_id": "user123"
        }
        assert _is_background_task(a2a_context) is False

    def test_detects_background_via_reply_topic_without_client(self):
        """Should detect background task when replyToTopic exists but no client_id."""
        a2a_context = {
            "replyToTopic": "agent/peer-agent/responses"
            # No client_id
        }
        assert _is_background_task(a2a_context) is True

    def test_detects_interactive_when_client_id_present(self):
        """Should detect interactive task when client_id is present."""
        a2a_context = {
            "client_id": "user123"
        }
        assert _is_background_task(a2a_context) is False

    def test_detects_interactive_when_both_reply_topic_and_client(self):
        """Should detect interactive when both replyToTopic and client_id present."""
        a2a_context = {
            "replyToTopic": "gateway/response",
            "client_id": "user123"
        }
        assert _is_background_task(a2a_context) is False

    def test_detects_background_when_no_indicators(self):
        """Should default to background=False when no clear indicators."""
        a2a_context = {}
        assert _is_background_task(a2a_context) is False


class TestSendTruncationNotification:
    """Tests for _send_truncation_notification function."""

    @pytest.mark.asyncio
    async def test_sends_interactive_notification_with_warning(self):
        """Should send notification with warning emoji for interactive tasks."""
        component = Mock()
        component._publish_a2a_event = Mock()
        component.get_config = Mock(return_value="test-namespace")

        a2a_context = {
            "logical_task_id": "task1",
            "contextId": "ctx1",
            "jsonrpc_request_id": "req1",
            "client_id": "client1"
        }

        with patch('solace_agent_mesh.agent.adk.runner.a2a') as mock_a2a:
            mock_a2a.create_agent_text_message.return_value = {"type": "text"}
            mock_a2a.create_status_update.return_value = {"type": "status"}
            mock_a2a.create_success_response.return_value = Mock(model_dump=Mock(return_value={}))
            mock_a2a.get_client_response_topic.return_value = "response/topic"

            await _send_truncation_notification(
                component=component,
                a2a_context=a2a_context,
                summary="Test summary of conversation",
                is_background=False,
                log_identifier="[Test]"
            )

            # Verify message was created with interactive warning
            call_args = mock_a2a.create_agent_text_message.call_args
            notification_text = call_args[1]['text']
            assert "ℹ️" in notification_text
            assert "Your conversation history reached the limit" in notification_text
            assert "Test summary of conversation" in notification_text

            # Verify publish was called
            assert component._publish_a2a_event.called

    @pytest.mark.asyncio
    async def test_sends_background_notification_with_info(self):
        """Should send notification with info emoji for background tasks."""
        component = Mock()
        component._publish_a2a_event = Mock()
        component.get_config = Mock(return_value="test-namespace")

        a2a_context = {
            "logical_task_id": "task1",
            "contextId": "ctx1",
            "jsonrpc_request_id": "req1",
            "replyToTopic": "agent/peer/responses"  # Background task indicator
        }

        with patch('solace_agent_mesh.agent.adk.runner.a2a') as mock_a2a:
            mock_a2a.create_agent_text_message.return_value = {"type": "text"}
            mock_a2a.create_status_update.return_value = {"type": "status"}
            mock_a2a.create_success_response.return_value = Mock(model_dump=Mock(return_value={}))
            mock_a2a.get_client_response_topic.return_value = "response/topic"

            await _send_truncation_notification(
                component=component,
                a2a_context=a2a_context,
                summary="Background task summary",
                is_background=True,
                log_identifier="[Test]"
            )

            # Verify message was created with background info
            call_args = mock_a2a.create_agent_text_message.call_args
            notification_text = call_args[1]['text']
            assert "ℹ️" in notification_text
            assert "Note:" in notification_text
            assert "Background task summary" in notification_text

            # Verify publish was called
            assert component._publish_a2a_event.called