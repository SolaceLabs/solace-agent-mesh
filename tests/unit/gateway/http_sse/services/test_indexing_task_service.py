"""Unit tests for indexing task service."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
import asyncio

from solace_agent_mesh.gateway.http_sse.services.indexing_task_service import (
    IndexingTaskService,
)


class TestIndexingTaskService:
    """Tests for IndexingTaskService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_sse_manager = MagicMock()
        self.mock_sse_manager.send_event = AsyncMock()

        self.mock_project_service = MagicMock()
        self.mock_project_service.artifact_service = AsyncMock()
        self.mock_project_service.app_name = "test-app"

        self.service = IndexingTaskService(
            self.mock_sse_manager,
            self.mock_project_service
        )

    def test_create_task_id(self):
        """Test that task ID generation is unique and formatted correctly."""
        task_id1 = IndexingTaskService.create_task_id("upload", "project-123")
        task_id2 = IndexingTaskService.create_task_id("upload", "project-123")

        # Should both start with same prefix
        assert task_id1.startswith("indexing_upload_project-123_")
        assert task_id2.startswith("indexing_upload_project-123_")

        # But should be unique
        assert task_id1 != task_id2

    def test_create_task_id_different_operations(self):
        """Test task IDs for different operations."""
        upload_id = IndexingTaskService.create_task_id("upload", "proj1")
        delete_id = IndexingTaskService.create_task_id("delete", "proj1")
        import_id = IndexingTaskService.create_task_id("import", "proj1")

        assert "upload" in upload_id
        assert "delete" in delete_id
        assert "import" in import_id

    @pytest.mark.asyncio
    async def test_convert_and_index_upload_no_files(self):
        """Test upload task with no files to convert."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        await self.service.convert_and_index_upload_async(
            "task-123",
            mock_project,
            files_to_convert=[],
            is_text_based=[]
        )

        # Should send task_completed event with event_type="index_message"
        completion_calls = [
            c for c in self.mock_sse_manager.send_event.call_args_list
            if c[1].get("event_type") == "index_message"
            and c[1].get("event_data", {}).get("type") == "task_completed"
        ]
        assert len(completion_calls) == 1

    @pytest.mark.asyncio
    async def test_convert_and_index_sends_progress_events(self):
        """Test that upload task sends SSE progress events."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        files_to_convert = [
            ("doc.pdf", 1, "application/pdf"),
        ]

        with patch.object(self.service, '_convert_file_async') as mock_convert:
            mock_convert.return_value = {
                "status": "success",
                "data_version": 1
            }

            with patch.object(self.service, '_rebuild_index_async') as mock_rebuild:
                mock_rebuild.return_value = {
                    "status": "success",
                    "indexed_files": ["doc.pdf"]
                }

                with patch.object(self.service, '_get_files_for_indexing') as mock_get_files:
                    mock_get_files.return_value = ["doc.pdf"]

                    await self.service.convert_and_index_upload_async(
                        "task-123",
                        mock_project,
                        files_to_convert,
                        is_text_based=[]
                    )

        # Verify SSE events were sent with event_type="index_message"
        # and check the type field inside event_data
        for call_args in self.mock_sse_manager.send_event.call_args_list:
            assert call_args[1].get("event_type") == "index_message"

        event_types = [
            call_args[1].get("event_data", {}).get("type")
            for call_args in self.mock_sse_manager.send_event.call_args_list
        ]

        assert "conversion_started" in event_types
        assert "conversion_file_progress" in event_types
        assert "conversion_file_completed" in event_types
        assert "conversion_completed" in event_types
        assert "index_started" in event_types
        assert "index_completed" in event_types
        assert "task_completed" in event_types

    @pytest.mark.asyncio
    async def test_convert_and_index_handles_conversion_failure(self):
        """Test that conversion failures are handled gracefully."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        files_to_convert = [
            ("bad.pdf", 1, "application/pdf"),
        ]

        with patch.object(self.service, '_convert_file_async') as mock_convert:
            # Conversion fails
            mock_convert.return_value = {
                "status": "error",
                "error": "Corrupted file"
            }

            with patch.object(self.service, '_rebuild_index_async') as mock_rebuild:
                # Index still builds (from other files)
                mock_rebuild.return_value = {
                    "status": "success",
                    "indexed_files": []
                }

                with patch.object(self.service, '_get_files_for_indexing') as mock_get_files:
                    mock_get_files.return_value = []

                    await self.service.convert_and_index_upload_async(
                        "task-123",
                        mock_project,
                        files_to_convert,
                        is_text_based=[]
                    )

        # Should send conversion_failed event with event_type="index_message"
        for call_args in self.mock_sse_manager.send_event.call_args_list:
            assert call_args[1].get("event_type") == "index_message"

        event_types = [
            call_args[1].get("event_data", {}).get("type")
            for call_args in self.mock_sse_manager.send_event.call_args_list
        ]

        assert "conversion_failed" in event_types

    @pytest.mark.asyncio
    async def test_convert_and_index_builds_index_after_conversion(self):
        """Test that index is rebuilt after file conversion."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        files_to_convert = [("doc.pdf", 1, "application/pdf")]

        with patch.object(self.service, '_convert_file_async') as mock_convert:
            mock_convert.return_value = {"status": "success", "data_version": 1}

            with patch.object(self.service, '_rebuild_index_async') as mock_rebuild:
                mock_rebuild.return_value = {
                    "status": "success",
                    "indexed_files": ["doc.pdf"]
                }

                with patch.object(self.service, '_get_files_for_indexing') as mock_get_files:
                    mock_get_files.return_value = ["doc.pdf"]

                    await self.service.convert_and_index_upload_async(
                        "task-123",
                        mock_project,
                        files_to_convert,
                        is_text_based=[]
                    )

        # Verify index rebuild was called
        mock_rebuild.assert_called_once_with(mock_project)

    @pytest.mark.asyncio
    async def test_rebuild_index_after_delete(self):
        """Test index rebuild after file deletion."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        with patch.object(self.service, '_rebuild_index_async') as mock_rebuild:
            mock_rebuild.return_value = {
                "status": "success",
                "indexed_files": ["remaining.txt"]
            }

            with patch.object(self.service, '_get_files_for_indexing') as mock_get_files:
                mock_get_files.return_value = ["remaining.txt"]

                await self.service.rebuild_index_after_delete_async(
                    "task-456",
                    mock_project
                )

        # Verify rebuild was called
        mock_rebuild.assert_called_once_with(mock_project)

        # Verify SSE events with event_type="index_message"
        for call_args in self.mock_sse_manager.send_event.call_args_list:
            assert call_args[1].get("event_type") == "index_message"

        event_types = [
            call_args[1].get("event_data", {}).get("type")
            for call_args in self.mock_sse_manager.send_event.call_args_list
        ]

        assert "index_started" in event_types
        assert "index_completed" in event_types
        assert "task_completed" in event_types

    @pytest.mark.asyncio
    async def test_rebuild_index_handles_index_failure(self):
        """Test handling of index build failures."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        with patch.object(self.service, '_rebuild_index_async') as mock_rebuild:
            mock_rebuild.return_value = {
                "status": "error",
                "message": "Index build failed"
            }

            with patch.object(self.service, '_get_files_for_indexing') as mock_get_files:
                mock_get_files.return_value = ["file.txt"]

                await self.service.rebuild_index_after_delete_async(
                    "task-456",
                    mock_project
                )

        # Should send indexing_failed event with event_type="index_message"
        for call_args in self.mock_sse_manager.send_event.call_args_list:
            assert call_args[1].get("event_type") == "index_message"

        event_types = [
            call_args[1].get("event_data", {}).get("type")
            for call_args in self.mock_sse_manager.send_event.call_args_list
        ]

        assert "indexing_failed" in event_types

    @pytest.mark.asyncio
    async def test_get_files_for_indexing(self):
        """Test getting list of files to be indexed."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        async def mock_stream():
            yield ("doc.pdf.converted.txt", 1, "text", {})
            yield ("readme.md", 1, "text", {})

        with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.collect_project_text_files_stream') as mock_collect:
            mock_collect.return_value = mock_stream()

            files = await self.service._get_files_for_indexing(mock_project)

            # Should return original filenames (without .converted.txt)
            assert "doc.pdf" in files
            assert "readme.md" in files
            assert len(files) == 2

    @pytest.mark.asyncio
    async def test_convert_file_async_calls_converter(self):
        """Test that file conversion is called correctly."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        with patch('solace_agent_mesh.gateway.http_sse.services.file_converter_service.convert_and_save_artifact') as mock_convert:
            mock_convert.return_value = {
                "status": "success",
                "data_version": 1
            }

            result = await self.service._convert_file_async(
                mock_project,
                "doc.pdf",
                1,
                "application/pdf"
            )

            # Verify converter was called
            mock_convert.assert_called_once()
            call_args = mock_convert.call_args[1]
            assert call_args["source_filename"] == "doc.pdf"
            assert call_args["source_version"] == 1
            assert call_args["mime_type"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_rebuild_index_async_calls_build(self):
        """Test that index rebuild calls build_bm25_index."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        async def mock_stream():
            yield ("file.txt", 1, "content", {})

        with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.collect_project_text_files_stream') as mock_collect:
            mock_collect.return_value = mock_stream()

            with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.build_bm25_index') as mock_build:
                mock_build.return_value = (
                    b"zip bytes",
                    {
                        "file_count": 1,
                        "chunk_count": 5,
                        "chunks": [{"filename": "file.txt", "chunk_id": 0}]
                    }
                )

                with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.save_project_index') as mock_save:
                    mock_save.return_value = {
                        "status": "success",
                        "data_version": 1
                    }

                    result = await self.service._rebuild_index_async(mock_project)

                    assert result["status"] == "success"
                    assert "indexed_files" in result

    @pytest.mark.asyncio
    async def test_rebuild_index_deletes_empty_index(self):
        """Test that empty indices are deleted."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        async def mock_empty_stream():
            # Return empty stream
            return
            yield

        with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.collect_project_text_files_stream') as mock_collect:
            mock_collect.return_value = mock_empty_stream()

            with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.build_bm25_index') as mock_build:
                mock_build.side_effect = ValueError("No chunks created from documents")

                result = await self.service._rebuild_index_async(mock_project)

                # Should delete index artifact
                self.mock_project_service.artifact_service.delete_artifact.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_event_calls_sse_manager(self):
        """Test that _send_event calls SSE manager correctly."""
        await self.service._send_event(
            "task-123",
            {"type": "test_event", "data": "test"}
        )

        self.mock_sse_manager.send_event.assert_called_once_with(
            task_id="task-123",
            event_data={"type": "test_event", "data": "test"},
            event_type="index_message"
        )

    @pytest.mark.asyncio
    async def test_convert_and_index_import_uses_upload_logic(self):
        """Test that import reuses upload logic."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        with patch.object(self.service, 'convert_and_index_upload_async') as mock_upload:
            await self.service.convert_and_index_import_async(
                "task-789",
                mock_project,
                files_to_convert=[("doc.pdf", 1, "application/pdf")],
                is_text_based=[]
            )

            # Should call upload logic
            mock_upload.assert_called_once_with(
                "task-789",
                mock_project,
                [("doc.pdf", 1, "application/pdf")],
                []
            )

    @pytest.mark.asyncio
    async def test_task_handles_exceptions_gracefully(self):
        """Test that unexpected exceptions are caught and reported."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        with patch.object(self.service, '_get_files_for_indexing') as mock_get_files:
            # Raise unexpected exception outside the normal flow
            mock_get_files.side_effect = RuntimeError("Unexpected error")

            with patch.object(self.service, '_convert_file_async') as mock_convert:
                mock_convert.return_value = {"status": "success", "data_version": 1}

                # Should not raise, should send error event
                await self.service.convert_and_index_upload_async(
                    "task-123",
                    mock_project,
                    files_to_convert=[("doc.pdf", 1, "application/pdf")],
                    is_text_based=[]
                )

        # Verify task_error event was sent with event_type="index_message"
        for call_args in self.mock_sse_manager.send_event.call_args_list:
            assert call_args[1].get("event_type") == "index_message"

        event_types = [
            call_args[1].get("event_data", {}).get("type")
            for call_args in self.mock_sse_manager.send_event.call_args_list
        ]

        assert "task_error" in event_types
