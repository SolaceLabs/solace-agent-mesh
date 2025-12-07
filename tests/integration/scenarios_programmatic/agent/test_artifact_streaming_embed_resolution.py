"""
Integration tests for embed resolution in artifact streaming chunks.
Tests verify that early embeds (math, datetime, uuid, artifact_meta) are properly
resolved in the streamed chunks of artifact creation updates before being sent to the browser.
"""

import pytest
import json
from typing import List, Dict, Any, Optional
from sam_test_infrastructure.llm_server.server import TestLLMServer
from sam_test_infrastructure.gateway_interface.component import TestGatewayComponent
from sam_test_infrastructure.a2a_validator.validator import A2AMessageValidator
from solace_agent_mesh.agent.sac.app import SamAgentApp
from a2a.types import TaskStatusUpdateEvent, DataPart

from tests.integration.scenarios_programmatic.test_helpers import (
    prime_llm_server,
    create_gateway_input_data,
    submit_test_input,
    get_all_task_events,
)

pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.agent,
]


def extract_artifact_progress_chunks(
    all_events: List[Any],
) -> List[str]:
    """
    Extract artifact_chunk values from ArtifactCreationProgressData events.

    Parses TaskStatusUpdateEvent messages to find data_part entries with
    type="artifact_creation_progress" and extracts their artifact_chunk fields.

    Returns:
        List of artifact chunk strings (may contain None values for chunks without content)
    """
    chunks = []

    for event in all_events:
        if not isinstance(event, TaskStatusUpdateEvent):
            continue

        if not event.status or not event.status.message or not event.status.message.parts:
            continue

        for part in event.status.message.parts:
            # A2A Part objects use .root to access the underlying part type
            # Check if this is a DataPart
            if not hasattr(part, 'root') or not isinstance(part.root, DataPart):
                continue

            if not hasattr(part.root, 'data') or not part.root.data:
                continue

            try:
                # The data field is a dictionary (not JSON string)
                data = part.root.data

                # Check if this is artifact_creation_progress data
                # All fields are at the top level (from model_dump())
                if data.get("type") == "artifact_creation_progress":
                    artifact_chunk = data.get("artifact_chunk")

                    # Only append non-None chunks (chunks without content have None)
                    if artifact_chunk is not None:
                        chunks.append(artifact_chunk)

            except (AttributeError, KeyError, TypeError) as e:
                # Skip parts that don't match expected structure
                continue

    return chunks


