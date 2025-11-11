"""
Unit tests for template block parsing in FencedBlockStreamParser.
"""

from solace_agent_mesh.agent.adk.stream_parser import (
    FencedBlockStreamParser,
    TemplateBlockStartedEvent,
    TemplateBlockCompletedEvent,
    BlockStartedEvent,
    BlockCompletedEvent,
)


def test_parse_simple_template_block():
    """Test parsing a simple standalone template block."""
    parser = FencedBlockStreamParser()

    # Simulate streaming a template block
    input_text = '«««template: data="users.json"\nHello {{name}}!\n»»»'

    result = parser.process_chunk(input_text)
    final_result = parser.finalize()

    # Should have template events
    events = result.events
    assert len(events) == 2
    assert isinstance(events[0], TemplateBlockStartedEvent)
    assert events[0].params == {"data": "users.json"}
    assert isinstance(events[1], TemplateBlockCompletedEvent)
    assert events[1].template_content == "Hello {{name}}!\n"

    # User-facing text should be empty (template is hidden)
    assert result.user_facing_text == ""


def test_parse_template_with_jsonpath_and_limit():
    """Test parsing a template with jsonpath and limit parameters."""
    parser = FencedBlockStreamParser()

    input_text = '«««template: data="data.json" jsonpath="$.items" limit="10"\n{{#items}}Item: {{.}}{{/items}}\n»»»'

    result = parser.process_chunk(input_text)
    parser.finalize()

    events = result.events
    assert len(events) == 2
    assert isinstance(events[0], TemplateBlockStartedEvent)
    assert events[0].params == {
        "data": "data.json",
        "jsonpath": "$.items",
        "limit": "10",
    }
    assert isinstance(events[1], TemplateBlockCompletedEvent)


def test_template_nested_in_artifact_preserved():
    """Test that template blocks inside save_artifact are preserved literally."""
    parser = FencedBlockStreamParser()

    # Template inside an artifact should be preserved
    input_text = (
        '«««save_artifact: filename="doc.md"\n'
        "This is a document with an embedded template:\n"
        '«««template: data="users.json"\n'
        "Hello {{name}}!\n"
        "»»»\n"
        "End of document.\n"
        "»»»"
    )

    result = parser.process_chunk(input_text)
    parser.finalize()

    events = result.events
    # Should only have artifact events, not template events
    assert len(events) == 2
    assert isinstance(events[0], BlockStartedEvent)
    assert isinstance(events[1], BlockCompletedEvent)

    # The artifact content should contain the literal template syntax
    artifact_content = events[1].content
    assert '«««template: data="users.json"' in artifact_content
    assert "Hello {{name}}!" in artifact_content


def test_mixed_text_and_template():
    """Test parsing text interspersed with template blocks."""
    parser = FencedBlockStreamParser()

    input_text = (
        "Some regular text before.\n"
        '«««template: data="data.csv"\n'
        "Template content here.\n"
        "»»»\n"
        "Text after the template."
    )

    result = parser.process_chunk(input_text)
    parser.finalize()

    # User-facing text should contain the text parts but not the template
    assert "Some regular text before.\n" in result.user_facing_text
    assert "Template content here" not in result.user_facing_text

    # Should have template events
    events = result.events
    template_events = [e for e in events if isinstance(e, TemplateBlockCompletedEvent)]
    assert len(template_events) == 1
    assert template_events[0].template_content == "Template content here.\n"


def test_unterminated_template_block():
    """Test handling of unterminated template blocks."""
    parser = FencedBlockStreamParser()

    # Template without closing delimiter
    input_text = '«««template: data="data.json"\nUnterminated template content'

    result = parser.process_chunk(input_text)
    final_result = parser.finalize()

    # Should get a completed event in finalize (with incomplete content)
    events = final_result.events
    assert len(events) == 1
    assert isinstance(events[0], TemplateBlockCompletedEvent)
    assert "Unterminated template content" in events[0].template_content


def test_multiple_template_blocks():
    """Test parsing multiple template blocks in sequence."""
    parser = FencedBlockStreamParser()

    input_text = (
        '«««template: data="users.json"\n'
        "Template 1\n"
        "»»»\n"
        "Some text\n"
        '«««template: data="products.csv"\n'
        "Template 2\n"
        "»»»"
    )

    result = parser.process_chunk(input_text)
    parser.finalize()

    template_events = [
        e for e in result.events if isinstance(e, TemplateBlockCompletedEvent)
    ]
    assert len(template_events) == 2
    assert template_events[0].template_content == "Template 1\n"
    assert template_events[1].template_content == "Template 2\n"


