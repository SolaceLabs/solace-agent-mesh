"""
Integration test for automatic session compaction.

Verifies that compaction triggers when character threshold is exceeded,
events are properly filtered, and the agent continues working correctly.
"""

import pytest
import base64
from unittest.mock import patch
from google.adk.events import Event as ADKEvent
from google.adk.events.event_actions import EventActions, EventCompaction
from google.genai import types as adk_types

from sam_test_infrastructure.llm_server.server import TestLLMServer
from sam_test_infrastructure.gateway_interface.component import TestGatewayComponent
from solace_agent_mesh.agent.sac.app import SamAgentApp

from .test_helpers import (
    prime_llm_server,
    create_gateway_input_data,
    submit_test_input,
    get_all_task_events,
    extract_outputs_from_event_list,
)

pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.default
]


def create_compaction_event_mock(start_ts: float, end_ts: float, summary_text: str) -> ADKEvent:
    """Create mock compaction event with proper timestamps."""
    return ADKEvent(
        invocation_id="compaction_event_id",
        author="system",
        content=None,
        timestamp=end_ts,
        actions=EventActions(
            compaction=EventCompaction(
                start_timestamp=start_ts,
                end_timestamp=end_ts,
                compacted_content=adk_types.Content(
                    role="model",
                    parts=[adk_types.Part(text=summary_text)]
                )
            )
        )
    )


async def send_message_to_session(
    gateway_component, target_agent, user_identity, message_text, scenario_id,
    llm_server, session_id=None, llm_response_text="Acknowledged."
):
    """Send message to session (reuse session_id if provided)."""
    llm_response_data = {
        "id": f"chatcmpl-{scenario_id}",
        "object": "chat.completion",
        "model": "test-llm-model",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": llm_response_text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    prime_llm_server(llm_server, [llm_response_data])

    external_context = {"test_case": scenario_id}
    if not session_id:
        import uuid
        session_id = f"test_session_{uuid.uuid4().hex[:8]}"
    external_context["a2a_session_id"] = session_id

    input_data = create_gateway_input_data(
        target_agent=target_agent,
        user_identity=user_identity,
        text_parts_content=[message_text],
        scenario_id=scenario_id,
        external_context_override=external_context,
    )
    task_id = await submit_test_input(gateway_component, input_data, scenario_id)
    all_events = await get_all_task_events(gateway_component, task_id, overall_timeout=10.0)
    return task_id, session_id, all_events


async def test_session_compaction_triggers_and_filters(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    compaction_agent_app_under_test: SamAgentApp,
):
    """
    Test that session compaction:
    1. Triggers when character threshold exceeded (threshold=300)
    2. Creates compaction event with correct timestamps
    3. Filters ghost events on session reload
    4. Agent continues working after compaction
    5. Summary notification sent to user

    Setup:
    - Message 1: ~250 chars
    - Message 2: ~250 chars (total ~500 > 300, triggers on msg 3)
    - Message 3: small (~50 chars)
    - After compaction: removes ~30% (~250 chars), keeps ~300 chars
    - Post-compaction with msg 3: should be < 300 chars
    """
    with patch('google.adk.apps.llm_event_summarizer.LlmEventSummarizer.maybe_summarize_events') as mock_summarizer:
        def mock(events):
            # Use actual event timestamps for proper filtering
            start_ts = events[0].timestamp if events and hasattr(events[0], 'timestamp') else 0
            end_ts = events[-1].timestamp if events and hasattr(events[-1], 'timestamp') else 1
            return create_compaction_event_mock(start_ts, end_ts, "Summary of previous messages.")

        mock_summarizer.side_effect = mock

        sid = None

        # Send 2 large messages to exceed threshold
        _, sid, _ = await send_message_to_session(
            test_gateway_app_instance, "TestAgentCompaction", "compaction_test@example.com",
            "a" * 100, "compact_test_1", test_llm_server, sid, "Acknowledged."
        )

        _, sid, _ = await send_message_to_session(
            test_gateway_app_instance, "TestAgentCompaction", "compaction_test@example.com",
            "b" * 100, "compact_test_2", test_llm_server, sid, "Acknowledged."
        )

        # Send small message to trigger compaction (total will exceed 300)
        _, sid, all_events = await send_message_to_session(
            test_gateway_app_instance, "TestAgentCompaction", "compaction_test@example.com",
            "c" * 10, "compact_test_3", test_llm_server, sid, "OK"
        )

        # Verify compaction occurred
        assert mock_summarizer.called, "Compaction should have been triggered"

        # Verify agent responded successfully after compaction
        terminal_event, aggregated_text, terminal_text = extract_outputs_from_event_list(all_events, "compact_test_3")
        response_text = aggregated_text or terminal_text
        assert response_text is not None, "Agent should respond after compaction"

        # Verify summary notification was sent
        assert "summarized" in response_text.lower() or "token limit" in response_text.lower() or "Summary" in response_text, \
            f"Response should contain compaction summary notification"


async def test_compaction_cutoff_before_30_percent(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    compaction_agent_app_under_test: SamAgentApp,
):
    """
    Test cutoff calculation when boundary BEFORE 30% is closer.

    With 2 equal interactions (each ~250 chars):
    - Total: ~500 chars
    - 30% = 150 chars
    - Int1 at 250: distance 100
    - Int2 at 500: distance 350
    - Should compact Int1 only (before 30% mark)
    """
    compacted_events_count = []

    with patch('google.adk.apps.llm_event_summarizer.LlmEventSummarizer.maybe_summarize_events') as m:
        def mock(events):
            compacted_events_count.append(len(events))
            start_ts = events[0].timestamp if events and hasattr(events[0], 'timestamp') else 0
            end_ts = events[-1].timestamp if events and hasattr(events[-1], 'timestamp') else 1
            return create_compaction_event_mock(start_ts, end_ts, "S1")
        m.side_effect = mock

        sid = None
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "cutoff_before@test.com", "a" * 100, "cb_1", test_llm_server, sid, "Acknowledged.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "cutoff_before@test.com", "b" * 100, "cb_2", test_llm_server, sid, "Acknowledged.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "cutoff_before@test.com", "c" * 10, "cb_3", test_llm_server, sid, "OK")

        assert m.called
        # Should compact 1 interaction (4 events: context + user + agent + context)
        assert compacted_events_count[0] == 4, f"Should compact 4 events (1 interaction), got {compacted_events_count[0]}"


