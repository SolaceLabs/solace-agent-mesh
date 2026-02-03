"""
Integration tests for artifact services.
Tests filesystem and in-memory artifact storage implementations.
"""

import pytest
from typing import Dict, Any
from google.genai import types as adk_types
from sam_test_infrastructure.llm_server.server import TestLLMServer
from sam_test_infrastructure.gateway_interface.component import TestGatewayComponent
from sam_test_infrastructure.a2a_validator.validator import A2AMessageValidator
from sam_test_infrastructure.artifact_service.service import TestInMemoryArtifactService
from solace_agent_mesh.agent.sac.app import SamAgentApp
from solace_agent_mesh.agent.utils.artifact_helpers import (
    save_artifact_with_metadata,
    load_artifact_content_or_metadata,
    get_artifact_info_list,
)
from solace_agent_mesh.common.constants import (
    ARTIFACT_TAG_USER_UPLOADED,
    ARTIFACT_TAG_WORKING,
)
from datetime import datetime, timezone

from tests.integration.scenarios_programmatic.test_helpers import (
    prime_llm_server,
    create_gateway_input_data,
    submit_test_input,
    get_all_task_events,
    extract_outputs_from_event_list,
    assert_final_response_text_contains,
)

pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.agent,
]


class TestArtifactServiceOperations:
    """Tests for basic artifact service operations."""

    async def test_save_and_load_artifact(
        self,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """Test saving and loading an artifact."""
        scenario_id = "test_save_load_artifact"
        
        # Save an artifact
        content = b"Hello, World!"
        artifact_part = adk_types.Part.from_bytes(data=content, mime_type="text/plain")
        
        version = await test_artifact_service_instance.save_artifact(
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_123",
            filename="greeting.txt",
            artifact=artifact_part
        )
        
        assert version == 0, f"Scenario {scenario_id}: Expected version 0, got {version}"
        
        # Load the artifact
        loaded_artifact = await test_artifact_service_instance.load_artifact(
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_123",
            filename="greeting.txt"
        )
        
        assert loaded_artifact is not None, f"Scenario {scenario_id}: Artifact not found"
        assert loaded_artifact.inline_data.data == content, f"Scenario {scenario_id}: Content mismatch"
        
        print(f"Scenario {scenario_id}: Artifact saved and loaded successfully")

    async def test_artifact_versioning(
        self,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """Test artifact versioning."""
        scenario_id = "test_artifact_versioning"
        
        # Save multiple versions
        for i in range(3):
            content = f"Version {i+1}".encode()
            artifact_part = adk_types.Part.from_bytes(data=content, mime_type="text/plain")
            
            version = await test_artifact_service_instance.save_artifact(
                app_name="TestAgent",
                user_id="test_user@example.com",
                session_id="test_session_123",
                filename="versioned.txt",
                artifact=artifact_part
            )
            
            assert version == i, f"Scenario {scenario_id}: Expected version {i}, got {version}"
        
        # List versions
        versions = await test_artifact_service_instance.list_versions(
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_123",
            filename="versioned.txt"
        )
        
        assert len(versions) == 3, f"Scenario {scenario_id}: Expected 3 versions, got {len(versions)}"
        assert versions == [0, 1, 2], f"Scenario {scenario_id}: Version list mismatch"
        
        # Load specific version
        v2_artifact = await test_artifact_service_instance.load_artifact(
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_123",
            filename="versioned.txt",
            version=2
        )
        
        assert v2_artifact.inline_data.data == b"Version 3", f"Scenario {scenario_id}: Version 2 content mismatch"
        
        print(f"Scenario {scenario_id}: Artifact versioning works correctly")

    async def test_list_artifact_keys(
        self,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """Test listing artifact keys."""
        scenario_id = "test_list_artifact_keys"
        
        # Save multiple artifacts
        filenames = ["file1.txt", "file2.txt", "file3.txt"]
        for filename in filenames:
            content = f"Content of {filename}".encode()
            artifact_part = adk_types.Part.from_bytes(data=content, mime_type="text/plain")
            
            await test_artifact_service_instance.save_artifact(
                app_name="TestAgent",
                user_id="test_user@example.com",
                session_id="test_session_123",
                filename=filename,
                artifact=artifact_part
            )
        
        # List artifacts
        keys = await test_artifact_service_instance.list_artifact_keys(
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_123"
        )
        
        assert len(keys) == 3, f"Scenario {scenario_id}: Expected 3 keys, got {len(keys)}"
        assert set(keys) == set(filenames), f"Scenario {scenario_id}: Key list mismatch"
        
        print(f"Scenario {scenario_id}: Artifact keys listed successfully")

    async def test_delete_artifact(
        self,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """Test deleting an artifact."""
        scenario_id = "test_delete_artifact"
        
        # Save an artifact
        content = b"To be deleted"
        artifact_part = adk_types.Part.from_bytes(data=content, mime_type="text/plain")
        
        await test_artifact_service_instance.save_artifact(
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_123",
            filename="delete_me.txt",
            artifact=artifact_part
        )
        
        # Verify it exists
        keys_before = await test_artifact_service_instance.list_artifact_keys(
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_123"
        )
        assert "delete_me.txt" in keys_before, f"Scenario {scenario_id}: Artifact not found before deletion"
        
        # Delete it
        await test_artifact_service_instance.delete_artifact(
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_123",
            filename="delete_me.txt"
        )
        
        # Verify it's gone
        keys_after = await test_artifact_service_instance.list_artifact_keys(
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_123"
        )
        assert "delete_me.txt" not in keys_after, f"Scenario {scenario_id}: Artifact still exists after deletion"
        
        print(f"Scenario {scenario_id}: Artifact deleted successfully")


class TestArtifactToolIntegration:
    """Tests for artifact tool integration."""

    async def test_list_artifacts_tool(
        self,
        test_llm_server: TestLLMServer,
        test_gateway_app_instance: TestGatewayComponent,
        sam_app_under_test: SamAgentApp,
        test_artifact_service_instance: TestInMemoryArtifactService,
        a2a_message_validator: A2AMessageValidator,
    ):
        """Test list_artifacts tool."""
        scenario_id = "test_list_artifacts_tool"
        
        # Pre-populate some artifacts
        component = sam_app_under_test.get_component()
        artifact_service = component.artifact_service
        
        for i in range(2):
            content = f"Test artifact {i}".encode()
            await save_artifact_with_metadata(
                artifact_service=artifact_service,
                app_name="TestAgent",
                user_id="artifact_user@example.com",
                session_id="artifact_session",
                filename=f"test_{i}.txt",
                content_bytes=content,
                mime_type="text/plain",
                metadata_dict={"index": i},
                timestamp=datetime.now(timezone.utc)
            )
        
        # Prime LLM to call list_artifacts tool
        tool_call_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": "call_list_123",
                        "type": "function",
                        "function": {
                            "name": "list_artifacts",
                            "arguments": '{}'
                        }
                    }]
                },
                "finish_reason": "tool_calls"
            }]
        }
        
        final_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "I found the artifacts you requested."
                },
                "finish_reason": "stop"
            }]
        }
        
        prime_llm_server(test_llm_server, [tool_call_response, final_response])
        
        # Create test input
        test_input = create_gateway_input_data(
            target_agent="TestAgent",
            user_identity="artifact_user@example.com",
            text_parts_content=["List all my artifacts"],
            scenario_id=scenario_id,
            external_context_override={"a2a_session_id": "artifact_session"}
        )
        
        # Submit task
        task_id = await submit_test_input(test_gateway_app_instance, test_input, scenario_id)
        
        # Get events
        all_events = await get_all_task_events(test_gateway_app_instance, task_id, overall_timeout=10.0)
        
        # Verify response
        terminal_event, stream_text, terminal_text = extract_outputs_from_event_list(all_events, scenario_id)
        content = stream_text if stream_text else terminal_text
        
        assert_final_response_text_contains(
            content,
            "found",
            scenario_id,
            terminal_event
        )
        
        print(f"Scenario {scenario_id}: list_artifacts tool executed successfully")

    async def test_load_artifact_tool(
        self,
        test_llm_server: TestLLMServer,
        test_gateway_app_instance: TestGatewayComponent,
        sam_app_under_test: SamAgentApp,
        test_artifact_service_instance: TestInMemoryArtifactService,
        a2a_message_validator: A2AMessageValidator,
    ):
        """Test load_artifact tool."""
        scenario_id = "test_load_artifact_tool"
        
        # Pre-populate an artifact
        component = sam_app_under_test.get_component()
        artifact_service = component.artifact_service
        
        content = b"This is the artifact content"
        await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name="TestAgent",
            user_id="artifact_user@example.com",
            session_id="artifact_session",
            filename="data.txt",
            content_bytes=content,
            mime_type="text/plain",
            metadata_dict={"type": "data"},
            timestamp=datetime.now(timezone.utc)
        )
        
        # Prime LLM to call load_artifact tool
        tool_call_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": "call_load_123",
                        "type": "function",
                        "function": {
                            "name": "load_artifact",
                            "arguments": '{"filename": "data.txt"}'
                        }
                    }]
                },
                "finish_reason": "tool_calls"
            }]
        }
        
        final_response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "I loaded the artifact successfully."
                },
                "finish_reason": "stop"
            }]
        }
        
        prime_llm_server(test_llm_server, [tool_call_response, final_response])
        
        # Create test input
        test_input = create_gateway_input_data(
            target_agent="TestAgent",
            user_identity="artifact_user@example.com",
            text_parts_content=["Load the data.txt artifact"],
            scenario_id=scenario_id,
            external_context_override={"a2a_session_id": "artifact_session"}
        )
        
        # Submit task
        task_id = await submit_test_input(test_gateway_app_instance, test_input, scenario_id)
        
        # Get events
        all_events = await get_all_task_events(test_gateway_app_instance, task_id, overall_timeout=10.0)
        
        # Verify response
        terminal_event, stream_text, terminal_text = extract_outputs_from_event_list(all_events, scenario_id)
        content_result = stream_text if stream_text else terminal_text
        
        assert_final_response_text_contains(
            content_result,
            "loaded",
            scenario_id,
            terminal_event
        )
        
        print(f"Scenario {scenario_id}: load_artifact tool executed successfully")


