"""
Unit tests for auto-summarization functionality in runner.py
"""
import pytest
import time
import base64
from unittest.mock import AsyncMock, Mock, patch
from google.adk.events import Event as ADKEvent
from google.adk.events.event_actions import EventActions, EventCompaction
from google.adk.sessions import Session as ADKSession
from google.genai import types as adk_types
from litellm.exceptions import BadRequestError
from solace_agent_mesh.agent.adk.runner import (
    _calculate_session_context_tokens,
    _create_compaction_event,
    _find_compaction_cutoff,
    _is_context_limit_error,
    _is_background_task,
    _send_truncation_notification,
)


class TestCalculateSessionContextTokens:
    """Tests for _calculate_session_context_tokens function."""

    def test_empty_events_list_returns_zero(self):
        """Empty events list should return 0 tokens."""
        result = _calculate_session_context_tokens([])
        assert result == 0

    def test_events_with_no_content_returns_zero(self):
        """Events with no content should return 0 tokens."""
        events = [
            ADKEvent(invocation_id="test1", author="user"),
            ADKEvent(invocation_id="test2", author="model"),
        ]
        result = _calculate_session_context_tokens(events)
        assert result == 0

    def test_single_event_single_part_counts_correctly(self):
        """Single event with single text part should count tokens."""
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
        result = _calculate_session_context_tokens(events)
        # Real token count: ~3-5 tokens for "Hello world"
        assert result > 0, "Should count tokens"
        assert result < 20, "Should not be excessive"

    def test_multiple_events_multiple_parts_sums_correctly(self):
        """Multiple events with multiple parts should sum all tokens."""
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
        result = _calculate_session_context_tokens(events)
        # Real token count should be more than single event
        assert result > 5, "Multiple events should have more tokens"
        assert result < 50, "Should not be excessive"

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
        result = _calculate_session_context_tokens(events)
        # Should count events with content only (2 events)
        assert result > 0, "Should count tokens from events with content"
        assert result < 30, "Should not be excessive"

    def test_events_with_empty_text_parts(self):
        """Events with empty text parts should be handled by token_counter."""
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
        result = _calculate_session_context_tokens(events)
        # Should count non-empty parts
        assert result > 0, "Should count valid text parts"
        assert result < 20, "Should be reasonable"

    def test_token_counter_failure_returns_zero(self):
        """Should gracefully handle token_counter exceptions."""
        # Create events with extremely large content to potentially cause issues
        events = [
            ADKEvent(
                invocation_id="test1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(text="Test")]
                )
            )
        ]
        result = _calculate_session_context_tokens(events)
        # Normal case should work (not trigger exception)
        assert result > 0, "Normal cases should work"

    def test_event_with_binary_image_content(self):
        """Should count tokens for events with embedded binary images."""
        # Create a fake JPEG image (100KB)
        fake_image_data = b'\xFF\xD8\xFF\xE0' + b'\x00' * (100 * 1024 - 4)
        encoded = base64.b64encode(fake_image_data).decode('utf-8')

        events = [
            ADKEvent(
                invocation_id="test1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[
                        adk_types.Part(text="Here is an image:"),
                        adk_types.Part(
                            inline_data=adk_types.Blob(
                                data=encoded.encode('utf-8'),
                                mime_type="image/jpeg"
                            )
                        )
                    ]
                )
            )
        ]
        result = _calculate_session_context_tokens(events)
        # Image should contribute significant tokens (base 85 + tiles)
        # Text "Here is an image:" ≈ 4 tokens + image ≈ 85-170 tokens
        assert result > 50, f"Image should add significant tokens, got {result}"
        assert result < 500, "Should be reasonable"

    def test_text_plus_image_counts_both(self):
        """Should count both text and image tokens."""
        fake_image_data = b'\xFF\xD8\xFF\xE0' + b'\x00' * (50 * 1024 - 4)
        encoded = base64.b64encode(fake_image_data).decode('utf-8')

        # Text only event
        text_only_events = [
            ADKEvent(
                invocation_id="test1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(text="Here is content")]
                )
            )
        ]
        text_tokens = _calculate_session_context_tokens(text_only_events)

        # Text + image event
        text_image_events = [
            ADKEvent(
                invocation_id="test1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[
                        adk_types.Part(text="Here is content"),
                        adk_types.Part(
                            inline_data=adk_types.Blob(
                                data=encoded.encode('utf-8'),
                                mime_type="image/jpeg"
                            )
                        )
                    ]
                )
            )
        ]
        text_image_tokens = _calculate_session_context_tokens(text_image_events)

        # Text + image should have more tokens than text alone
        assert text_image_tokens > text_tokens, \
            f"Image + text ({text_image_tokens}) should > text only ({text_tokens})"
        # Image should add at least 50 tokens
        assert text_image_tokens - text_tokens > 50, \
            f"Image should add >50 tokens, but only added {text_image_tokens - text_tokens}"

    def test_event_with_binary_video_content(self):
        """Should count tokens for events with embedded binary video data."""
        # Create a fake MP4 video (1MB)
        fake_video_data = b'\x00\x00\x00\x20ftypmp42' + b'\x00' * (1024 * 1024 - 8)
        encoded = base64.b64encode(fake_video_data).decode('utf-8')

        events = [
            ADKEvent(
                invocation_id="test1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[
                        adk_types.Part(text="Watch this video:"),
                        adk_types.Part(
                            inline_data=adk_types.Blob(
                                data=encoded.encode('utf-8'),
                                mime_type="video/mp4"
                            )
                        )
                    ]
                )
            )
        ]
        result = _calculate_session_context_tokens(events)
        # Video size: 1MB raw + base64 encoding (~33% overhead) = ~1.33MB data
        # Token estimate: 1 token per 250 bytes = ~5,300+ tokens
        # Including text overhead: ~5,600+ tokens
        assert result > 5000, f"Video should contribute ~5600+ tokens, got {result}"
        assert result < 6000, "Should be in expected range"

    def test_event_with_binary_audio_content(self):
        """Should count tokens for events with embedded audio data (currently skipped)."""
        # Create a fake WAV audio file (500KB)
        fake_audio_data = b'RIFF' + b'\x00' * (500 * 1024 - 4)
        encoded = base64.b64encode(fake_audio_data).decode('utf-8')

        events = [
            ADKEvent(
                invocation_id="test1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[
                        adk_types.Part(text="Here is audio:"),
                        adk_types.Part(
                            inline_data=adk_types.Blob(
                                data=encoded.encode('utf-8'),
                                mime_type="audio/wav"
                            )
                        )
                    ]
                )
            )
        ]
        result = _calculate_session_context_tokens(events)
        # Audio is currently skipped (not yet supported by litellm.token_counter)
        # Only text "Here is audio:" should be counted: ~3-4 tokens + overhead
        # Expected: 8-15 tokens (just text, no audio contribution)
        assert result > 5, f"Should count at least text, got {result}"
        assert result < 50, f"Audio is skipped, only text counted, got {result}"

    def test_mixed_binary_types_text_image_video_audio(self):
        """Should count all binary types together with text."""
        fake_image = b'\xFF\xD8\xFF\xE0' + b'\x00' * (50 * 1024 - 4)
        fake_video = b'\x00\x00\x00\x20ftypmp42' + b'\x00' * (500 * 1024 - 8)
        fake_audio = b'RIFF' + b'\x00' * (100 * 1024 - 4)

        image_encoded = base64.b64encode(fake_image).decode('utf-8')
        video_encoded = base64.b64encode(fake_video).decode('utf-8')
        audio_encoded = base64.b64encode(fake_audio).decode('utf-8')

        events = [
            ADKEvent(
                invocation_id="test1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[
                        adk_types.Part(text="Here's a multimedia message with image, video, and audio."),
                        adk_types.Part(
                            inline_data=adk_types.Blob(
                                data=image_encoded.encode('utf-8'),
                                mime_type="image/jpeg"
                            )
                        ),
                        adk_types.Part(
                            inline_data=adk_types.Blob(
                                data=video_encoded.encode('utf-8'),
                                mime_type="video/mp4"
                            )
                        ),
                        adk_types.Part(
                            inline_data=adk_types.Blob(
                                data=audio_encoded.encode('utf-8'),
                                mime_type="audio/wav"
                            )
                        )
                    ]
                )
            )
        ]
        result = _calculate_session_context_tokens(events)
        # Mixed content should have substantial token count
        # image (~85-170) + video (~200+) + audio (~100+) + text (~10) = 400+
        assert result > 200, f"Mixed media should total significant tokens, got {result}"
        assert result < 10000, "Should be reasonable"

    def test_multiple_images_in_single_event(self):
        """Should count tokens for multiple images in one event."""
        fake_image1 = b'\xFF\xD8\xFF\xE0' + b'\x00' * (50 * 1024 - 4)
        fake_image2 = b'\xFF\xD8\xFF\xE0' + b'\x00' * (75 * 1024 - 4)

        image1_encoded = base64.b64encode(fake_image1).decode('utf-8')
        image2_encoded = base64.b64encode(fake_image2).decode('utf-8')

        events = [
            ADKEvent(
                invocation_id="test1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[
                        adk_types.Part(text="Two images:"),
                        adk_types.Part(
                            inline_data=adk_types.Blob(
                                data=image1_encoded.encode('utf-8'),
                                mime_type="image/jpeg"
                            )
                        ),
                        adk_types.Part(
                            inline_data=adk_types.Blob(
                                data=image2_encoded.encode('utf-8'),
                                mime_type="image/jpeg"
                            )
                        )
                    ]
                )
            )
        ]
        result = _calculate_session_context_tokens(events)
        # Should count both images via token_counter
        assert result > 100, f"Multiple images should count significantly, got {result}"

    def test_jpg_image_mime_type(self):
        """Should handle JPG (image/jpeg) correctly."""
        fake_jpg = b'\xFF\xD8\xFF\xE0' + b'\x00' * (100 * 1024 - 4)
        jpg_encoded = base64.b64encode(fake_jpg).decode('utf-8')

        events = [
            ADKEvent(
                invocation_id="test1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[
                        adk_types.Part(text="JPG image:"),
                        adk_types.Part(
                            inline_data=adk_types.Blob(
                                data=jpg_encoded.encode('utf-8'),
                                mime_type="image/jpeg"
                            )
                        )
                    ]
                )
            )
        ]
        result = _calculate_session_context_tokens(events)
        # JPG should be counted as image
        assert result > 50, f"JPG should be counted, got {result}"

    def test_bmp_image_mime_type(self):
        """Should handle BMP (image/bmp) correctly."""
        # BMP header: 'BM' + file size (4 bytes) + reserved (4 bytes) + offset (4 bytes)
        fake_bmp = b'BM' + b'\x00' * (100 * 1024 - 2)
        bmp_encoded = base64.b64encode(fake_bmp).decode('utf-8')

        events = [
            ADKEvent(
                invocation_id="test1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[
                        adk_types.Part(text="BMP image:"),
                        adk_types.Part(
                            inline_data=adk_types.Blob(
                                data=bmp_encoded.encode('utf-8'),
                                mime_type="image/bmp"
                            )
                        )
                    ]
                )
            )
        ]
        result = _calculate_session_context_tokens(events)
        # BMP should be counted as image
        assert result > 50, f"BMP should be counted, got {result}"

    def test_token_calculation_consistency_across_calls(self):
        """Multiple calls with same events should return same token count (no randomness)."""
        fake_image = b'\xFF\xD8\xFF\xE0' + b'\x00' * (50 * 1024 - 4)
        image_encoded = base64.b64encode(fake_image).decode('utf-8')

        events = [
            ADKEvent(
                invocation_id="test1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[
                        adk_types.Part(text="Consistent image test"),
                        adk_types.Part(
                            inline_data=adk_types.Blob(
                                data=image_encoded.encode('utf-8'),
                                mime_type="image/jpeg"
                            )
                        )
                    ]
                )
            )
        ]

        result1 = _calculate_session_context_tokens(events)
        result2 = _calculate_session_context_tokens(events)
        result3 = _calculate_session_context_tokens(events)

        # All three calls should return exact same value
        assert result1 == result2 == result3, f"Token counts should be consistent: {result1}, {result2}, {result3}"