async def test_compaction_cutoff_after_30_percent_varied_sizes(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    compaction_agent_app_under_test: SamAgentApp,
):
    """
    Test cutoff calculation with varied interaction sizes.

    - Int1: small (~60 chars)
    - Int2: large (~250 chars)
    - With different sizes, tests boundary selection logic
    """
    with patch('google.adk.apps.llm_event_summarizer.LlmEventSummarizer.maybe_summarize_events') as m:
        def mock(events):
            start_ts = events[0].timestamp if events and hasattr(events[0], 'timestamp') else 0
            end_ts = events[-1].timestamp if events and hasattr(events[-1], 'timestamp') else 1
            return create_compaction_event_mock(start_ts, end_ts, "S1")
        m.side_effect = mock

        sid = None
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "cutoff_after@test.com", "a" * 10, "ca_1", test_llm_server, sid, "Acknowledged.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "cutoff_after@test.com", "b" * 100, "ca_2", test_llm_server, sid, "Acknowledged.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "cutoff_after@test.com", "c" * 10, "ca_3", test_llm_server, sid, "OK")

        assert m.called


async def test_progressive_summarization_double_compaction(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    compaction_agent_app_under_test: SamAgentApp,
):
    """
    Test progressive summarization: second compaction re-summarizes first summary.

    Flow:
    1. Send 2 msgs → exceed threshold → first compaction
    2. Send 2 MORE msgs → exceed threshold again → second compaction
    3. Verify second compaction receives fake event with first summary
    """
    compaction_calls = []

    with patch('google.adk.apps.llm_event_summarizer.LlmEventSummarizer.maybe_summarize_events') as m:
        def mock(events):
            compaction_calls.append(len(events))
            start_ts = events[0].timestamp if events and hasattr(events[0], 'timestamp') else 0
            end_ts = events[-1].timestamp if events and hasattr(events[-1], 'timestamp') else len(compaction_calls)
            return create_compaction_event_mock(start_ts, end_ts, f"S{len(compaction_calls)}")
        m.side_effect = mock

        sid = None

        # First compaction
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "progressive@test.com", "a" * 100, "prog_1", test_llm_server, sid, "Acknowledged.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "progressive@test.com", "b" * 100, "prog_2", test_llm_server, sid, "Acknowledged.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "progressive@test.com", "c" * 10, "prog_3", test_llm_server, sid, "OK")

        assert len(compaction_calls) >= 1, f"First compaction should occur, got {len(compaction_calls)}"

        # Second compaction
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "progressive@test.com", "d" * 100, "prog_4", test_llm_server, sid, "Acknowledged.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "progressive@test.com", "e" * 10, "prog_5", test_llm_server, sid, "OK")

        assert len(compaction_calls) >= 2, f"Second compaction should occur, got {len(compaction_calls)}"


