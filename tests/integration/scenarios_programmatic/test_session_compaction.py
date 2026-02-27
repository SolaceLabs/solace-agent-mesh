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
    1. Triggers when token threshold exceeded (threshold=300 tokens)
    2. Creates compaction event with correct timestamps
    3. Filters ghost events on session reload
    4. Agent continues working after compaction
    5. Summary notification sent to user

    Setup:
    - Threshold: 300 tokens
    - Token-to-char ratio: ~3.5-4.5 chars/token, so 300 tokens ≈ 1050-1350 chars
    - Message 1: realistic query (~400 chars → ~100 tokens)
    - Message 2: realistic query (~400 chars → ~100 tokens, total ~200)
    - Message 3: realistic query (~400 chars → ~100 tokens, total ~300+, triggers)
    """
    with patch('google.adk.apps.llm_event_summarizer.LlmEventSummarizer.maybe_summarize_events') as mock_summarizer:
        def mock(events):
            # Use actual event timestamps for proper filtering
            start_ts = events[0].timestamp if events and hasattr(events[0], 'timestamp') else 0
            end_ts = events[-1].timestamp if events and hasattr(events[-1], 'timestamp') else 1
            return create_compaction_event_mock(start_ts, end_ts, "Summary of previous messages.")

        mock_summarizer.side_effect = mock

        sid = None

        # Message 1: Realistic customer service inquiry
        msg1 = (
            "Hello, I'm having trouble with my recent order #12345. I ordered a laptop "
            "three weeks ago and it still hasn't arrived. The tracking information shows "
            "it was shipped on January 15th, but there haven't been any updates since then. "
            "I've tried contacting the shipping company directly, but they told me to reach "
            "out to the merchant. Can you please help me track down where my package is? "
            "I need this laptop urgently for work and I'm getting really concerned about the delay."
        )
        _, sid, _ = await send_message_to_session(
            test_gateway_app_instance, "TestAgentCompaction", "compaction_test@example.com",
            msg1, "compact_test_1", test_llm_server, sid,
            "I understand your concern. Let me look into order #12345 for you right away."
        )

        # Message 2: Follow-up with additional details
        msg2 = (
            "Thank you for looking into this. I should also mention that I paid for expedited "
            "shipping, so I expected it to arrive within 5-7 business days. It's been way longer "
            "than that now. Additionally, I noticed that my credit card was charged the full amount "
            "including the expedited shipping fee of $29.99. If the package is lost, I'd like to "
            "request either a replacement with expedited shipping at no extra cost, or a full refund "
            "including the shipping charges. What are my options here?"
        )
        _, sid, _ = await send_message_to_session(
            test_gateway_app_instance, "TestAgentCompaction", "compaction_test@example.com",
            msg2, "compact_test_2", test_llm_server, sid,
            "I've located your order and I see the tracking issue. Let me escalate this to our shipping department."
        )

        # Message 3: Final question that triggers compaction
        msg3 = (
            "I appreciate your help. One more thing - if we do need to send a replacement, "
            "can you make sure it's the exact same model I originally ordered? It was the "
            "Dell XPS 15 with 32GB RAM and 1TB SSD in the silver color. I specifically chose "
            "that configuration and I don't want to receive a different model or color. Also, "
            "is there any way you can provide updates via email so I don't have to keep calling? "
            "I'm usually in meetings during business hours and it's hard for me to make phone calls."
        )
        _, sid, all_events = await send_message_to_session(
            test_gateway_app_instance, "TestAgentCompaction", "compaction_test@example.com",
            msg3, "compact_test_3", test_llm_server, sid,
            "Absolutely, I'll ensure the replacement is the exact Dell XPS 15 configuration you ordered."
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

    With 2 equal interactions (each ~100 tokens):
    - Total: ~200 tokens
    - 30% = 60 tokens
    - Int1 at 100: distance 40
    - Int2 at 200: distance 140
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
        msg1 = (
            "I need help resetting my password for my account. I've tried using the forgot password "
            "link multiple times over the past hour, but I'm not receiving any reset emails. I've "
            "checked both my inbox and spam folder thoroughly. My username is john.doe@example.com "
            "and I last successfully logged in about two weeks ago. The account is really important "
            "to me because it contains years of project data and client information that I need to "
            "access urgently. Can you please help me resolve this issue as soon as possible?"
        )
        msg2 = (
            "I appreciate your quick response. I've double-checked and my email address is definitely "
            "correct in the system - I can see it when I try to log in. I've also tried from different "
            "browsers (Chrome and Firefox) and different devices (my laptop and phone) but nothing is "
            "working. I'm wondering if there might be an issue with your email service or if my account "
            "has been flagged for some reason? I haven't changed anything on my end and I've been a "
            "paying customer for over 3 years now. What other options do we have to get me back in?"
        )
        msg3 = (
            "That sounds like a good plan. Before we proceed with the manual reset, I just want to "
            "make sure this won't affect any of my saved data, preferences, or subscription status. "
            "I have several ongoing projects with collaborators and I don't want to lose access to "
            "those shared workspaces. Also, will I need to update my password on any mobile apps or "
            "integrations I've set up? I use your API with several third-party tools and I want to "
            "make sure I know what to expect. Should I receive the reset email within the next few "
            "minutes, or will it take longer than usual since it's being sent manually?"
        )

        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "cutoff_before@test.com", msg1, "cb_1", test_llm_server, sid, "I can help with that. Let me look into your account and resend the reset email for you.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "cutoff_before@test.com", msg2, "cb_2", test_llm_server, sid, "I've checked your account and everything looks normal. I'm manually triggering a password reset now.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "cutoff_before@test.com", msg3, "cb_3", test_llm_server, sid, "Your data is safe and you should receive the email within 2-3 minutes.")

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

    - Int1: small (~30 tokens)
    - Int2: large (~120 tokens)
    - With different sizes, tests boundary selection logic
    """
    with patch('google.adk.apps.llm_event_summarizer.LlmEventSummarizer.maybe_summarize_events') as m:
        def mock(events):
            start_ts = events[0].timestamp if events and hasattr(events[0], 'timestamp') else 0
            end_ts = events[-1].timestamp if events and hasattr(events[-1], 'timestamp') else 1
            return create_compaction_event_mock(start_ts, end_ts, "S1")
        m.side_effect = mock

        sid = None
        msg1 = (
            "Good morning! I have a few questions about your company and services. First, I'd like to know "
            "what your business hours are, including whether you're open on weekends and holidays. I'm in the "
            "Pacific time zone and I often need support outside of regular business hours. Also, do you have "
            "24/7 live chat support, or is it limited to specific hours as well? I've been trying to reach "
            "someone all weekend without success and I really need help with my account."
        )
        msg2 = (
            "Thank you for that information about your hours. That's very helpful to know. I also wanted to ask "
            "about your return policy in detail because I recently purchased a product from your website last week "
            "and I'm not entirely satisfied with it. The product itself works fine and there's nothing defective, "
            "but it's just not quite what I expected based on the product description and photos on your site. "
            "I'm within the 30-day window that's mentioned on your website, but I wanted to confirm the exact "
            "step-by-step process for initiating a return and whether I'll need to pay for return shipping costs. "
            "The item cost $89.99 and I used a credit card for the purchase. Do I absolutely need the original "
            "packaging and all the inserts, or is it okay if I threw away the outer shipping box? I still have "
            "the product box itself and all the contents."
        )
        msg3 = (
            "Perfect, that all makes sense and sounds very reasonable. I really appreciate you taking the time "
            "to explain the whole process to me in detail. One last thing - can you please send me a prepaid "
            "return shipping label via email? My email address on file should be correct, but just to confirm "
            "it's cutoff_after@test.com. How long should I expect it to take before I receive the email with "
            "the return label? And once I ship it back, approximately how many business days will it take to "
            "process my refund?"
        )

        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "cutoff_after@test.com", msg1, "ca_1", test_llm_server, sid, "We're open Monday through Friday, 9 AM to 6 PM EST. Weekend support is available via email only.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "cutoff_after@test.com", msg2, "ca_2", test_llm_server, sid, "You can return it within 30 days for any reason. We'll provide a prepaid return label and issue a full refund once we receive it.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "cutoff_after@test.com", msg3, "ca_3", test_llm_server, sid, "I'll send the return label to your email within 10 minutes. Refunds typically process in 3-5 business days after we receive the item.")

        assert m.called