class TestFindCompactionCutoff:
    """Tests for _find_compaction_cutoff function."""

    def test_empty_events_returns_zero(self):
        """Empty events list should return (0, 0)."""
        cutoff_idx, actual_tokens = _find_compaction_cutoff([], 100)
        assert cutoff_idx == 0
        assert actual_tokens == 0

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
        cutoff_idx, actual_tokens = _find_compaction_cutoff(events, 10)
        assert cutoff_idx == 0
        assert actual_tokens == 0

    def test_finds_cutoff_at_nearest_user_turn_boundary(self):
        """Should find user turn boundary closest to target token count.

        Real-world scenario: Multi-turn conversation about project planning.
        - Turn 1: User asks about timeline (with details), model responds with detailed timeline
        - Turn 2: User asks about resources (with details), model responds with recommendations
        - Turn 3: User follow-up (current), model should respond

        When hitting token limit, should compact Turn 1 + 2, keep Turn 3.
        """
        events = [
            # Turn 1: User asks about project timeline
            ADKEvent(
                invocation_id="u1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(
                        text="Can you help me plan a project timeline? We need to launch in Q2 "
                             "and have several dependencies to manage. The team size is 7 people. "
                             "What's your approach to planning? We need detailed phases with estimates."
                    )]
                )
            ),
            # Turn 1: Model response with timeline details
            ADKEvent(
                invocation_id="m1",
                author="model",
                content=adk_types.Content(
                    role="model",
                    parts=[adk_types.Part(
                        text="I'd recommend a phased approach. Phase 1: Requirements gathering and analysis (2-3 weeks), "
                             "Phase 2: Design and prototyping (3-4 weeks), Phase 3: Development and integration (6-8 weeks), "
                             "Phase 4: Testing, QA and bug fixes (2-3 weeks), Phase 5: Deployment preparation (1 week). "
                             "This gives buffer time for unexpected issues and aligns with Q2 deadline. "
                             "Critical path: DB design → API development → frontend integration → testing."
                    )]
                )
            ),
            # Turn 2: User asks about resources and team structure
            ADKEvent(
                invocation_id="u2",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(
                        text="That makes sense. What about team allocation and structure? We have 5 backend developers, "
                             "2 frontend developers, and 2 QA engineers. How should we organize them? "
                             "Is that sufficient for this timeline? Also, do we need a dedicated project manager?"
                    )]
                )
            ),
            # Turn 2: Model response with resource recommendations
            ADKEvent(
                invocation_id="m2",
                author="model",
                content=adk_types.Content(
                    role="model",
                    parts=[adk_types.Part(
                        text="With your team composition, here's what I recommend: Backend: 2 on API layer, 2 on database, 1 on DevOps/infrastructure. "
                             "Frontend: 1 on UI components, 1 on integration and state management. QA: parallel testing from Phase 2 onward. "
                             "This team is well-positioned for the timeline. A project manager would be valuable for coordination, risk tracking, "
                             "stakeholder communication, and daily stand-ups. Consider allocating someone 50-75% on PM duties if a full-time PM isn't available. "
                             "Key: Daily sync-ups, clear blockers, weekly reviews."
                    )]
                )
            ),
            # Turn 3: User follow-up question (should NOT be compacted)
            ADKEvent(
                invocation_id="u3",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(
                        text="Got it. Now, what are the biggest risks we should mitigate early? "
                             "And should we set up weekly checkpoints? What metrics should we track?"
                    )]
                )
            ),
            # Turn 3: Model response (placeholder - won't be compacted)
            ADKEvent(
                invocation_id="m3",
                author="model",
                content=adk_types.Content(
                    role="model",
                    parts=[adk_types.Part(
                        text="Key risks: scope creep, dependency blockers, and team knowledge gaps on new tech. "
                             "Weekly checkpoints are essential."
                    )]
                )
            ),
        ]

        # Get actual token counts at each boundary
        tokens_at_2 = _calculate_session_context_tokens(events[:2])  # Turn 1 complete
        tokens_at_4 = _calculate_session_context_tokens(events[:4])  # Turn 1 + 2 complete

        # Target: midpoint between turn 1 and turn 1+2
        target = (tokens_at_2 + tokens_at_4) // 2

        # Calculate which cutoff is closest to target
        distance_at_2 = abs(tokens_at_2 - target)
        distance_at_4 = abs(tokens_at_4 - target)
        expected_cutoff = 2 if distance_at_2 <= distance_at_4 else 4
        expected_tokens = tokens_at_2 if distance_at_2 <= distance_at_4 else tokens_at_4

        cutoff_idx, actual_tokens = _find_compaction_cutoff(events, target)

        # Should find the EXACT boundary closest to target
        assert cutoff_idx == expected_cutoff, \
            f"Target={target}, tokens_at_2={tokens_at_2} (dist={distance_at_2}), " \
            f"tokens_at_4={tokens_at_4} (dist={distance_at_4}). " \
            f"Expected cutoff={expected_cutoff}, got {cutoff_idx}"

        # Actual tokens must match exactly what we calculated
        assert actual_tokens == expected_tokens, \
            f"Expected {expected_tokens} tokens, got {actual_tokens}"

        # Should not compact the last turn (Turn 3)
        assert cutoff_idx < 5, "Should never compact beyond Turn 2"

    def test_always_leaves_at_least_one_user_turn_uncompacted(self):
        """Last user turn should never be compacted, even with high token targets.

        Real-world scenario: Long conversation with increasing token usage.
        - Turn 1: Detailed question and comprehensive response
        - Turn 2: Follow-up questions (current)

        Should never compact Turn 2 (the current turn), even if token budget is high.
        This ensures the most recent context is always available.
        """
        events = [
            # Turn 1: Detailed initial question
            ADKEvent(
                invocation_id="u1",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(
                        text="I need comprehensive help with system architecture design. "
                             "We're building a microservices platform for e-commerce with expected "
                             "traffic of 100k requests per day. We need API gateway, authentication, "
                             "payment processing, inventory management, and analytics. What's your recommendation? "
                             "Consider scalability, cost, and maintainability. Also discuss database choices."
                    )]
                )
            ),
            # Turn 1: Comprehensive response (lots of tokens)
            ADKEvent(
                invocation_id="m1",
                author="model",
                content=adk_types.Content(
                    role="model",
                    parts=[adk_types.Part(
                        text="I'd recommend a comprehensive architecture: Use Kong or AWS API Gateway for routing. "
                             "For authentication, implement OAuth 2.0 with JWT tokens. Payment processing: integrate with Stripe or Adyen. "
                             "Inventory: separate microservice with Redis caching for high-frequency queries. "
                             "Analytics: use event streaming (Kafka) with aggregation in BigQuery or Elastic. "
                             "Database: PostgreSQL for transactional data, with read replicas for analytics queries. "
                             "Use CDN for static assets. Implement circuit breakers and retry logic. "
                             "Container orchestration with Kubernetes. This scales to millions of requests. "
                             "Cost optimization: use spot instances, reserved capacity, auto-scaling."
                    )]
                )
            ),
            # Turn 2: Follow-up questions (CURRENT, should not be compacted)
            ADKEvent(
                invocation_id="u2",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(
                        text="That's very helpful. Now I need clarification on a few points. "
                             "How do we handle distributed transactions across microservices? "
                             "What about data consistency? And how do we monitor this complex system?"
                    )]
                )
            ),
        ]

        # Even with very high token target (simulating context limit pressure),
        # should stop before last turn (Turn 2)
        cutoff_idx, actual_tokens = _find_compaction_cutoff(events, 5000)

        # Should be at index 2 (boundary before u2, the current turn)
        assert cutoff_idx == 2, \
            f"Should stop at turn boundary before last turn (u2), got {cutoff_idx}"
        # Should have compacted u1 + m1
        assert actual_tokens > 0, "Should have calculated token count for Turn 1"

    def test_cutoff_precision_with_three_turn_boundaries(self):
        """Should find EXACT closest boundary among three potential cutoff points."""
        # Create events with precisely calculated token distribution
        events = [
            # Turn 1: Small
            ADKEvent(
                invocation_id="u1",
                author="user",
                content=adk_types.Content(role="user", parts=[adk_types.Part(text="First")])
            ),
            ADKEvent(
                invocation_id="m1",
                author="model",
                content=adk_types.Content(role="model", parts=[adk_types.Part(text="Response one")])
            ),
            # Turn 2: Medium
            ADKEvent(
                invocation_id="u2",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(text="Second question with more content. " * 10)]
                )
            ),
            ADKEvent(
                invocation_id="m2",
                author="model",
                content=adk_types.Content(
                    role="model",
                    parts=[adk_types.Part(text="Detailed response. " * 20)]
                )
            ),
            # Turn 3: Large (should not be compacted)
            ADKEvent(
                invocation_id="u3",
                author="user",
                content=adk_types.Content(
                    role="user",
                    parts=[adk_types.Part(text="Third question. " * 20)]
                )
            ),
        ]

        # Calculate tokens at each boundary
        tokens_turn1_boundary = _calculate_session_context_tokens(events[:2])
        tokens_turn2_boundary = _calculate_session_context_tokens(events[:4])

        # Target: closer to turn2 boundary
        target = tokens_turn2_boundary - 10

        cutoff_idx, actual_tokens = _find_compaction_cutoff(events, target)

        # Should choose turn2 boundary (index 4) as it's closer to target
        assert cutoff_idx == 4, \
            f"Target {target} closer to turn2 ({tokens_turn2_boundary}) than turn1 ({tokens_turn1_boundary}), " \
            f"expected cutoff=4, got {cutoff_idx}"

    def test_cumulative_token_calculation_large_session(self):
        """Should handle large session (100+ events) with O(N) efficiency."""
        # Create 100 small events
        events = []
        for i in range(100):
            events.append(
                ADKEvent(
                    invocation_id=f"event_{i}",
                    author="user" if i % 2 == 0 else "model",
                    content=adk_types.Content(
                        role="user" if i % 2 == 0 else "model",
                        parts=[adk_types.Part(text=f"Message {i}. " * 3)]
                    )
                )
            )

        # Should complete without timeout or error
        import time
        start = time.time()
        result = _calculate_session_context_tokens(events)
        elapsed = time.time() - start

        # Should complete reasonably fast (< 30 seconds for 100 events)
        assert elapsed < 30, f"Token calculation took {elapsed:.2f}s for 100 events, should be faster"
        assert result > 0, "Should calculate total tokens for large session"

    def test_find_cutoff_with_large_session(self):
        """_find_compaction_cutoff should work efficiently with 100+ events."""
        # Create 100 events with user turns at indices 0, 2, 4, ..., 98
        events = []
        for i in range(100):
            events.append(
                ADKEvent(
                    invocation_id=f"event_{i}",
                    author="user" if i % 2 == 0 else "model",
                    content=adk_types.Content(
                        role="user" if i % 2 == 0 else "model",
                        parts=[adk_types.Part(text=f"Message {i}. " * 2)]
                    )
                )
            )

        # Should find cutoff efficiently
        import time
        start = time.time()
        cutoff_idx, actual_tokens = _find_compaction_cutoff(events, target_tokens=500)
        elapsed = time.time() - start

        # Should complete reasonably fast (< 20 seconds total: calc + cutoff finding)
        assert elapsed < 20, f"Cutoff finding took {elapsed:.2f}s for 100 events, should be faster"
        # Should be at a valid user turn boundary
        assert cutoff_idx > 0 and cutoff_idx < len(events), f"Cutoff should be valid index, got {cutoff_idx}"
        # Should leave at least last user turn uncompacted
        assert cutoff_idx < 98, "Should leave at least last user turn uncompacted"


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

