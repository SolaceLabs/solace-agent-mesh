"""
Unit tests for template block resolution in artifact content.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from solace_agent_mesh.common.utils.templates import resolve_template_blocks_in_string


@pytest.mark.asyncio
async def test_resolve_simple_template_block():
    """Test resolving a simple template block in text."""
    text = """
Some text before.
«««template: data="users.json"
Hello {{ name }}!
»»»
Text after.
"""

    # Mock artifact service
    artifact_service = MagicMock()

    # Mock the load function to return user data
    async def mock_load(*args, **kwargs):
        return {
            "status": "success",
            "content": {"name": "Alice"},
            "mime_type": "application/json",
        }

    session_context = {
        "app_name": "test",
        "user_id": "user1",
        "session_id": "session1",
    }

    with patch(
        "solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata",
        side_effect=mock_load,
    ):
        result = await resolve_template_blocks_in_string(
            text=text,
            artifact_service=artifact_service,
            session_context=session_context,
        )

        # Template should be resolved
        assert "Hello Alice!" in result
        assert "«««template:" not in result
        assert "Some text before." in result
        assert "Text after." in result


@pytest.mark.asyncio
async def test_resolve_template_with_csv_data():
    """Test resolving a template with CSV data."""
    text = """«««template: data="sales.csv" limit="2"
{% for row in data_rows %}Row: {% for cell in row %}{{ cell }} {% endfor %}
{% endfor %}»»»"""

    csv_content = "Name,Amount\nAlice,100\nBob,200\nCharlie,300"

    async def mock_load(*args, **kwargs):
        return {
            "status": "success",
            "content": csv_content,
            "mime_type": "text/csv",
        }

    with patch(
        "solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata",
        side_effect=mock_load,
    ):
        result = await resolve_template_blocks_in_string(
            text=text,
            artifact_service=MagicMock(),
            session_context={"app_name": "test", "user_id": "u1", "session_id": "s1"},
        )

        # Should render first 2 rows only
        assert "Alice" in result
        assert "Bob" in result
        assert "Charlie" not in result  # Limited to 2 rows


@pytest.mark.asyncio
async def test_resolve_multiple_template_blocks():
    """Test resolving multiple template blocks in the same text."""
    text = """
First: «««template: data="data1.json"
Value: {{ value }}
»»»

Second: «««template: data="data2.json"
Name: {{ name }}
»»»
"""

    call_count = [0]

    async def mock_load(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return {
                "status": "success",
                "content": 42,
                "mime_type": "application/json",
            }
        else:
            return {
                "status": "success",
                "content": {"name": "Bob"},
                "mime_type": "application/json",
            }

    with patch(
        "solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata",
        side_effect=mock_load,
    ):
        result = await resolve_template_blocks_in_string(
            text=text,
            artifact_service=MagicMock(),
            session_context={"app_name": "test", "user_id": "u1", "session_id": "s1"},
        )

        # Both templates should be resolved
        assert "Value: 42" in result
        assert "Name: Bob" in result
        assert "«««template:" not in result


@pytest.mark.asyncio
async def test_resolve_with_missing_data_artifact():
    """Test handling of missing data artifact."""
    text = """«««template: data="missing.json"
{{ value }}
»»»"""

    async def mock_load(*args, **kwargs):
        return {
            "status": "error",
            "message": "Not found",
        }

    with patch(
        "solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata",
        side_effect=mock_load,
    ):
        result = await resolve_template_blocks_in_string(
            text=text,
            artifact_service=MagicMock(),
            session_context={"app_name": "test", "user_id": "u1", "session_id": "s1"},
        )

        # Should return error message
        assert "[Template Error:" in result
        assert "missing.json" in result


@pytest.mark.asyncio
async def test_no_template_blocks():
    """Test text without template blocks passes through unchanged."""
    text = "Just some regular text without any templates."

    result = await resolve_template_blocks_in_string(
        text=text,
        artifact_service=MagicMock(),
        session_context={"app_name": "test", "user_id": "u1", "session_id": "s1"},
    )

    assert result == text
