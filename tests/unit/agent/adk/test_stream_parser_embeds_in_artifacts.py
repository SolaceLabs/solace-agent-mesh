"""
Unit tests for handling embeds inside save_artifact blocks in the stream parser.
Tests that embeds like «datetime:iso» are correctly preserved as literal text
when inside an artifact, rather than causing the parser to lose state.
"""

from solace_agent_mesh.agent.adk.stream_parser import (
    FencedBlockStreamParser,
    BlockStartedEvent,
    BlockCompletedEvent,
)


def test_embed_in_artifact_preserved():
    """
    Test that an embed inside a save_artifact block is correctly preserved
    as literal text in the artifact content.
    """
    content = """«««save_artifact: filename="test.txt"
This file was created at «datetime:iso».
»»»"""

    parser = FencedBlockStreamParser()
    result = parser.process_chunk(content)
    final_result = parser.finalize()

    all_events = result.events + final_result.events
    completed = [e for e in all_events if isinstance(e, BlockCompletedEvent)]

    assert len(completed) == 1
    artifact_content = completed[0].content

    # The embed should be preserved as literal text
    assert "«datetime:iso»" in artifact_content
    assert "This file was created at «datetime:iso»." in artifact_content


def test_multiple_embeds_in_artifact():
    """
    Test that multiple embeds in an artifact are all preserved.
    """
    content = """«««save_artifact: filename="report.md"
# Report Generated on «datetime:iso»

UUID: «uuid:»
Calculation: «math:42 * 2»
»»»"""

    parser = FencedBlockStreamParser()
    result = parser.process_chunk(content)
    final_result = parser.finalize()

    all_events = result.events + final_result.events
    completed = [e for e in all_events if isinstance(e, BlockCompletedEvent)]

    assert len(completed) == 1
    artifact_content = completed[0].content

    # All embeds should be preserved
    assert "«datetime:iso»" in artifact_content
    assert "«uuid:»" in artifact_content
    assert "«math:42 * 2»" in artifact_content


def test_embed_at_end_of_artifact():
    """
    Test that an embed at the very end of an artifact (before the closing delimiter)
    doesn't prevent the artifact from being closed correctly.

    This was the specific bug reported: «datetime:iso» at the end of the artifact
    caused the closing »»» to appear in the chat instead of being consumed.
    """
    content = """«««save_artifact: filename="timestamped.txt"
Created: «datetime:iso»
»»»"""

    parser = FencedBlockStreamParser()

    # Simulate realistic streaming with small chunks
    chunk_size = 10
    all_events = []
    all_user_text = []

    for i in range(0, len(content), chunk_size):
        chunk = content[i : i + chunk_size]
        result = parser.process_chunk(chunk)
        all_events.extend(result.events)
        if result.user_facing_text:
            all_user_text.append(result.user_facing_text)

    final_result = parser.finalize()
    all_events.extend(final_result.events)
    if final_result.user_facing_text:
        all_user_text.append(final_result.user_facing_text)

    completed = [e for e in all_events if isinstance(e, BlockCompletedEvent)]

    assert len(completed) == 1, "Should have exactly one completed block"
    artifact_content = completed[0].content

    # The embed should be in the artifact
    assert "«datetime:iso»" in artifact_content
    assert artifact_content == "Created: «datetime:iso»\n"

    # The closing delimiter should NOT appear in user-visible text
    user_visible = "".join(all_user_text)
    assert "»»»" not in user_visible, "Closing delimiter should not be in user text"


def test_nested_template_with_embed_after():
    """
    Test the exact scenario from the bug report: nested template in artifact,
    followed by more content including an embed.
    """
    content = """«««save_artifact: filename="eds-test.md" description="Testing the Employee Data System"
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

Document created: «datetime:iso»
»»»"""

    parser = FencedBlockStreamParser()

    # Simulate realistic streaming
    chunk_size = 75
    all_events = []
    all_user_text = []

    for i in range(0, len(content), chunk_size):
        chunk = content[i : i + chunk_size]
        result = parser.process_chunk(chunk)
        all_events.extend(result.events)
        if result.user_facing_text:
            all_user_text.append(result.user_facing_text)

    final_result = parser.finalize()
    all_events.extend(final_result.events)
    if final_result.user_facing_text:
        all_user_text.append(final_result.user_facing_text)

    completed = [e for e in all_events if isinstance(e, BlockCompletedEvent)]
    started = [e for e in all_events if isinstance(e, BlockStartedEvent)]

    assert len(started) == 1, "Should have exactly one save_artifact block started"
    assert len(completed) == 1, "Should have exactly one block completed"

    artifact_content = completed[0].content

    # All content should be preserved
    assert "# Testing the Employee Data System" in artifact_content
    assert '«««template: data="data.csv"' in artifact_content
    assert "{% for h in headers %}" in artifact_content

    # The nested template closing delimiter should be in the artifact (not consumed)
    assert (
        artifact_content.count("»»»") == 1
    ), "Should have the nested template's closing delimiter"

    # The content after the nested template should be preserved
    assert "Analysis and Conclusion" in artifact_content
    assert "successfully embedded and rendered" in artifact_content

    # The datetime embed should be preserved
    assert "«datetime:iso»" in artifact_content

    # The closing delimiter should NOT be in user-visible text
    user_visible = "".join(all_user_text)
    assert "»»»" not in user_visible, "Closing delimiter should not appear in user text"


def test_embed_causes_potential_block_but_returns_to_in_block():
    """
    Test that when we encounter a single « (from an embed) while IN_BLOCK,
    we transition to POTENTIAL_BLOCK, realize it's not a nested block,
    and correctly return to IN_BLOCK state (not IDLE).
    """
    content = """«««save_artifact: filename="test.txt"
Before embed.
«datetime:iso»
After embed.
»»»"""

    parser = FencedBlockStreamParser()

    # Process character by character to verify state transitions
    chunk_size = 1
    all_events = []
    all_user_text = []

    for i in range(0, len(content), chunk_size):
        chunk = content[i : i + chunk_size]
        result = parser.process_chunk(chunk)
        all_events.extend(result.events)
        if result.user_facing_text:
            all_user_text.append(result.user_facing_text)

    final_result = parser.finalize()
    all_events.extend(final_result.events)
    if final_result.user_facing_text:
        all_user_text.append(final_result.user_facing_text)

    completed = [e for e in all_events if isinstance(e, BlockCompletedEvent)]

    assert len(completed) == 1
    artifact_content = completed[0].content

    # All content including the embed should be in the artifact
    assert "Before embed." in artifact_content
    assert "«datetime:iso»" in artifact_content
    assert "After embed." in artifact_content

    # Nothing should be in user text (everything is inside the artifact)
    user_visible = "".join(all_user_text)
    assert user_visible == "", "No user-visible text expected (everything in artifact)"