def test_template_with_csv_data():
    """Test parsing a template designed for CSV data."""
    parser = FencedBlockStreamParser()

    input_text = (
        '«««template: data="sales.csv" limit="5"\n'
        "| {{#headers}}{{.}} | {{/headers}}\n"
        "|{{#headers}}---|{{/headers}}\n"
        "{{#data_rows}}\n"
        "| {{#.}}{{.}} | {{/.}}\n"
        "{{/data_rows}}\n"
        "»»»"
    )

    result = parser.process_chunk(input_text)
    parser.finalize()

    events = result.events
    assert len(events) == 2
    assert isinstance(events[0], TemplateBlockStartedEvent)
    assert events[0].params == {"data": "sales.csv", "limit": "5"}
    assert isinstance(events[1], TemplateBlockCompletedEvent)
    assert "{{#headers}}" in events[1].template_content
    assert "{{#data_rows}}" in events[1].template_content


def test_nested_template_in_artifact_with_streaming():
    """
    Test that template blocks inside save_artifact are preserved literally
    when data arrives in small chunks (simulating realistic streaming).
    """
    parser = FencedBlockStreamParser()

    # Build the full content we want to test
    full_text = (
        '«««save_artifact: filename="report.md" description="Monthly report"\n'
        "# Sales Report\n"
        "\n"
        "Here is the data:\n"
        "\n"
        '«««template: data="sales.csv" limit="10"\n'
        "| {% for h in headers %}{{ h }} | {% endfor %}\n"
        "|{% for h in headers %}---|{% endfor %}\n"
        "{% for row in data_rows %}\n"
        "| {% for cell in row %}{{ cell }} | {% endfor %}\n"
        "{% endfor %}\n"
        "»»»\n"
        "\n"
        "That concludes the report.\n"
        "»»»"
    )

    # Simulate realistic streaming by processing small chunks
    chunk_size = 3  # Very small chunks to stress-test the parser
    all_events = []
    all_user_text = []

    for i in range(0, len(full_text), chunk_size):
        chunk = full_text[i : i + chunk_size]
        result = parser.process_chunk(chunk)
        all_events.extend(result.events)
        if result.user_facing_text:
            all_user_text.append(result.user_facing_text)

    # Finalize to handle any remaining state
    final_result = parser.finalize()
    all_events.extend(final_result.events)
    if final_result.user_facing_text:
        all_user_text.append(final_result.user_facing_text)

    # Verify we got the right events
    started_events = [e for e in all_events if isinstance(e, BlockStartedEvent)]
    completed_events = [e for e in all_events if isinstance(e, BlockCompletedEvent)]

    assert (
        len(started_events) == 1
    ), f"Expected 1 BlockStartedEvent, got {len(started_events)}"
    assert (
        len(completed_events) == 1
    ), f"Expected 1 BlockCompletedEvent, got {len(completed_events)}"

    # Verify the artifact parameters
    assert started_events[0].params["filename"] == "report.md"
    assert started_events[0].params["description"] == "Monthly report"

    # CRITICAL: Verify the artifact content contains the COMPLETE nested template
    artifact_content = completed_events[0].content

    # Check for template start
    assert (
        '«««template: data="sales.csv" limit="10"' in artifact_content
    ), f"Template start missing. Content:\n{artifact_content}"

    # Check for template body
    assert (
        "{% for h in headers %}" in artifact_content
    ), f"Template body missing. Content:\n{artifact_content}"
    assert (
        "{% for row in data_rows %}" in artifact_content
    ), f"Template loops missing. Content:\n{artifact_content}"

    # Check for template end
    assert artifact_content.count("»»»") == 1, (
        f"Should have exactly 1 nested template closing delimiter in artifact content. "
        f"Found {artifact_content.count('»»»')}. Content:\n{artifact_content}"
    )

    # Verify the complete structure
    expected_template = (
        '«««template: data="sales.csv" limit="10"\n'
        "| {% for h in headers %}{{ h }} | {% endfor %}\n"
        "|{% for h in headers %}---|{% endfor %}\n"
        "{% for row in data_rows %}\n"
        "| {% for cell in row %}{{ cell }} | {% endfor %}\n"
        "{% endfor %}\n"
        "»»»"
    )

    assert expected_template in artifact_content, (
        f"Complete nested template not found in artifact.\n"
        f"Expected:\n{expected_template}\n"
        f"Got artifact content:\n{artifact_content}"
    )

    # Should NOT have any TemplateBlockStartedEvent or TemplateBlockCompletedEvent
    # because the template is nested inside an artifact
    template_started = [
        e for e in all_events if isinstance(e, TemplateBlockStartedEvent)
    ]
    template_completed = [
        e for e in all_events if isinstance(e, TemplateBlockCompletedEvent)
    ]
    assert (
        len(template_started) == 0
    ), "Should not emit template events for nested templates"
    assert (
        len(template_completed) == 0
    ), "Should not emit template events for nested templates"

    # User-facing text should be empty (artifact content is not shown to user during streaming)
    combined_user_text = "".join(all_user_text)
    assert (
        combined_user_text == ""
    ), f"Expected no user-facing text, got: {combined_user_text}"
