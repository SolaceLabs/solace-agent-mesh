"""
Unit tests for artifact copy utility functions.
Tests cover project context detection and artifact copying from projects to sessions.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils import (
    has_pending_project_context,
    copy_project_artifacts_to_session,
)


class TestHasPendingProjectContext:
    """Test the has_pending_project_context function."""

    @pytest.fixture
    def mock_artifact_service(self):
        """Mock artifact service for testing."""
        service = Mock()
        service.list_artifact_versions = AsyncMock()
        return service

    @pytest.fixture
    def mock_db(self):
        """Mock database session for testing."""
        return Mock()

    @pytest.mark.asyncio
    async def test_has_pending_project_context_finds_flag(
        self, mock_artifact_service, mock_db
    ):
        """Test that function detects artifacts with project_context_pending=True."""
        # Mock artifact info list
        artifact_info1 = Mock()
        artifact_info1.filename = "file1.txt"
        artifact_info2 = Mock()
        artifact_info2.filename = "file2.txt"

        with patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.get_artifact_info_list"
        ) as mock_get_list, patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.load_artifact_content_or_metadata"
        ) as mock_load:
            mock_get_list.return_value = [artifact_info1, artifact_info2]

            # First artifact has no flag, second has the flag
            mock_load.side_effect = [
                {"status": "success", "metadata": {}},
                {
                    "status": "success",
                    "metadata": {"project_context_pending": True},
                },
            ]

            result = await has_pending_project_context(
                user_id="user123",
                session_id="session456",
                artifact_service=mock_artifact_service,
                app_name="testapp",
                db=mock_db,
            )

            assert result is True
            assert mock_get_list.call_count == 1
            assert mock_load.call_count == 2

    @pytest.mark.asyncio
    async def test_has_pending_project_context_no_flag(
        self, mock_artifact_service, mock_db
    ):
        """Test that function returns False when no flag exists."""
        # Mock artifact info list
        artifact_info1 = Mock()
        artifact_info1.filename = "file1.txt"
        artifact_info2 = Mock()
        artifact_info2.filename = "file2.txt"

        with patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.get_artifact_info_list"
        ) as mock_get_list, patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.load_artifact_content_or_metadata"
        ) as mock_load:
            mock_get_list.return_value = [artifact_info1, artifact_info2]

            # Neither artifact has the flag
            mock_load.side_effect = [
                {"status": "success", "metadata": {}},
                {"status": "success", "metadata": {"other_field": "value"}},
            ]

            result = await has_pending_project_context(
                user_id="user123",
                session_id="session456",
                artifact_service=mock_artifact_service,
                app_name="testapp",
                db=mock_db,
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_has_pending_project_context_no_artifacts(
        self, mock_artifact_service, mock_db
    ):
        """Test that function returns False when session has no artifacts."""
        with patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.get_artifact_info_list"
        ) as mock_get_list:
            mock_get_list.return_value = []

            result = await has_pending_project_context(
                user_id="user123",
                session_id="session456",
                artifact_service=mock_artifact_service,
                app_name="testapp",
                db=mock_db,
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_has_pending_project_context_handles_errors(
        self, mock_artifact_service, mock_db
    ):
        """Test that function handles errors gracefully."""
        with patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.get_artifact_info_list"
        ) as mock_get_list:
            mock_get_list.side_effect = Exception("Service error")

            result = await has_pending_project_context(
                user_id="user123",
                session_id="session456",
                artifact_service=mock_artifact_service,
                app_name="testapp",
                db=mock_db,
            )

            assert result is False


class TestCopyProjectArtifactsToSession:
    """Test the copy_project_artifacts_to_session function."""

    @pytest.fixture
    def mock_project_service(self):
        """Mock project service for testing."""
        service = Mock()
        service.app_name = "testapp"
        return service

    @pytest.fixture
    def mock_component(self):
        """Mock WebUIBackendComponent for testing."""
        component = Mock()
        return component

    @pytest.fixture
    def mock_db(self):
        """Mock database session for testing."""
        return Mock()

    @pytest.fixture
    def mock_project(self):
        """Mock project object for testing."""
        project = Mock()
        project.id = "project123"
        project.user_id = "project_user"
        return project

    @pytest.mark.asyncio
    async def test_copy_project_artifacts_sets_pending_flag(
        self, mock_project_service, mock_component, mock_db, mock_project
    ):
        """Test that artifacts are saved with project_context_pending=True."""
        mock_artifact_service = Mock()
        mock_component.get_shared_artifact_service.return_value = mock_artifact_service
        mock_project_service.get_project.return_value = mock_project

        # Mock project artifacts
        artifact_info1 = Mock()
        artifact_info1.filename = "file1.txt"
        artifact_info2 = Mock()
        artifact_info2.filename = "file2.txt"

        with patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.get_artifact_info_list"
        ) as mock_get_list, patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.load_artifact_content_or_metadata"
        ) as mock_load, patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.save_artifact_with_metadata"
        ) as mock_save:
            # First call returns project artifacts, second returns empty session
            mock_get_list.side_effect = [[artifact_info1, artifact_info2], []]

            # Mock loading artifact content and metadata
            mock_load.side_effect = [
                # file1.txt content
                {"status": "success", "raw_bytes": b"content1", "mime_type": "text/plain"},
                # file1.txt metadata
                {"status": "success", "metadata": {"original": "metadata1"}},
                # file2.txt content
                {"status": "success", "raw_bytes": b"content2", "mime_type": "text/plain"},
                # file2.txt metadata
                {"status": "success", "metadata": {"original": "metadata2"}},
            ]

            count, names = await copy_project_artifacts_to_session(
                project_id="project123",
                user_id="user123",
                session_id="session456",
                project_service=mock_project_service,
                component=mock_component,
                db=mock_db,
            )

            # Verify artifacts were saved
            assert mock_save.call_count == 2
            assert count == 2
            assert names == ["file1.txt", "file2.txt"]

            # Verify each saved artifact has project_context_pending=True
            for call in mock_save.call_args_list:
                metadata = call[1]["metadata_dict"]
                assert metadata["project_context_pending"] is True

    @pytest.mark.asyncio
    async def test_copy_project_artifacts_creates_single_version_per_artifact(
        self, mock_project_service, mock_component, mock_db, mock_project
    ):
        """CRITICAL REGRESSION TEST: Verify save_artifact_with_metadata is called exactly once per artifact."""
        mock_artifact_service = Mock()
        mock_component.get_shared_artifact_service.return_value = mock_artifact_service
        mock_project_service.get_project.return_value = mock_project

        # Mock 3 project artifacts
        artifact_info1 = Mock()
        artifact_info1.filename = "file1.txt"
        artifact_info2 = Mock()
        artifact_info2.filename = "file2.txt"
        artifact_info3 = Mock()
        artifact_info3.filename = "file3.txt"

        with patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.get_artifact_info_list"
        ) as mock_get_list, patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.load_artifact_content_or_metadata"
        ) as mock_load, patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.save_artifact_with_metadata"
        ) as mock_save:
            # First call returns project artifacts, second returns empty session
            mock_get_list.side_effect = [
                [artifact_info1, artifact_info2, artifact_info3],
                [],
            ]

            # Mock loading artifact content and metadata for 3 artifacts
            mock_load.side_effect = [
                # file1
                {"status": "success", "raw_bytes": b"content1", "mime_type": "text/plain"},
                {"status": "success", "metadata": {}},
                # file2
                {"status": "success", "raw_bytes": b"content2", "mime_type": "text/plain"},
                {"status": "success", "metadata": {}},
                # file3
                {"status": "success", "raw_bytes": b"content3", "mime_type": "text/plain"},
                {"status": "success", "metadata": {}},
            ]

            count, names = await copy_project_artifacts_to_session(
                project_id="project123",
                user_id="user123",
                session_id="session456",
                project_service=mock_project_service,
                component=mock_component,
                db=mock_db,
            )

            # CRITICAL: Verify each artifact is saved exactly once (not twice)
            assert mock_save.call_count == 3, (
                f"Expected save_artifact_with_metadata to be called exactly 3 times "
                f"(once per artifact), but was called {mock_save.call_count} times"
            )
            assert count == 3
            assert names == ["file1.txt", "file2.txt", "file3.txt"]

            # Verify the filenames match
            saved_filenames = [call[1]["filename"] for call in mock_save.call_args_list]
            assert saved_filenames == ["file1.txt", "file2.txt", "file3.txt"]

    @pytest.mark.asyncio
    async def test_copy_project_artifacts_skips_existing_artifacts(
        self, mock_project_service, mock_component, mock_db, mock_project
    ):
        """Test that deduplication logic skips existing artifacts."""
        mock_artifact_service = Mock()
        mock_component.get_shared_artifact_service.return_value = mock_artifact_service
        mock_project_service.get_project.return_value = mock_project

        # Mock project artifacts
        project_artifact1 = Mock()
        project_artifact1.filename = "file1.txt"
        project_artifact2 = Mock()
        project_artifact2.filename = "file2.txt"
        project_artifact3 = Mock()
        project_artifact3.filename = "file3.txt"

        # Mock existing session artifacts (file1 and file2 already exist)
        session_artifact1 = Mock()
        session_artifact1.filename = "file1.txt"
        session_artifact2 = Mock()
        session_artifact2.filename = "file2.txt"

        with patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.get_artifact_info_list"
        ) as mock_get_list, patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.load_artifact_content_or_metadata"
        ) as mock_load, patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.save_artifact_with_metadata"
        ) as mock_save:
            # First call returns project artifacts, second returns existing session artifacts
            mock_get_list.side_effect = [
                [project_artifact1, project_artifact2, project_artifact3],
                [session_artifact1, session_artifact2],
            ]

            # Mock loading only for file3 (the new one)
            mock_load.side_effect = [
                {"status": "success", "raw_bytes": b"content3", "mime_type": "text/plain"},
                {"status": "success", "metadata": {}},
            ]

            count, names = await copy_project_artifacts_to_session(
                project_id="project123",
                user_id="user123",
                session_id="session456",
                project_service=mock_project_service,
                component=mock_component,
                db=mock_db,
            )

            # Verify only file3.txt was copied
            assert mock_save.call_count == 1
            assert count == 1
            assert names == ["file3.txt"]

            # Verify it was file3.txt that was saved
            saved_filename = mock_save.call_args_list[0][1]["filename"]
            assert saved_filename == "file3.txt"

    @pytest.mark.asyncio
    async def test_copy_project_artifacts_returns_correct_metadata(
        self, mock_project_service, mock_component, mock_db, mock_project
    ):
        """Test that function returns correct count and artifact names."""
        mock_artifact_service = Mock()
        mock_component.get_shared_artifact_service.return_value = mock_artifact_service
        mock_project_service.get_project.return_value = mock_project

        # Mock 2 new project artifacts
        artifact_info1 = Mock()
        artifact_info1.filename = "new_file1.txt"
        artifact_info2 = Mock()
        artifact_info2.filename = "new_file2.txt"

        with patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.get_artifact_info_list"
        ) as mock_get_list, patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.load_artifact_content_or_metadata"
        ) as mock_load, patch(
            "solace_agent_mesh.gateway.http_sse.utils.artifact_copy_utils.save_artifact_with_metadata"
        ) as mock_save:
            # First call returns project artifacts, second returns empty session
            mock_get_list.side_effect = [[artifact_info1, artifact_info2], []]

            # Mock loading artifact content and metadata
            mock_load.side_effect = [
                # new_file1.txt content
                {"status": "success", "raw_bytes": b"content1", "mime_type": "text/plain"},
                # new_file1.txt metadata
                {"status": "success", "metadata": {}},
                # new_file2.txt content
                {"status": "success", "raw_bytes": b"content2", "mime_type": "text/plain"},
                # new_file2.txt metadata
                {"status": "success", "metadata": {}},
            ]

            count, names = await copy_project_artifacts_to_session(
                project_id="project123",
                user_id="user123",
                session_id="session456",
                project_service=mock_project_service,
                component=mock_component,
                db=mock_db,
            )

            # Verify return values
            assert count == 2, f"Expected count=2, got {count}"
            assert names == ["new_file1.txt", "new_file2.txt"], f"Expected specific names, got {names}"

    @pytest.mark.asyncio
    async def test_copy_project_artifacts_no_project(
        self, mock_project_service, mock_component, mock_db
    ):
        """Test handling when project doesn't exist."""
        mock_project_service.get_project.return_value = None

        count, names = await copy_project_artifacts_to_session(
            project_id="nonexistent",
            user_id="user123",
            session_id="session456",
            project_service=mock_project_service,
            component=mock_component,
            db=mock_db,
        )

        assert count == 0
        assert names == []

    @pytest.mark.asyncio
    async def test_copy_project_artifacts_no_project_id(
        self, mock_project_service, mock_component, mock_db
    ):
        """Test handling when no project_id is provided."""
        count, names = await copy_project_artifacts_to_session(
            project_id="",
            user_id="user123",
            session_id="session456",
            project_service=mock_project_service,
            component=mock_component,
            db=mock_db,
        )

        assert count == 0
        assert names == []

    @pytest.mark.asyncio
    async def test_copy_project_artifacts_no_db(
        self, mock_project_service, mock_component
    ):
        """Test handling when database session is None."""
        count, names = await copy_project_artifacts_to_session(
            project_id="project123",
            user_id="user123",
            session_id="session456",
            project_service=mock_project_service,
            component=mock_component,
            db=None,
        )

        assert count == 0
        assert names == []