class TestArtifactTagging:
    """Tests for artifact tagging functionality."""

    async def test_tags_stored_in_metadata(
        self,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """Test that tags are correctly stored in artifact metadata."""
        scenario_id = "test_tags_stored_in_metadata"

        # Save artifact with tags
        content = b"Content with tags"
        test_tags = ["__internal", "custom_tag"]

        result = await save_artifact_with_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_tags",
            filename="tagged_file.txt",
            content_bytes=content,
            mime_type="text/plain",
            metadata_dict={"description": "File with tags"},
            timestamp=datetime.now(timezone.utc),
            tags=test_tags,
        )

        assert result["status"] == "success", f"Scenario {scenario_id}: Save failed"

        # Load metadata and verify tags are stored
        metadata_result = await load_artifact_content_or_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_tags",
            filename="tagged_file.txt",
            version="latest",
            load_metadata_only=True,
        )

        assert metadata_result["status"] == "success", f"Scenario {scenario_id}: Load metadata failed"
        assert "tags" in metadata_result["metadata"], f"Scenario {scenario_id}: Tags not in metadata"
        assert metadata_result["metadata"]["tags"] == test_tags, f"Scenario {scenario_id}: Tags mismatch"

        print(f"Scenario {scenario_id}: Tags correctly stored in metadata")

    async def test_user_uploaded_tag(
        self,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """Test that user-uploaded artifacts can be tagged with __user_uploaded."""
        scenario_id = "test_user_uploaded_tag"

        content = b"User uploaded content"

        result = await save_artifact_with_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_user_upload",
            filename="user_upload.txt",
            content_bytes=content,
            mime_type="text/plain",
            metadata_dict={},
            timestamp=datetime.now(timezone.utc),
            tags=[ARTIFACT_TAG_USER_UPLOADED],
        )

        assert result["status"] == "success", f"Scenario {scenario_id}: Save failed"

        # Verify tag via metadata load
        metadata_result = await load_artifact_content_or_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_user_upload",
            filename="user_upload.txt",
            version="latest",
            load_metadata_only=True,
        )

        assert ARTIFACT_TAG_USER_UPLOADED in metadata_result["metadata"]["tags"], \
            f"Scenario {scenario_id}: __user_uploaded tag not found"

        print(f"Scenario {scenario_id}: __user_uploaded tag correctly stored")

    async def test_working_tag(
        self,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """Test that working artifacts can be tagged with __working."""
        scenario_id = "test_working_tag"

        content = b"Working artifact content"

        result = await save_artifact_with_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_working",
            filename="working_file.txt",
            content_bytes=content,
            mime_type="text/plain",
            metadata_dict={},
            timestamp=datetime.now(timezone.utc),
            tags=[ARTIFACT_TAG_WORKING],
        )

        assert result["status"] == "success", f"Scenario {scenario_id}: Save failed"

        # Verify tag via metadata load
        metadata_result = await load_artifact_content_or_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_working",
            filename="working_file.txt",
            version="latest",
            load_metadata_only=True,
        )

        assert ARTIFACT_TAG_WORKING in metadata_result["metadata"]["tags"], \
            f"Scenario {scenario_id}: __working tag not found"

        print(f"Scenario {scenario_id}: __working tag correctly stored")

    async def test_tags_in_artifact_info_list(
        self,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """Test that tags are included in get_artifact_info_list results."""
        scenario_id = "test_tags_in_artifact_info_list"

        # Save artifacts with different tags
        artifacts_to_create = [
            ("user_file.txt", [ARTIFACT_TAG_USER_UPLOADED]),
            ("working_file.txt", [ARTIFACT_TAG_WORKING]),
            ("multi_tag.txt", [ARTIFACT_TAG_WORKING, "custom"]),
        ]

        for filename, tags in artifacts_to_create:
            await save_artifact_with_metadata(
                artifact_service=test_artifact_service_instance,
                app_name="TestAgent",
                user_id="test_user@example.com",
                session_id="test_session_list",
                filename=filename,
                content_bytes=b"Test content",
                mime_type="text/plain",
                metadata_dict={},
                timestamp=datetime.now(timezone.utc),
                tags=tags,
            )

        # Get artifact info list
        artifact_list = await get_artifact_info_list(
            artifact_service=test_artifact_service_instance,
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_list",
        )

        # Verify tags are included for each artifact
        artifacts_by_name = {a.filename: a for a in artifact_list}

        assert ARTIFACT_TAG_USER_UPLOADED in artifacts_by_name["user_file.txt"].tags, \
            f"Scenario {scenario_id}: user_file.txt missing __user_uploaded tag"
        assert ARTIFACT_TAG_WORKING in artifacts_by_name["working_file.txt"].tags, \
            f"Scenario {scenario_id}: working_file.txt missing __working tag"
        assert ARTIFACT_TAG_WORKING in artifacts_by_name["multi_tag.txt"].tags, \
            f"Scenario {scenario_id}: multi_tag.txt missing __working tag"
        assert "custom" in artifacts_by_name["multi_tag.txt"].tags, \
            f"Scenario {scenario_id}: multi_tag.txt missing custom tag"

        print(f"Scenario {scenario_id}: Tags correctly included in artifact info list")

    async def test_artifact_without_tags(
        self,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """Test that artifacts without tags handle gracefully (None or empty)."""
        scenario_id = "test_artifact_without_tags"

        content = b"No tags content"

        result = await save_artifact_with_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_no_tags",
            filename="no_tags.txt",
            content_bytes=content,
            mime_type="text/plain",
            metadata_dict={},
            timestamp=datetime.now(timezone.utc),
            tags=None,  # Explicitly no tags
        )

        assert result["status"] == "success", f"Scenario {scenario_id}: Save failed"

        # Verify metadata doesn't have tags key (or has None)
        metadata_result = await load_artifact_content_or_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_no_tags",
            filename="no_tags.txt",
            version="latest",
            load_metadata_only=True,
        )

        # Tags should not be present when saved as None
        assert metadata_result["metadata"].get("tags") is None, \
            f"Scenario {scenario_id}: Expected no tags, got {metadata_result['metadata'].get('tags')}"

        # Verify artifact info list handles this gracefully
        artifact_list = await get_artifact_info_list(
            artifact_service=test_artifact_service_instance,
            app_name="TestAgent",
            user_id="test_user@example.com",
            session_id="test_session_no_tags",
        )

        assert len(artifact_list) == 1, f"Scenario {scenario_id}: Expected 1 artifact"
        assert artifact_list[0].tags is None, \
            f"Scenario {scenario_id}: Expected None tags in ArtifactInfo"

        print(f"Scenario {scenario_id}: Artifacts without tags handled gracefully")