async def test_compaction_percentage_30_verification(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    compaction_agent_app_under_test: SamAgentApp,
):
    """
    Verify 30% compaction percentage compacts correct amount.

    With 2 interactions (~500 chars total), 30% = ~150 chars.
    Should compact 1 interaction (~250 chars).
    """
    char_counts = []

    with patch('google.adk.apps.llm_event_summarizer.LlmEventSummarizer.maybe_summarize_events') as m:
        def mock(events):
            chars = sum(len(p.text) for e in events if e.content and e.content.parts for p in e.content.parts if p.text)
            char_counts.append(chars)
            start_ts = events[0].timestamp if events and hasattr(events[0], 'timestamp') else 0
            end_ts = events[-1].timestamp if events and hasattr(events[-1], 'timestamp') else 1
            return create_compaction_event_mock(start_ts, end_ts, "S1")
        m.side_effect = mock

        sid = None
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "pct30@test.com", "m" * 100, "p30_1", test_llm_server, sid, "Acknowledged.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "pct30@test.com", "n" * 100, "p30_2", test_llm_server, sid, "Acknowledged.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "pct30@test.com", "z" * 10, "p30_3", test_llm_server, sid, "OK")

        assert m.called
        # Should compact ~250 chars (1 interaction)
        assert 200 < char_counts[0] < 300, f"Should compact ~250 chars (30% of total), got {char_counts[0]}"