class TestArtifactStreamingEmbedResolution:
    """Tests for embed resolution in streaming artifact chunks."""

    async def test_math_embed_resolved_in_streaming_chunks(
        self,
        test_llm_server: TestLLMServer,
        test_gateway_app_instance: TestGatewayComponent,
        sam_app_under_test: SamAgentApp,
        a2a_message_validator: A2AMessageValidator,
    ):
        """Verify math embeds are resolved in artifact streaming chunks."""
        scenario_id = "test_math_embed_streaming"

        # Prime LLM with artifact containing math embed
        # Add padding to force multiple chunks (chunk size is 50 bytes)
        llm_response = {
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": (
                            "«««save_artifact: filename=\"calculation.txt\" mime_type=\"text/plain\"\n"
                            "This is padding text to ensure the artifact is split across chunks.\n"
                            "The result of 2+2 is: «math:2+2»\n"
                            "More padding text here to make it longer than fifty bytes total.\n"
                            "»»»"
                        ),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }
        prime_llm_server(test_llm_server, [llm_response])

        # Submit test input
        test_input_data = create_gateway_input_data(
            target_agent="TestAgent",
            user_identity="embed_test_user@example.com",
            text_parts_content=["Create a calculation file"],
            scenario_id=scenario_id,
        )
        task_id = await submit_test_input(
            test_gateway_app_instance, test_input_data, scenario_id
        )

        # Capture all events
        all_events = await get_all_task_events(
            test_gateway_app_instance, task_id, overall_timeout=10.0
        )

        # Extract artifact progress chunks
        chunks = extract_artifact_progress_chunks(all_events)

        # Verify we got chunks
        assert len(chunks) > 0, (
            f"Scenario {scenario_id}: Expected to receive artifact progress chunks, "
            f"but got none. Total events: {len(all_events)}"
        )

        # Combine all chunks
        all_chunks_text = "".join(chunks)

        # Verify resolved value appears in chunks
        assert "4" in all_chunks_text, (
            f"Scenario {scenario_id}: Expected resolved math result '4' to appear in chunks. "
            f"Chunks: {chunks}"
        )

        # Verify unresolved embed does NOT appear in chunks
        assert "«math:2+2»" not in all_chunks_text, (
            f"Scenario {scenario_id}: Unresolved embed '«math:2+2»' should not appear in chunks. "
            f"Chunks: {chunks}"
        )

        # Verify no partial embeds (unclosed «)
        open_count = all_chunks_text.count("«")
        close_count = all_chunks_text.count("»")

        # Either no embeds at all, or equal open/close counts
        assert open_count == close_count, (
            f"Scenario {scenario_id}: Found partial embeds in chunks. "
            f"Open delimiters: {open_count}, Close delimiters: {close_count}. "
            f"Chunks: {chunks}"
        )

        print(f"Scenario {scenario_id}: Successfully verified embed resolution in {len(chunks)} chunks")

    async def test_multiple_math_embeds_in_artifact(
        self,
        test_llm_server: TestLLMServer,
        test_gateway_app_instance: TestGatewayComponent,
        sam_app_under_test: SamAgentApp,
        a2a_message_validator: A2AMessageValidator,
    ):
        """Verify multiple math embeds are all resolved correctly in streaming chunks."""
        scenario_id = "test_multiple_embeds_streaming"

        # Prime LLM with artifact containing multiple math embeds
        llm_response = {
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": (
                            "«««save_artifact: filename=\"calculations.txt\" mime_type=\"text/plain\"\n"
                            "Here are some calculations with padding to force chunking behavior:\n"
                            "First: «math:10*5» equals fifty.\n"
                            "Second: «math:3+7» equals ten.\n"
                            "Third: «math:100/4» equals twenty-five.\n"
                            "All calculations completed successfully with sufficient padding.\n"
                            "»»»"
                        ),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 25, "total_tokens": 35},
        }
        prime_llm_server(test_llm_server, [llm_response])

        # Submit test input
        test_input_data = create_gateway_input_data(
            target_agent="TestAgent",
            user_identity="embed_test_user@example.com",
            text_parts_content=["Create a calculations file"],
            scenario_id=scenario_id,
        )
        task_id = await submit_test_input(
            test_gateway_app_instance, test_input_data, scenario_id
        )

        # Capture all events
        all_events = await get_all_task_events(
            test_gateway_app_instance, task_id, overall_timeout=10.0
        )

        # Extract artifact progress chunks
        chunks = extract_artifact_progress_chunks(all_events)

        # Verify we got chunks
        assert len(chunks) > 0, f"Scenario {scenario_id}: Expected artifact chunks"

        # Combine all chunks
        all_chunks_text = "".join(chunks)

        # Verify all resolved values appear
        assert "50" in all_chunks_text, (
            f"Scenario {scenario_id}: Expected '50' from 10*5. Chunks: {chunks}"
        )
        assert "10" in all_chunks_text, (
            f"Scenario {scenario_id}: Expected '10' from 3+7. Chunks: {chunks}"
        )
        assert "25" in all_chunks_text, (
            f"Scenario {scenario_id}: Expected '25' from 100/4. Chunks: {chunks}"
        )

        # Verify no unresolved embeds remain
        assert "«math:" not in all_chunks_text, (
            f"Scenario {scenario_id}: Found unresolved embed markers. Chunks: {chunks}"
        )

        # Verify no partial embeds
        open_count = all_chunks_text.count("«")
        close_count = all_chunks_text.count("»")
        assert open_count == close_count, (
            f"Scenario {scenario_id}: Partial embeds detected. "
            f"Open: {open_count}, Close: {close_count}"
        )

        print(f"Scenario {scenario_id}: Verified {len(chunks)} chunks with multiple embeds resolved")

    async def test_datetime_embed_resolved_in_streaming_chunks(
        self,
        test_llm_server: TestLLMServer,
        test_gateway_app_instance: TestGatewayComponent,
        sam_app_under_test: SamAgentApp,
        a2a_message_validator: A2AMessageValidator,
    ):
        """Verify datetime embeds are resolved in streaming chunks."""
        scenario_id = "test_datetime_embed_streaming"

        # Prime LLM with artifact containing datetime embed
        llm_response = {
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": (
                            "«««save_artifact: filename=\"timestamp.txt\" mime_type=\"text/plain\"\n"
                            "This file was created with sufficient padding text to trigger chunking.\n"
                            "Creation time: «datetime:iso»\n"
                            "More padding to ensure multiple chunks are generated during streaming.\n"
                            "»»»"
                        ),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }
        prime_llm_server(test_llm_server, [llm_response])

        # Submit test input
        test_input_data = create_gateway_input_data(
            target_agent="TestAgent",
            user_identity="embed_test_user@example.com",
            text_parts_content=["Create a timestamp file"],
            scenario_id=scenario_id,
        )
        task_id = await submit_test_input(
            test_gateway_app_instance, test_input_data, scenario_id
        )

        # Capture all events
        all_events = await get_all_task_events(
            test_gateway_app_instance, task_id, overall_timeout=10.0
        )

        # Extract artifact progress chunks
        chunks = extract_artifact_progress_chunks(all_events)

        # Verify we got chunks
        assert len(chunks) > 0, f"Scenario {scenario_id}: Expected artifact chunks"

        # Combine all chunks
        all_chunks_text = "".join(chunks)

        # Verify datetime was resolved (should contain ISO format timestamp)
        # ISO format contains hyphens and colons: 2025-01-15T10:30:00
        assert "-" in all_chunks_text and ":" in all_chunks_text, (
            f"Scenario {scenario_id}: Expected ISO datetime format in chunks. "
            f"Chunks: {chunks}"
        )

        # Verify unresolved embed does NOT appear
        assert "«datetime:iso»" not in all_chunks_text, (
            f"Scenario {scenario_id}: Unresolved datetime embed should not appear. "
            f"Chunks: {chunks}"
        )

        # Verify no partial embeds
        open_count = all_chunks_text.count("«")
        close_count = all_chunks_text.count("»")
        assert open_count == close_count, (
            f"Scenario {scenario_id}: Partial embeds detected"
        )

        print(f"Scenario {scenario_id}: Successfully verified datetime embed resolution")

    async def test_uuid_embed_resolved_in_streaming_chunks(
        self,
        test_llm_server: TestLLMServer,
        test_gateway_app_instance: TestGatewayComponent,
        sam_app_under_test: SamAgentApp,
        a2a_message_validator: A2AMessageValidator,
    ):
        """Verify UUID embeds are resolved in streaming chunks."""
        scenario_id = "test_uuid_embed_streaming"

        # Prime LLM with artifact containing UUID embed
        llm_response = {
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": (
                            "«««save_artifact: filename=\"uuid_test.txt\" mime_type=\"text/plain\"\n"
                            "This file contains a UUID with padding to ensure chunking behavior works.\n"
                            "Generated ID: «uuid:»\n"
                            "Additional padding text to make the artifact long enough for multiple chunks.\n"
                            "»»»"
                        ),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }
        prime_llm_server(test_llm_server, [llm_response])

        # Submit test input
        test_input_data = create_gateway_input_data(
            target_agent="TestAgent",
            user_identity="embed_test_user@example.com",
            text_parts_content=["Create a UUID file"],
            scenario_id=scenario_id,
        )
        task_id = await submit_test_input(
            test_gateway_app_instance, test_input_data, scenario_id
        )

        # Capture all events
        all_events = await get_all_task_events(
            test_gateway_app_instance, task_id, overall_timeout=10.0
        )

        # Extract artifact progress chunks
        chunks = extract_artifact_progress_chunks(all_events)

        # Verify we got chunks
        assert len(chunks) > 0, f"Scenario {scenario_id}: Expected artifact chunks"

        # Combine all chunks
        all_chunks_text = "".join(chunks)

        # Verify UUID was resolved (UUID format: 8-4-4-4-12 hex digits with hyphens)
        # Count hyphens - a UUID has exactly 4 hyphens
        import re
        uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        has_uuid = re.search(uuid_pattern, all_chunks_text, re.IGNORECASE)

        assert has_uuid is not None, (
            f"Scenario {scenario_id}: Expected UUID format in chunks. "
            f"Chunks: {chunks}"
        )

        # Verify unresolved embed does NOT appear
        assert "«uuid:»" not in all_chunks_text, (
            f"Scenario {scenario_id}: Unresolved UUID embed should not appear. "
            f"Chunks: {chunks}"
        )

        # Verify no partial embeds
        open_count = all_chunks_text.count("«")
        close_count = all_chunks_text.count("»")
        assert open_count == close_count, (
            f"Scenario {scenario_id}: Partial embeds detected"
        )

        print(f"Scenario {scenario_id}: Successfully verified UUID embed resolution")