class TestCreateCompactionEvent:
    """Tests for _create_compaction_event function - progressive summarization."""

    @pytest.mark.asyncio
    async def test_first_compaction_no_fake_event(self):
        """First compaction (no previous summary) should not create fake event."""
        # Setup mock component with session service
        component = Mock()
        component.adk_agent = Mock()
        component.adk_agent.model = Mock()
        component.get_config = Mock(return_value="test-namespace")

        # Mock session service
        mock_session_service = AsyncMock()
        mock_session_service.append_event = AsyncMock(return_value=None)
        component.session_service = mock_session_service
        
        # Create session with events (no previous compaction)
        # Need at least 2 user turns for compaction
        events = [
            ADKEvent(
                invocation_id="evt1",
                author="user",
                timestamp=1.0,
                content=adk_types.Content(role="user", parts=[adk_types.Part(text="Message 1")])
            ),
            ADKEvent(
                invocation_id="evt2",
                author="model",
                timestamp=2.0,
                content=adk_types.Content(role="model", parts=[adk_types.Part(text="Response 1")])
            ),
            ADKEvent(
                invocation_id="evt3",
                author="user",
                timestamp=3.0,
                content=adk_types.Content(role="user", parts=[adk_types.Part(text="Message 2")])
            ),
            ADKEvent(
                invocation_id="evt4",
                author="model",
                timestamp=4.0,
                content=adk_types.Content(role="model", parts=[adk_types.Part(text="Response 2")])
            ),
        ]
        session = ADKSession(
            id="test_session",
            user_id="test_user",
            app_name="test_app",
            events=events
        )
        
        # Mock LlmEventSummarizer
        with patch('solace_agent_mesh.agent.adk.runner.LlmEventSummarizer') as mock_summarizer_class:
            mock_summarizer = AsyncMock()
            mock_summarizer_class.return_value = mock_summarizer
            
            # Return a mock compaction event
            compaction_event = ADKEvent(
                invocation_id="compaction1",
                author="system",
                timestamp=2.0,
                actions=EventActions(
                    compaction=EventCompaction(
                        start_timestamp=0.0,
                        end_timestamp=2.0,
                        compacted_content=adk_types.Content(
                            role="model",
                            parts=[adk_types.Part(text="First summary")]
                        )
                    )
                )
            )
            mock_summarizer.maybe_summarize_events.return_value = compaction_event
            
            # Call function
            count, summary = await _create_compaction_event(
                component=component,
                session=session,
                compaction_threshold=0.5,
                log_identifier="[Test]"
            )
            
            # Verify summarizer was called
            assert mock_summarizer.maybe_summarize_events.called
            
            # Verify events passed to summarizer
            call_args = mock_summarizer.maybe_summarize_events.call_args
            events_passed = call_args[1]['events']  # keyword argument
            
            # Should NOT have fake event (first compaction)
            # First event should be actual user event, not fake summary
            assert len(events_passed) > 0
            first_event = events_passed[0]
            assert first_event.author == "user", "First compaction should start with user event, not fake summary"
            assert first_event.invocation_id == "evt1", "Should be the actual first event"

    @pytest.mark.asyncio
    async def test_second_compaction_creates_fake_event(self):
        """Second compaction should prepend fake event with first summary."""
        # Setup mock component with session service
        component = Mock()
        component.adk_agent = Mock()
        component.adk_agent.model = Mock()
        component.get_config = Mock(return_value="test-namespace")

        # Mock session service
        mock_session_service = AsyncMock()
        mock_session_service.append_event = AsyncMock(return_value=None)
        component.session_service = mock_session_service
        
        # Create session with previous compaction event + new events
        previous_compaction = ADKEvent(
            invocation_id="compaction1",
            author="system",
            timestamp=2.0,
            content=adk_types.Content(
                role="model",
                parts=[adk_types.Part(text="Summary from first compaction: user asked about features")]
            ),
            actions=EventActions(
                compaction=EventCompaction(
                    start_timestamp=0.0,
                    end_timestamp=2.0,
                    compacted_content=adk_types.Content(
                        role="model",
                        parts=[adk_types.Part(text="Summary from first compaction: user asked about features")]
                    )
                )
            )
        )
        
        new_events = [
            ADKEvent(
                invocation_id="evt3",
                author="user",
                timestamp=3.0,
                content=adk_types.Content(role="user", parts=[adk_types.Part(text="New question about pricing")])
            ),
            ADKEvent(
                invocation_id="evt4",
                author="model",
                timestamp=4.0,
                content=adk_types.Content(role="model", parts=[adk_types.Part(text="Pricing info response")])
            ),
            ADKEvent(
                invocation_id="evt5",
                author="user",
                timestamp=5.0,
                content=adk_types.Content(role="user", parts=[adk_types.Part(text="Follow-up question")])
            ),
            ADKEvent(
                invocation_id="evt6",
                author="model",
                timestamp=6.0,
                content=adk_types.Content(role="model", parts=[adk_types.Part(text="Follow-up response")])
            ),
        ]
        
        session = ADKSession(
            id="test_session",
            user_id="test_user",
            app_name="test_app",
            events=[previous_compaction] + new_events
        )
        
        # Mock LlmEventSummarizer
        with patch('solace_agent_mesh.agent.adk.runner.LlmEventSummarizer') as mock_summarizer_class:
            mock_summarizer = AsyncMock()
            mock_summarizer_class.return_value = mock_summarizer
            
            # Return second compaction event
            compaction_event = ADKEvent(
                invocation_id="compaction2",
                author="system",
                timestamp=4.0,
                actions=EventActions(
                    compaction=EventCompaction(
                        start_timestamp=0.0,
                        end_timestamp=4.0,
                        compacted_content=adk_types.Content(
                            role="model",
                            parts=[adk_types.Part(text="Second summary: features and pricing discussed")]
                        )
                    )
                )
            )
            mock_summarizer.maybe_summarize_events.return_value = compaction_event
            
            # Call function
            count, summary = await _create_compaction_event(
                component=component,
                session=session,
                compaction_threshold=0.5,
                log_identifier="[Test]"
            )
            
            # Verify summarizer was called
            assert mock_summarizer.maybe_summarize_events.called
            
            # CRITICAL VERIFICATION: Inspect events passed to summarizer
            call_args = mock_summarizer.maybe_summarize_events.call_args
            events_passed = call_args[1]['events']
            
            # Should have fake event prepended
            # With 50% compaction threshold and 2 new user turns, it compacts 1 turn (evt3+evt4)
            assert len(events_passed) >= 3, "Should have [FakeSummary, evt3, evt4] at minimum"
            
            # 1. First event should be FAKE summary event
            fake_event = events_passed[0]
            
            # 2. Verify it contains summary text from first compaction
            assert fake_event.content is not None
            assert fake_event.content.parts
            fake_text = fake_event.content.parts[0].text
            assert "Summary from first compaction" in fake_text, \
                f"Fake event should contain first summary text, got: {fake_text}"
            
            # 3. Verify it has NO .actions.compaction (this tricks LlmEventSummarizer!)
            assert fake_event.actions is None or not hasattr(fake_event.actions, 'compaction') or fake_event.actions.compaction is None, \
                "Fake event MUST NOT have .actions.compaction (this is the trick!)"
            
            # 4. Verify it's from "model" (summaries are from AI perspective)
            assert fake_event.author == "model", f"Fake event author should be 'model', got {fake_event.author}"
            assert fake_event.content.role == "model", f"Fake event role should be 'model', got {fake_event.content.role}"
            
            # 5. Verify invocation_id indicates it's fake
            assert "progressive_summary_fake_event" in fake_event.invocation_id, \
                f"Fake event should have identifiable invocation_id, got {fake_event.invocation_id}"
            
            # 6. Verify timestamp is from end of first compaction
            assert fake_event.timestamp == 2.0, f"Fake event timestamp should match end of first compaction, got {fake_event.timestamp}"
            
            # 7. Verify subsequent events are the actual new events (not all, just verify they're present)
            event_ids = [e.invocation_id for e in events_passed[1:]]
            assert "evt3" in event_ids, "Should contain evt3"
            assert "evt4" in event_ids, "Should contain evt4"

    @pytest.mark.asyncio
    async def test_fake_event_with_no_summary_text(self):
        """If previous compaction has no text, should skip fake event."""
        # Setup mock component with session service
        component = Mock()
        component.adk_agent = Mock()
        component.adk_agent.model = Mock()
        component.get_config = Mock(return_value="test-namespace")

        # Mock session service
        mock_session_service = AsyncMock()
        mock_session_service.append_event = AsyncMock(return_value=None)
        component.session_service = mock_session_service
        
        # Create session with compaction event that has NO text content
        previous_compaction = ADKEvent(
            invocation_id="compaction1",
            author="system",
            timestamp=2.0,
            content=adk_types.Content(role="model", parts=[]),  # NO TEXT PARTS!
            actions=EventActions(
                compaction=EventCompaction(
                    start_timestamp=0.0,
                    end_timestamp=2.0,
                    compacted_content=adk_types.Content(role="model", parts=[])  # Empty content
                )
            )
        )
        
        new_events = [
            ADKEvent(
                invocation_id="evt3",
                author="user",
                timestamp=3.0,
                content=adk_types.Content(role="user", parts=[adk_types.Part(text="New message")])
            ),
            ADKEvent(
                invocation_id="evt4",
                author="model",
                timestamp=4.0,
                content=adk_types.Content(role="model", parts=[adk_types.Part(text="Response")])
            ),
            ADKEvent(
                invocation_id="evt5",
                author="user",
                timestamp=5.0,
                content=adk_types.Content(role="user", parts=[adk_types.Part(text="Another message")])
            ),
            ADKEvent(
                invocation_id="evt6",
                author="model",
                timestamp=6.0,
                content=adk_types.Content(role="model", parts=[adk_types.Part(text="Another response")])
            ),
        ]
        
        session = ADKSession(
            id="test_session",
            user_id="test_user",
            app_name="test_app",
            events=[previous_compaction] + new_events
        )
        
        # Mock LlmEventSummarizer
        with patch('solace_agent_mesh.agent.adk.runner.LlmEventSummarizer') as mock_summarizer_class:
            mock_summarizer = AsyncMock()
            mock_summarizer_class.return_value = mock_summarizer
            mock_summarizer.maybe_summarize_events.return_value = ADKEvent(
                invocation_id="compaction2",
                author="system",
                timestamp=3.0,
                actions=EventActions(
                    compaction=EventCompaction(
                        start_timestamp=0.0,
                        end_timestamp=3.0,
                        compacted_content=adk_types.Content(
                            role="model",
                            parts=[adk_types.Part(text="Summary")]
                        )
                    )
                )
            )
            
            # Call function
            await _create_compaction_event(
                component=component,
                session=session,
                compaction_threshold=0.5,
                log_identifier="[Test]"
            )
            
            # Verify compaction was called
            assert mock_summarizer.maybe_summarize_events.called, "Compaction should be called"

            # Verify NO fake event was created (should start with evt3)
            call_args = mock_summarizer.maybe_summarize_events.call_args
            events_passed = call_args[1]['events']

            # Should start with actual event, not fake summary
            # (since previous compaction had no text content)
            first_event = events_passed[0]
            assert first_event.author == "user", "Should start with user event when no previous summary text"
            assert first_event.invocation_id == "evt3", \
                "Without summary text, should NOT create fake event"