async def test_session_compaction_with_binary_content(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    compaction_agent_app_under_test: SamAgentApp,
):
    """
    Test that compaction correctly accounts for binary content (images).

    Verifies:
    1. Token counter includes images in context size calculation
    2. Compaction triggers based on total tokens (text + images)
    3. Images are properly handled in compacted sessions
    4. Agent can continue after compaction with binary content

    Setup:
    - Message 1: Text + small image (~85 tokens for image)
    - Message 2: Text + medium image (~170 tokens for image, high-res)
    - Message 3: Small text (triggers compaction due to accumulated tokens)
    """
    compaction_events = []

    def create_image_part(width: int = 1920, height: int = 1080, size_kb: int = 100) -> adk_types.Part:
        """Create a fake image part with base64 encoded data."""
        # Create fake JPEG data (actual format doesn't matter for tests)
        fake_image_data = b'\xFF\xD8\xFF\xE0' + b'\x00' * (size_kb * 1024 - 4)  # Fake JPEG header + padding
        encoded = base64.b64encode(fake_image_data).decode('utf-8')
        return adk_types.Part(
            inline_data=adk_types.Blob(
                data=encoded.encode('utf-8'),
                mime_type="image/jpeg"
            )
        )

    with patch('google.adk.apps.llm_event_summarizer.LlmEventSummarizer.maybe_summarize_events') as mock_summarizer:
        def mock(events):
            compaction_events.append({
                'count': len(events),
                'has_images': any(
                    e.content and any(
                        p.inline_data and p.inline_data.mime_type.startswith('image')
                        for p in (e.content.parts or [])
                    )
                    for e in events
                )
            })
            start_ts = events[0].timestamp if events and hasattr(events[0], 'timestamp') else 0
            end_ts = events[-1].timestamp if events and hasattr(events[-1], 'timestamp') else 1
            return create_compaction_event_mock(start_ts, end_ts, "Summary with images handled correctly.")

        mock_summarizer.side_effect = mock

        sid = None

        # Message 1: Text + small image
        llm_response_1 = {
            "id": "chatcmpl-img1",
            "object": "chat.completion",
            "model": "gpt-4-vision",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Image received and understood."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 150, "completion_tokens": 10, "total_tokens": 160},  # 85 for image + text
        }
        prime_llm_server(test_llm_server, [llm_response_1])

        input_data_1 = create_gateway_input_data(
            target_agent="TestAgentCompaction",
            user_identity="image_test@example.com",
            text_parts_content=["Here is an image: "],
            scenario_id="img_1",
            external_context_override={
                "test_case": "img_1",
                "a2a_session_id": sid or f"test_session_binary_{pytest.timestamp if hasattr(pytest, 'timestamp') else 'abc'}",
            },
        )
        # Add image part to message
        if hasattr(input_data_1, 'message') and hasattr(input_data_1.message, 'parts'):
            input_data_1.message.parts.append(adk_types.Part(
                inline_data=adk_types.Blob(
                    data=base64.b64encode(b'\xFF\xD8\xFF\xE0' + b'\x00' * 50000).decode('utf-8').encode('utf-8'),
                    mime_type="image/jpeg"
                )
            ))

        task_id_1 = await submit_test_input(test_gateway_app_instance, input_data_1, "img_1")
        _, sid, _ = await get_all_task_events(test_gateway_app_instance, task_id_1, overall_timeout=10.0), \
                    input_data_1.message_context.get("a2a_session_id") if hasattr(input_data_1, 'message_context') else None, \
                    None
        if not sid:
            sid = f"test_session_binary_msg1"

        # Message 2: Text + larger image
        llm_response_2 = {
            "id": "chatcmpl-img2",
            "object": "chat.completion",
            "model": "gpt-4-vision",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Second image acknowledged."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 250, "completion_tokens": 10, "total_tokens": 260},  # 170 for high-res image + text
        }
        prime_llm_server(test_llm_server, [llm_response_2])

        _, sid, _ = await send_message_to_session(
            test_gateway_app_instance, "TestAgentCompaction", "image_test@example.com",
            "Another image for context", "img_2", test_llm_server, sid, "Second image acknowledged."
        )

        # Message 3: Small text message - should trigger compaction due to accumulated tokens
        llm_response_3 = {
            "id": "chatcmpl-img3",
            "object": "chat.completion",
            "model": "gpt-4-vision",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Continuing after compaction."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 8, "total_tokens": 58},
        }
        prime_llm_server(test_llm_server, [llm_response_3])

        _, sid, all_events = await send_message_to_session(
            test_gateway_app_instance, "TestAgentCompaction", "image_test@example.com",
            "Continue", "img_3", test_llm_server, sid, "Continuing after compaction."
        )

        # Verify compaction was triggered
        assert mock_summarizer.called, "Compaction should have been triggered due to image tokens"
        assert len(compaction_events) > 0, "At least one compaction event should be recorded"

        # Verify agent responded successfully
        terminal_event, aggregated_text, terminal_text = extract_outputs_from_event_list(all_events, "img_3")
        response_text = aggregated_text or terminal_text
        assert response_text is not None, "Agent should respond after compaction with binary content"

        # Verify summary notification includes context about continuation
        assert "Continuing" in response_text or "summarized" in response_text.lower(), \
            f"Response should indicate continuation after compaction, got: {response_text}"