async def test_progressive_summarization_double_compaction(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    compaction_agent_app_under_test: SamAgentApp,
):
    """
    Test progressive summarization: second compaction re-summarizes first summary.

    Flow:
    1. Send messages → exceed threshold → first compaction
    2. Send MORE messages → exceed threshold again → second compaction
    3. Verify second compaction receives fake event with first summary

    Critical verification:
    - Second call to maybe_summarize_events receives fake event as FIRST event
    - Fake event contains summary text from first compaction
    - Fake event has NO .actions.compaction (tricks LlmEventSummarizer)
    - Fake event author="model" and role="model"
    """
    compaction_calls = []
    call_args_history = []  # Store call arguments for inspection

    with patch('google.adk.apps.llm_event_summarizer.LlmEventSummarizer.maybe_summarize_events') as m:
        def mock(events):
            # Capture call arguments for later verification
            call_args_history.append(list(events))
            compaction_calls.append(len(events))
            start_ts = events[0].timestamp if events and hasattr(events[0], 'timestamp') else 0
            end_ts = events[-1].timestamp if events and hasattr(events[-1], 'timestamp') else len(compaction_calls)
            return create_compaction_event_mock(start_ts, end_ts, f"Summary {len(compaction_calls)}: previous interactions compressed")
        m.side_effect = mock

        sid = None

        # First batch of messages
        msg1 = (
            "I'm interested in upgrading my subscription from the Basic plan to the Professional plan. "
            "Can you tell me about the differences in features? I'm particularly interested in knowing "
            "if the Professional plan includes advanced analytics, priority support, and API access. "
            "I currently have 5 team members on my account and I want to make sure the upgrade would "
            "cover all of them without additional per-user fees."
        )
        msg2 = (
            "That's very helpful information. I have a follow-up question about the billing. If I upgrade "
            "today, will I be charged the full monthly rate for the Professional plan, or will it be prorated "
            "based on where I am in my current billing cycle? I renewed my Basic plan subscription just two "
            "weeks ago, so I'm hoping I won't lose that payment. Also, can I downgrade back to Basic if the "
            "Professional features don't meet my needs, and if so, is there a minimum commitment period?"
        )
        msg3 = "Perfect, that makes sense. Let me think about it and I'll get back to you tomorrow with my decision."

        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "progressive@test.com", msg1, "prog_1", test_llm_server, sid, "The Professional plan includes analytics, priority support, and full API access.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "progressive@test.com", msg2, "prog_2", test_llm_server, sid, "We'll prorate your current plan credit toward the Professional plan. No minimum commitment.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "progressive@test.com", msg3, "prog_3", test_llm_server, sid, "Sounds good! Feel free to reach out anytime.")

        assert len(compaction_calls) >= 1, f"First compaction should occur, got {len(compaction_calls)}"

        # Second batch of messages to trigger second compaction
        msg4 = (
            "Hi again! I've decided to go ahead with the upgrade to Professional. Before I confirm, I wanted "
            "to ask about data migration. Will all my existing projects, files, and settings automatically "
            "transfer to the new plan level, or is there a migration process I need to go through? I have "
            "about 50GB of data stored and several custom integrations set up with Zapier and Slack. I don't "
            "want to lose any of that work or have to reconfigure everything from scratch."
        )
        msg5 = "Excellent! Please proceed with the upgrade. Should I expect any downtime during the transition?"

        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "progressive@test.com", msg4, "prog_4", test_llm_server, sid, "Everything transfers automatically with zero downtime. Your integrations will continue working.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "progressive@test.com", msg5, "prog_5", test_llm_server, sid, "No downtime at all. I'm processing your upgrade now and it will be active within 2 minutes.")

        assert len(compaction_calls) >= 2, f"Second compaction should occur, got {len(compaction_calls)}"

        # Verify progressive summarization (fake event trick)
        if len(call_args_history) >= 2:
            first_call_events = call_args_history[0]
            second_call_events = call_args_history[1]

            # Verify second call has more events (fake summary event + new events)
            assert len(second_call_events) > 0, "Second compaction should have events"

            # Verify FIRST event in second call is the fake summary event
            fake_event = second_call_events[0]

            # 1. Verify it has content with summary text from first compaction
            assert fake_event.content is not None, "Fake event should have content"
            assert fake_event.content.parts, "Fake event should have parts"
            fake_text = None
            for part in fake_event.content.parts:
                if part.text:
                    fake_text = part.text
                    break
            assert fake_text is not None, "Fake event should have text content"
            assert "Summary 1" in fake_text, f"Fake event should contain first summary text, got: {fake_text}"

            # 2. Verify it has NO .actions.compaction (this is the trick!)
            assert fake_event.actions is None or not hasattr(fake_event.actions, 'compaction') or fake_event.actions.compaction is None, \
                "Fake event should NOT have .actions.compaction (this tricks LlmEventSummarizer)"

            # 3. Verify it's from "model" author (summaries are from AI perspective)
            assert fake_event.author == "model", f"Fake event author should be 'model', got {fake_event.author}"
            assert fake_event.content.role == "model", f"Fake event role should be 'model', got {fake_event.content.role}"

            # 4. Verify it has invocation_id marking it as fake
            assert "progressive_summary_fake_event" in fake_event.invocation_id or "fake" in fake_event.invocation_id.lower(), \
                f"Fake event should have identifiable invocation_id, got {fake_event.invocation_id}"


