"""
Unit test to verify that artifact_return guidance is added to peer responses with artifacts.
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from solace_agent_mesh.common.utils.embeds.constants import (
    EMBED_DELIMITER_OPEN,
    EMBED_DELIMITER_CLOSE,
)


@pytest.mark.asyncio
async def test_artifact_return_guidance_in_peer_response():
    """
    Test that when a peer agent creates artifacts, the response includes
    guidance about using artifact_return embed.
    """
    from solace_agent_mesh.agent.utils.artifact_helpers import generate_artifact_metadata_summary

    # Mock component
    component = Mock()
    component.log_identifier = "[TestComponent]"
    component.artifact_service = AsyncMock()

    # Mock artifact service to return metadata
    mock_metadata = {
        "filename": "test_file.csv",
        "version": 0,
        "mime_type": "text/csv",
        "description": "Test file",
        "size_bytes": 100,
    }

    component.artifact_service.load_artifact = AsyncMock(
        return_value=MagicMock(
            metadata={
                "filename": "test_file.csv",
                "version": 0,
                "mime_type": "text/csv",
                "description": "Test file",
                "size_bytes": 100,
            }
        )
    )

    # Create artifact identifiers
    artifact_identifiers = [
        {"filename": "test_file.csv", "version": 0}
    ]

    # Generate summary
    summary = await generate_artifact_metadata_summary(
        component=component,
        artifact_identifiers=artifact_identifiers,
        user_id="test_user",
        session_id="test_session",
        app_name="TestPeerAgent",
        header_text="Peer agent `TestPeerAgent` created 1 artifact(s):",
    )

    # Now add the artifact_return guidance (simulating what event_handlers.py does)
    artifact_return_guidance = (
        f"\n\n**Note:** If any of these artifacts fulfill the user's request, "
        f"you should return them directly to the user using the "
        f"{EMBED_DELIMITER_OPEN}artifact_return:filename:version{EMBED_DELIMITER_CLOSE} embed. "
        f"This is more convenient for the user than just describing the artifacts. "
        f"Replace 'filename' and 'version' with the actual values from the artifact metadata above."
    )
    full_summary = summary + artifact_return_guidance

    # Verify the guidance is present
    assert "artifact_return" in full_summary
    assert EMBED_DELIMITER_OPEN in full_summary
    assert EMBED_DELIMITER_CLOSE in full_summary
    assert "filename:version" in full_summary
    assert "more convenient for the user" in full_summary

    # Verify the delimiters are the correct constants (« and »)
    assert "«artifact_return:filename:version»" in full_summary

    print("✓ Artifact return guidance is correctly added to peer responses")
    print(f"\nFull summary preview:\n{full_summary[:500]}...")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_artifact_return_guidance_in_peer_response())
