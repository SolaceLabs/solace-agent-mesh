"""
Integration test for nested template preservation in artifacts.
This test simulates realistic streaming to verify the parser works correctly.
"""

from solace_agent_mesh.agent.adk.stream_parser import (
    FencedBlockStreamParser,
    BlockStartedEvent,
    BlockCompletedEvent,
    TemplateBlockStartedEvent,
    TemplateBlockCompletedEvent,
)


def test_nested_template_preservation_realistic_streaming():
    """
    Test that a nested template inside a save_artifact block is correctly
    preserved when streamed realistically (simulating the actual LLM output you showed).
    """
    # The EXACT content from the user's report
    full_content = """Here's your test file:

«««save_artifact: filename="eds-test.md" description="Testing the Employee Data System"
# Testing the Employee Data System

Introduction to This Test
This document is designed to test the Employee Data System's ability to dynamically embed structured data within markdown files.

Complete Employee List
The table below shows all employees currently in our system:

«««template: data="data.csv"
| {% for h in headers %}{{ h }} | {% endfor %}
|{% for h in headers %}---|{% endfor %}
{% for row in data_rows %}| {% for cell in row %}{{ cell }} | {% endfor %}
{% endfor %}
»»»

Analysis and Conclusion
The employee data has been successfully embedded and rendered in the table above.
»»»

I've created a new version of eds-test.md!"""

    # Create parser
    parser = FencedBlockStreamParser()

    # Simulate realistic streaming with varied chunk sizes (like real LLM output)
    # Using chunk sizes similar to what would come from an LLM (50-150 chars)
    chunk_size = 75
    all_events = []
    all_user_text = []

    for i in range(0, len(full_content), chunk_size):
        chunk = full_content[i : i + chunk_size]
        result = parser.process_chunk(chunk)
        all_events.extend(result.events)
        if result.user_facing_text:
            all_user_text.append(result.user_facing_text)

    # Finalize to handle any remaining state
    final_result = parser.finalize()
    all_events.extend(final_result.events)
    if final_result.user_facing_text:
        all_user_text.append(final_result.user_facing_text)

    # Extract events
    started_events = [e for e in all_events if isinstance(e, BlockStartedEvent)]
    completed_events = [e for e in all_events if isinstance(e, BlockCompletedEvent)]
    template_started = [
        e for e in all_events if isinstance(e, TemplateBlockStartedEvent)
    ]
    template_completed = [
        e for e in all_events if isinstance(e, TemplateBlockCompletedEvent)
    ]

    # Assertions
    assert (
        len(started_events) == 1
    ), f"Expected 1 BlockStartedEvent, got {len(started_events)}"
    assert (
        len(completed_events) == 1
    ), f"Expected 1 BlockCompletedEvent, got {len(completed_events)}"

    # Should NOT have template events (nested templates are literal text)
    assert (
        len(template_started) == 0
    ), "Should not emit template events for nested templates"
    assert (
        len(template_completed) == 0
    ), "Should not emit template events for nested templates"

    # Get the artifact content
    artifact_content = completed_events[0].content

    print(f"\n=== Saved Artifact Content ({len(artifact_content)} chars) ===")
    print(artifact_content)
    print(f"=== End Content ===\n")

    # Critical assertions - these match what the user reported as missing
    assert (
        "# Testing the Employee Data System" in artifact_content
    ), "Header should be in saved content"

    assert (
        '«««template: data="data.csv"' in artifact_content
    ), "Nested template start should be preserved"

    assert (
        "{% for h in headers %}" in artifact_content
    ), "Template body should be preserved"

    # This is the KEY assertion - the nested template's closing delimiter
    assert (
        artifact_content.count("»»»") == 1
    ), f"Should have exactly 1 nested template closing delimiter, found {artifact_content.count('»»»')}"

    assert (
        "Analysis and Conclusion" in artifact_content
    ), "Content after nested template should be preserved"

    assert (
        "successfully embedded and rendered" in artifact_content
    ), "Full text after template should be preserved (not truncated)"

    # Verify the complete nested template is intact
    nested_template = """«««template: data="data.csv"
| {% for h in headers %}{{ h }} | {% endfor %}
|{% for h in headers %}---|{% endfor %}
{% for row in data_rows %}| {% for cell in row %}{{ cell }} | {% endfor %}
{% endfor %}
»»»"""

    assert (
        nested_template in artifact_content
    ), "Complete nested template structure should be in artifact"

    # Verify user-facing text
    user_visible_text = "".join(all_user_text)
    print(f"\n=== User Visible Text ({len(user_visible_text)} chars) ===")
    print(user_visible_text)
    print(f"=== End User Text ===\n")

    # User should see text before and after artifact, but NOT the artifact itself
    assert (
        "Here's your test file:" in user_visible_text
    ), "Text before artifact should be visible"
    assert (
        "I've created a new version" in user_visible_text
    ), "Text after artifact should be visible"

    # User should NOT see the artifact delimiters or content
    assert (
        "«««save_artifact:" not in user_visible_text
    ), "save_artifact delimiter should not be visible to user"
    assert (
        "# Testing the Employee Data System" not in user_visible_text
    ), "Artifact content should not be visible to user"

    # CRITICAL: User should NOT see the closing delimiter in the chat
    # This was the bug the user reported
    assert (
        "»»»" not in user_visible_text
    ), "Closing delimiter should NOT appear in user-visible text!"
