"""
Integration tests for artifact deletion with metadata cleanup.

Tests the bug fix for DATAGO-121102: ensuring that when artifacts are deleted,
both the data artifact AND the associated metadata artifact (.metadata.json)
are properly removed from storage.

These tests verify:
1. HTTP API layer: Project deletion endpoint calls correct helper function
2. Service layer: delete_artifact_with_metadata removes both data and metadata
3. Multiple versions of both artifacts are deleted
4. Orphaned metadata files don't accumulate
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from google.genai import types as adk_types
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter
from sam_test_infrastructure.artifact_service.service import TestInMemoryArtifactService
from solace_agent_mesh.agent.utils.artifact_helpers import (
    save_artifact_with_metadata,
    delete_artifact_with_metadata,
    METADATA_SUFFIX,
)


class TestProjectArtifactDeletionHTTPAPI:
    """Tests for HTTP API layer - verifying endpoints call the right helper"""

    def test_delete_project_artifact_endpoint_exists(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
    ):
        """Test that the DELETE endpoint exists for project artifacts"""
        # Setup: Create a project
        project_id = "test-delete-endpoint"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Delete Endpoint Test",
            user_id="sam_dev_user",
        )

        # Act: Try to delete an artifact (even if it doesn't exist)
        response = api_client.delete(
            f"/api/v1/projects/{project_id}/artifacts/test.txt"
        )

        # Assert: Should not return 404 (endpoint exists)
        # May return 200 (with error status) or 500, but not 404
        assert response.status_code != 404, "Delete endpoint should exist"

    @patch('solace_agent_mesh.gateway.http_sse.services.project_service.delete_artifact_with_metadata')
    def test_delete_project_artifact_calls_helper_function(
        self,
        mock_delete_with_metadata,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
    ):
        """Test that deleting a project artifact calls delete_artifact_with_metadata"""
        # Setup the mock to return success
        mock_delete_with_metadata.return_value = {
            "status": "success",
            "data_filename": "test.txt",
            "metadata_filename": f"test.txt{METADATA_SUFFIX}",
            "message": "Both artifacts deleted successfully",
        }

        # Setup: Create a project
        project_id = "test-calls-helper"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Helper Function Test",
            user_id="sam_dev_user",
        )

        # Act: Delete an artifact
        response = api_client.delete(
            f"/api/v1/projects/{project_id}/artifacts/test.txt"
        )

        # Assert: delete_artifact_with_metadata was called
        assert mock_delete_with_metadata.called, \
            "delete_artifact_with_metadata should be called"

        # Verify it was called with correct parameters
        call_args = mock_delete_with_metadata.call_args
        assert call_args is not None
        assert call_args.kwargs["filename"] == "test.txt"
        assert call_args.kwargs["user_id"] == "sam_dev_user"
        assert f"project-{project_id}" in call_args.kwargs["session_id"]


class TestArtifactDeletionServiceLayer:
    """Tests for service layer - verifying actual artifact deletion with real artifact service"""

    async def test_delete_artifact_with_metadata_removes_both(
        self,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """
        Core bug fix test: Verify delete_artifact_with_metadata removes both
        data and metadata artifacts
        """
        # Setup: Save an artifact with metadata
        test_content = b"Test CSV data\nrow1,row2\nvalue1,value2"

        print("\n[TEST] Step 1: Creating artifact with metadata...")
        await save_artifact_with_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
            filename="test_data.csv",
            content_bytes=test_content,
            mime_type="text/csv",
            metadata_dict={"description": "Test CSV file", "rows": 2},
            timestamp=datetime.now(timezone.utc),
        )
        print("[TEST] ✓ Artifact created")

        # Verify both artifacts exist before deletion
        print("\n[TEST] Step 2: Verifying both data and metadata artifacts exist...")
        data_keys = await test_artifact_service_instance.list_artifact_keys(
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
        )
        print(f"[TEST] Found {len(data_keys)} artifacts: {data_keys}")
        assert "test_data.csv" in data_keys, "Data artifact should exist"
        assert f"test_data.csv{METADATA_SUFFIX}" in data_keys, "Metadata artifact should exist"
        assert len(data_keys) == 2, f"Should have 2 artifacts, got {len(data_keys)}: {data_keys}"
        print("[TEST] ✓ Both data and metadata artifacts confirmed to exist")

        # Act: Delete using the helper function
        print("\n[TEST] Step 3: Deleting artifacts using delete_artifact_with_metadata()...")
        result = await delete_artifact_with_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
            filename="test_data.csv",
        )
        print(f"[TEST] Delete result: {result}")

        # Assert: Function returns success
        assert result["status"] == "success", f"Expected success, got {result}"
        print("[TEST] ✓ Deletion completed successfully")

        # Verify both artifacts are deleted
        print("\n[TEST] Step 4: Verifying both artifacts are deleted...")
        keys_after = await test_artifact_service_instance.list_artifact_keys(
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
        )
        print(f"[TEST] Artifacts remaining: {len(keys_after)} - {keys_after}")
        assert len(keys_after) == 0, \
            f"All artifacts should be deleted, but found {len(keys_after)}: {keys_after}"
        print("[TEST] ✓ Both artifacts confirmed deleted - NO ORPHANED METADATA!")
        print("\n[TEST] ✅ BUG FIX VERIFIED: Both data and metadata deleted successfully\n")

    async def test_delete_multiple_versions_removes_all(
        self,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """Test that deleting an artifact removes all versions of both data and metadata"""
        # Setup: Create 3 versions of an artifact with metadata
        for version in range(3):
            test_content = f"Test data version {version}".encode()

            await save_artifact_with_metadata(
                artifact_service=test_artifact_service_instance,
                app_name="TestApp",
                user_id="test_user",
                session_id="test_session",
                filename="versioned_data.txt",
                content_bytes=test_content,
                mime_type="text/plain",
                metadata_dict={"version": version},
                timestamp=datetime.now(timezone.utc),
            )

        # Verify versions exist
        data_versions = await test_artifact_service_instance.list_versions(
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
            filename="versioned_data.txt",
        )
        assert len(data_versions) == 3, f"Should have 3 data versions, got {len(data_versions)}"

        metadata_versions = await test_artifact_service_instance.list_versions(
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
            filename=f"versioned_data.txt{METADATA_SUFFIX}",
        )
        assert len(metadata_versions) == 3, f"Should have 3 metadata versions, got {len(metadata_versions)}"

        # Act: Delete the artifact
        result = await delete_artifact_with_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
            filename="versioned_data.txt",
        )

        # Assert: All versions deleted
        assert result["status"] == "success"

        data_versions_after = await test_artifact_service_instance.list_versions(
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
            filename="versioned_data.txt",
        )
        assert len(data_versions_after) == 0, "All data versions should be deleted"

        metadata_versions_after = await test_artifact_service_instance.list_versions(
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
            filename=f"versioned_data.txt{METADATA_SUFFIX}",
        )
        assert len(metadata_versions_after) == 0, "All metadata versions should be deleted"

    async def test_delete_when_metadata_missing_partial_success(
        self,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """Test graceful handling when data exists but metadata is missing"""
        # Setup: Create only the data artifact (no metadata)
        test_content = b"Data without metadata"
        artifact_part = adk_types.Part.from_bytes(data=test_content, mime_type="text/plain")

        await test_artifact_service_instance.save_artifact(
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
            filename="no_metadata.txt",
            artifact=artifact_part,
        )

        # Verify only data exists
        keys_before = await test_artifact_service_instance.list_artifact_keys(
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
        )
        assert "no_metadata.txt" in keys_before
        assert f"no_metadata.txt{METADATA_SUFFIX}" not in keys_before

        # Act: Delete the artifact
        result = await delete_artifact_with_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
            filename="no_metadata.txt",
        )

        # Assert: Should succeed or partial success
        assert result["status"] in ["success", "partial success"], \
            f"Expected success or partial success, got {result['status']}"

        # Data should be deleted
        keys_after = await test_artifact_service_instance.list_artifact_keys(
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
        )
        assert "no_metadata.txt" not in keys_after, "Data artifact should be deleted"

    async def test_no_orphaned_metadata_after_multiple_deletions(
        self,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """
        Verify the bug doesn't occur: No orphaned metadata files after deleting
        multiple artifacts
        """
        # Setup: Create 3 different artifacts with metadata
        test_files = [
            ("report1.csv", b"Report 1 data", "text/csv"),
            ("report2.csv", b"Report 2 data", "text/csv"),
            ("document.txt", b"Document content", "text/plain"),
        ]

        for filename, content, mime_type in test_files:
            await save_artifact_with_metadata(
                artifact_service=test_artifact_service_instance,
                app_name="TestApp",
                user_id="test_user",
                session_id="test_session",
                filename=filename,
                content_bytes=content,
                mime_type=mime_type,
                metadata_dict={"description": f"Test file {filename}"},
                timestamp=datetime.now(timezone.utc),
            )

        # Verify all artifacts exist (3 data + 3 metadata = 6 total)
        all_keys_before = await test_artifact_service_instance.list_artifact_keys(
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
        )
        assert len(all_keys_before) == 6, \
            f"Should have 6 artifacts (3 data + 3 metadata), got {len(all_keys_before)}: {all_keys_before}"

        # Act: Delete each artifact
        for filename, _, _ in test_files:
            result = await delete_artifact_with_metadata(
                artifact_service=test_artifact_service_instance,
                app_name="TestApp",
                user_id="test_user",
                session_id="test_session",
                filename=filename,
            )
            assert result["status"] == "success", f"Failed to delete {filename}: {result}"

        # Assert: NO artifacts remain (no orphaned metadata)
        all_keys_after = await test_artifact_service_instance.list_artifact_keys(
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
        )
        assert len(all_keys_after) == 0, \
            f"All artifacts should be deleted, but found {len(all_keys_after)}: {all_keys_after}"

    async def test_delete_with_special_characters_in_filename(
        self,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """Test deletion works correctly with special characters in filename"""
        # Setup: Create artifact with special characters
        special_filename = "test-file_with.special-chars.csv"
        test_content = b"Special file content"

        await save_artifact_with_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
            filename=special_filename,
            content_bytes=test_content,
            mime_type="text/csv",
            metadata_dict={"description": "Special chars test"},
            timestamp=datetime.now(timezone.utc),
        )

        # Verify both exist
        keys_before = await test_artifact_service_instance.list_artifact_keys(
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
        )
        assert special_filename in keys_before
        assert f"{special_filename}{METADATA_SUFFIX}" in keys_before

        # Act: Delete
        result = await delete_artifact_with_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
            filename=special_filename,
        )

        # Assert: Both deleted
        assert result["status"] == "success"

        keys_after = await test_artifact_service_instance.list_artifact_keys(
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
        )
        assert len(keys_after) == 0, f"All artifacts should be deleted, found: {keys_after}"

    async def test_delete_nonexistent_artifact_returns_appropriate_status(
        self,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """Test that deleting a non-existent artifact returns appropriate status"""
        # Act: Try to delete non-existent artifact
        result = await delete_artifact_with_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
            filename="nonexistent.txt",
        )

        # Assert: Should return success (idempotent - artifact doesn't exist = goal achieved)
        # or error/partial success depending on implementation
        assert result["status"] in ["success", "error", "partial success"], \
            f"Expected valid status, got {result['status']}"
        assert "message" in result
        assert isinstance(result["message"], str)

    async def test_delete_artifact_with_metadata_response_format(
        self,
        test_artifact_service_instance: TestInMemoryArtifactService,
    ):
        """Test that delete_artifact_with_metadata returns expected response format"""
        # Setup: Create an artifact
        await save_artifact_with_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
            filename="format_test.txt",
            content_bytes=b"test",
            mime_type="text/plain",
            metadata_dict={},
            timestamp=datetime.now(timezone.utc),
        )

        # Act: Delete
        result = await delete_artifact_with_metadata(
            artifact_service=test_artifact_service_instance,
            app_name="TestApp",
            user_id="test_user",
            session_id="test_session",
            filename="format_test.txt",
        )

        # Assert: Response format is correct
        assert "status" in result, "Response should contain 'status' field"
        assert result["status"] in ["success", "partial success", "error"]

        assert "data_filename" in result, "Response should contain 'data_filename'"
        assert result["data_filename"] == "format_test.txt"

        assert "metadata_filename" in result, "Response should contain 'metadata_filename'"
        assert result["metadata_filename"] == f"format_test.txt{METADATA_SUFFIX}"

        assert "message" in result, "Response should contain 'message'"
        assert isinstance(result["message"], str)