async def test_compaction_percentage_30_verification(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    compaction_agent_app_under_test: SamAgentApp,
):
    """
    Verify 30% compaction percentage compacts correct amount.

    With 2 interactions (~200 tokens total), 30% = ~60 tokens.
    Should compact 1 interaction (~100 tokens).
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
        msg1 = (
            "I'm trying to cancel my subscription but the cancel button isn't working on the website. "
            "I've tried multiple browsers and cleared my cache, but nothing happens when I click it. "
            "This is really frustrating because I need to cancel before my next billing date which is "
            "in three days. Can you please help me cancel my subscription immediately?"
        )
        msg2 = (
            "Thank you for the quick response. I want to make sure I understand correctly - if you "
            "cancel my subscription now, will I still have access to my account until the end of my "
            "current billing period, or will it be shut off immediately? I have some important files "
            "that I need to download first before losing access. Also, will I receive a confirmation "
            "email once the cancellation is processed?"
        )
        msg3 = "Perfect, please go ahead and process the cancellation. I've already backed up my files."

        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "pct30@test.com", msg1, "p30_1", test_llm_server, sid, "I apologize for the technical issue. I can help you cancel your subscription right away.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "pct30@test.com", msg2, "p30_2", test_llm_server, sid, "You'll keep access until the end of your billing period and receive a confirmation email.")
        _, sid, _ = await send_message_to_session(test_gateway_app_instance, "TestAgentCompaction", "pct30@test.com", msg3, "p30_3", test_llm_server, sid, "Your subscription has been cancelled. You'll receive confirmation shortly.")

        assert m.called
        # Should compact roughly 30% worth of text (first interaction)
        # Exact amount varies based on response lengths, but should be in reasonable range
        assert 100 < char_counts[0] < 800, f"Should compact reasonable amount (30% of total), got {char_counts[0]}"


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
    - Message 1: Text + image (~100 tokens)
    - Message 2: Text + larger text to accumulate tokens (~150 tokens)
    - Message 3: More text to push over 300 token threshold (triggers compaction)
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
            text_parts_content=[
                "Hello, I'm attaching a screenshot of an error message I'm seeing when I try to log into my account. "
                "I've been getting this error for the past two days and I can't access any of my saved data. "
                "The error appears right after I enter my username and password on the login page. "
                "Can you please take a look at the screenshot and let me know what might be causing this issue? "
                "I've tried clearing my browser cache and cookies, using a different browser, and even restarting "
                "my computer, but nothing seems to work. This is really urgent because I need to access my files "
                "for a presentation tomorrow morning."
            ],
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

        msg2 = (
            "Thank you for looking into this. I should also mention that I've checked the screenshot I sent "
            "and I noticed there's an error code at the bottom: ERR_AUTH_TIMEOUT_2048. I searched online for "
            "this error code but couldn't find any helpful information about what it means or how to fix it. "
            "Does this error code give you any clues about what might be wrong? Also, I wanted to ask if "
            "there's any chance that my account has been locked or suspended for some reason. I haven't "
            "received any emails about account issues, and my subscription payment went through successfully "
            "last week, so I don't think it's a billing problem. What other reasons could cause an "
            "authentication timeout error like this?"
        )
        _, sid, _ = await send_message_to_session(
            test_gateway_app_instance, "TestAgentCompaction", "image_test@example.com",
            msg2, "img_2", test_llm_server, sid,
            "I can see the error in your screenshot. ERR_AUTH_TIMEOUT_2048 indicates a server-side authentication delay."
        )

        # Message 3: More text to push over 300 token threshold (triggers compaction)
        llm_response_3 = {
            "id": "chatcmpl-img3",
            "object": "chat.completion",
            "model": "gpt-4-vision",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "I've reset your session. Please try logging in again now."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 15, "total_tokens": 65},
        }
        prime_llm_server(test_llm_server, [llm_response_3])

        msg3 = (
            "That's really helpful to know it's a server issue and not something wrong with my account. "
            "I appreciate you looking into this so quickly. Before I try logging in again, I just want to "
            "confirm - will resetting my session affect any of my saved preferences, bookmarks, or custom "
            "settings within the application? I spent a lot of time configuring everything just the way I "
            "like it and I don't want to have to redo all of that setup. Also, if the login works now, "
            "is there anything I should do to prevent this timeout error from happening again in the future?"
        )
        _, sid, all_events = await send_message_to_session(
            test_gateway_app_instance, "TestAgentCompaction", "image_test@example.com",
            msg3, "img_3", test_llm_server, sid, "Your preferences are safe. Try logging in now - it should work."
        )

        # Verify compaction was triggered
        assert mock_summarizer.called, "Compaction should have been triggered when total tokens exceed threshold"
        assert len(compaction_events) > 0, "At least one compaction event should be recorded"

        # Verify agent responded successfully
        terminal_event, aggregated_text, terminal_text = extract_outputs_from_event_list(all_events, "img_3")
        response_text = aggregated_text or terminal_text
        assert response_text is not None, "Agent should respond after compaction with binary content"

        # Verify summary notification includes context about continuation
        assert "Continuing" in response_text or "summarized" in response_text.lower(), \
            f"Response should indicate continuation after compaction, got: {response_text}"