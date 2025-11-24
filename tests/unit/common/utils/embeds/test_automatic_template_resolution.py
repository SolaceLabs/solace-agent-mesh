"""
Test that template resolution happens automatically when resolving late embeds.
"""

import pytest
from solace_agent_mesh.common.utils.embeds import (
    LATE_EMBED_TYPES,
    evaluate_embed,
    resolve_embeds_recursively_in_string,
)
from solace_agent_mesh.common.utils.embeds.types import ResolutionMode
from tests.integration.conftest import TestInMemoryArtifactService


@pytest.mark.asyncio
async def test_template_resolution_automatic_with_late_embeds():
    """
    Test that templates are automatically resolved when resolving late embeds
    without needing a separate call to resolve_template_blocks_in_string.
    """
    artifact_service = TestInMemoryArtifactService()

    # Create a CSV data artifact
    csv_content = """name,age,department
Alice,30,Engineering
Bob,25,Sales"""

    await artifact_service.save_artifact(
        app_name="test_app",
        user_id="test_user",
        session_id="test_session",
        filename="employees.csv",
        artifact=type('Part', (), {'inline_data': type('InlineData', (), {
            'data': csv_content.encode('utf-8'),
            'mime_type': 'text/csv'
        })})()
    )

    # Create an artifact with a template block
    artifact_content = """# Employee Report

Here are all our employees:

«««template: data="employees.csv"
| {% for h in headers %}{{ h }} | {% endfor %}
|{% for h in headers %}---|{% endfor %}
{% for row in data_rows %}| {% for cell in row %}{{ cell }} | {% endfor %}
{% endfor %}
»»»

End of report."""

    await artifact_service.save_artifact(
        app_name="test_app",
        user_id="test_user",
        session_id="test_session",
        filename="report.md",
        artifact=type('Part', (), {'inline_data': type('InlineData', (), {
            'data': artifact_content.encode('utf-8'),
            'mime_type': 'text/markdown'
        })})()
    )

    # Now embed the artifact using artifact_content (a late embed)
    text_with_embed = "Here's the report: «artifact_content:report.md»"

    context = {
        "artifact_service": artifact_service,
        "session_context": {
            "app_name": "test_app",
            "user_id": "test_user",
            "session_id": "test_session",
        }
    }

    config = {
        "gateway_max_artifact_resolve_size_bytes": -1,
        "gateway_recursive_embed_depth": 12,
    }

    # Resolve late embeds - templates should be resolved automatically
    result = await resolve_embeds_recursively_in_string(
        text=text_with_embed,
        context=context,
        resolver_func=evaluate_embed,
        types_to_resolve=LATE_EMBED_TYPES,
        resolution_mode=ResolutionMode.RECURSIVE_ARTIFACT_CONTENT,
        log_identifier="[Test]",
        config=config,
        max_depth=12,
        max_total_size=-1,
    )

    # Verify the template was resolved (should contain the CSV data as a table)
    assert "Alice" in result
    assert "Bob" in result
    assert "Engineering" in result
    assert "Sales" in result
    assert "| name | age | department |" in result

    # The template block delimiters should be gone
    assert "«««template:" not in result
    assert "»»»" not in result

    print("\n=== Result ===")
    print(result)
    print("=== End Result ===")


@pytest.mark.asyncio
async def test_no_template_resolution_with_early_embeds_only():
    """
    Test that templates are NOT resolved when only early embeds are being resolved
    (since templates are considered late embeds).
    """
    from solace_agent_mesh.common.utils.embeds import EARLY_EMBED_TYPES, resolve_embeds_recursively_in_string

    artifact_service = TestInMemoryArtifactService()

    # Create a text artifact with a template block
    artifact_content = """Report generated at «datetime:iso»

«««template: data="data.csv"
Some template content
»»»"""

    # Resolve only early embeds (datetime)
    # Templates should NOT be resolved since they're late embeds
    context = {
        "artifact_service": artifact_service,
        "session_context": {
            "app_name": "test_app",
            "user_id": "test_user",
            "session_id": "test_session",
        }
    }

    result = await resolve_embeds_recursively_in_string(
        text=artifact_content,
        context=context,
        resolver_func=evaluate_embed,
        types_to_resolve=EARLY_EMBED_TYPES,
        resolution_mode=ResolutionMode.A2A_MESSAGE_TO_USER,
        log_identifier="[Test]",
        config={},
        max_depth=12,
        max_total_size=-1,
    )

    # datetime should be resolved
    assert "«datetime:iso»" not in result

    # But template block should still be present (not resolved)
    assert "«««template:" in result
    assert "»»»" in result

    print("\n=== Result (Early Embeds Only) ===")
    print(result)
    print("=== End Result ===")
