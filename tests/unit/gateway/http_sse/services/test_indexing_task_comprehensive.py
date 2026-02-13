"""Comprehensive tests for 100% coverage of indexing_task_service.py."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from solace_agent_mesh.gateway.http_sse.services.indexing_task_service import (
    IndexingTaskService,
)


class TestIndexingTaskServiceComprehensive:
    """Comprehensive tests for IndexingTaskService."""

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

    @pytest.mark.asyncio
    async def test_convert_and_index_multiple_files_mixed_success_failure(self):
        """Test upload with mix of successful and failed conversions."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        files_to_convert = [
            ("good.pdf", 1, "application/pdf"),
            ("bad.pdf", 2, "application/pdf"),
            ("ok.docx", 1, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ]

        def mock_convert(project, filename, version, mime_type):
            if "bad" in filename:
                return {"status": "error", "error": "Conversion failed"}
            return {"status": "success", "data_version": version}

        with patch.object(self.service, '_convert_file_async', side_effect=mock_convert):
            with patch.object(self.service, '_rebuild_index_async') as mock_rebuild:
                mock_rebuild.return_value = {
                    "status": "success",
                    "indexed_files": ["good.pdf", "ok.docx"]
                }

                with patch.object(self.service, '_get_files_for_indexing') as mock_get_files:
                    mock_get_files.return_value = ["good.pdf", "ok.docx"]

                    await self.service.convert_and_index_upload_async(
                        "task-123",
                        mock_project,
                        files_to_convert,
                        is_text_based=[]
                    )

        # Verify both success and failure events were sent
        event_types = [
            call_args[1].get("event_type")
            for call_args in self.mock_sse_manager.send_event.call_args_list
        ]

        assert "conversion_file_completed" in event_types  # For good.pdf and ok.docx
        assert "conversion_failed" in event_types  # For bad.pdf

    @pytest.mark.asyncio
    async def test_convert_and_index_with_text_files_only(self):
        """Test upload with text files only (no conversion needed)."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        with patch.object(self.service, '_rebuild_index_async') as mock_rebuild:
            mock_rebuild.return_value = {
                "status": "success",
                "indexed_files": ["readme.txt"]
            }

            with patch.object(self.service, '_get_files_for_indexing') as mock_get_files:
                mock_get_files.return_value = ["readme.txt"]

                await self.service.convert_and_index_upload_async(
                    "task-123",
                    mock_project,
                    files_to_convert=[],  # No files to convert
                    is_text_based=[("readme.txt", 1)]  # Direct indexing
                )

        # Should skip conversion and go straight to indexing
        event_types = [
            call_args[1].get("event_type")
            for call_args in self.mock_sse_manager.send_event.call_args_list
        ]

        assert "conversion_started" not in event_types
        assert "index_started" in event_types
        assert "index_completed" in event_types

    @pytest.mark.asyncio
    async def test_convert_and_index_index_build_fails(self):
        """Test handling when index build fails after conversion."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        files_to_convert = [("doc.pdf", 1, "application/pdf")]

        with patch.object(self.service, '_convert_file_async') as mock_convert:
            mock_convert.return_value = {"status": "success", "data_version": 1}

            with patch.object(self.service, '_rebuild_index_async') as mock_rebuild:
                mock_rebuild.return_value = {
                    "status": "error",
                    "message": "Index build failed"
                }

                with patch.object(self.service, '_get_files_for_indexing') as mock_get_files:
                    mock_get_files.return_value = ["doc.pdf"]

                    await self.service.convert_and_index_upload_async(
                        "task-123",
                        mock_project,
                        files_to_convert,
                        is_text_based=[]
                    )

        # Should send indexing_failed event
        event_types = [
            call_args[1].get("event_type")
            for call_args in self.mock_sse_manager.send_event.call_args_list
        ]

        assert "indexing_failed" in event_types
        assert "task_completed" in event_types

    @pytest.mark.asyncio
    async def test_convert_file_async_exception_handling(self):
        """Test handling of exceptions in _convert_file_async."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        with patch('solace_agent_mesh.gateway.http_sse.services.file_converter_service.convert_and_save_artifact') as mock_convert:
            mock_convert.side_effect = RuntimeError("Unexpected error")

            result = await self.service._convert_file_async(
                mock_project,
                "doc.pdf",
                1,
                "application/pdf"
            )

            # Should return None on exception
            assert result is None

    @pytest.mark.asyncio
    async def test_rebuild_index_no_chunks_deletes_index(self):
        """Test that empty projects delete the index."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        async def empty_stream():
            return
            yield  # Never reached

        with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.collect_project_text_files_stream') as mock_collect:
            mock_collect.return_value = empty_stream()

            with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.build_bm25_index') as mock_build:
                mock_build.side_effect = ValueError("No chunks created from documents")

                result = await self.service._rebuild_index_async(mock_project)

                # Should attempt to delete index
                self.mock_project_service.artifact_service.delete_artifact.assert_called_once()

                assert result["status"] == "success"
                assert "index_deleted" in result

    @pytest.mark.asyncio
    async def test_rebuild_index_delete_fails_gracefully(self):
        """Test that index deletion failure is handled gracefully."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        async def empty_stream():
            return
            yield

        with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.collect_project_text_files_stream') as mock_collect:
            mock_collect.return_value = empty_stream()

            with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.build_bm25_index') as mock_build:
                mock_build.side_effect = ValueError("No chunks created from documents")

                # Make delete fail
                self.mock_project_service.artifact_service.delete_artifact.side_effect = Exception("Delete failed")

                result = await self.service._rebuild_index_async(mock_project)

                # Should handle gracefully
                assert result["status"] == "success"
                assert result["index_deleted"] is False

    @pytest.mark.asyncio
    async def test_rebuild_index_build_exception_handling(self):
        """Test handling of general exceptions during index build."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        async def mock_stream():
            yield ("file.txt", 1, "content", {})

        with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.collect_project_text_files_stream') as mock_collect:
            mock_collect.return_value = mock_stream()

            with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.build_bm25_index') as mock_build:
                mock_build.side_effect = RuntimeError("Build error")

                result = await self.service._rebuild_index_async(mock_project)

                assert result["status"] == "error"
                assert "Failed to build BM25 index" in result["message"]

    @pytest.mark.asyncio
    async def test_rebuild_index_save_exception_handling(self):
        """Test handling of exceptions during index save."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        async def mock_stream():
            yield ("file.txt", 1, "content", {})

        with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.collect_project_text_files_stream') as mock_collect:
            mock_collect.return_value = mock_stream()

            with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.build_bm25_index') as mock_build:
                mock_build.return_value = (
                    b"zip",
                    {"file_count": 1, "chunk_count": 5, "chunks": [{"filename": "file.txt", "chunk_id": 0}]}
                )

                with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.save_project_index') as mock_save:
                    mock_save.side_effect = Exception("Save error")

                    result = await self.service._rebuild_index_async(mock_project)

                    assert result["status"] == "error"
                    assert "Failed to save index artifact" in result["message"]

    @pytest.mark.asyncio
    async def test_rebuild_index_stream_creation_exception(self):
        """Test handling of exceptions when creating text files stream."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.collect_project_text_files_stream') as mock_collect:
            mock_collect.side_effect = Exception("Stream creation failed")

            result = await self.service._rebuild_index_async(mock_project)

            assert result["status"] == "error"
            assert "Failed to access project files" in result["message"]

    @pytest.mark.asyncio
    async def test_rebuild_index_outer_exception_handler(self):
        """Test outer catch-all exception handler in rebuild_index."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.collect_project_text_files_stream') as mock_collect:
            # Make it raise an unexpected error after stream creation
            async def bad_stream():
                raise RuntimeError("Unexpected stream error")
                yield

            mock_collect.return_value = bad_stream()

            result = await self.service._rebuild_index_async(mock_project)

            assert result["status"] == "error"
            # Message may be wrapped, just check it contains the error
            assert "error" in result["message"].lower() or "Unexpected stream error" in result["message"]

    @pytest.mark.asyncio
    async def test_get_files_for_indexing_removes_converted_suffix(self):
        """Test that .converted.txt suffix is properly removed."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        async def mock_stream():
            yield ("report.pdf.converted.txt", 1, "text", {})
            yield ("readme.md", 1, "text", {})
            yield ("slides.pptx.converted.txt", 1, "text", {})

        with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.collect_project_text_files_stream') as mock_collect:
            mock_collect.return_value = mock_stream()

            files = await self.service._get_files_for_indexing(mock_project)

            # Should have original filenames
            assert "report.pdf" in files
            assert "readme.md" in files
            assert "slides.pptx" in files
            # Should not have .converted.txt versions
            assert "report.pdf.converted.txt" not in files

    @pytest.mark.asyncio
    async def test_get_files_for_indexing_deduplicates(self):
        """Test that duplicate files are deduplicated."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        async def mock_stream():
            # Same original file might have multiple chunks
            yield ("doc.pdf.converted.txt", 1, "text1", {})
            yield ("doc.pdf.converted.txt", 1, "text2", {})  # Same file, different chunk

        with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.collect_project_text_files_stream') as mock_collect:
            mock_collect.return_value = mock_stream()

            files = await self.service._get_files_for_indexing(mock_project)

            # Should only list doc.pdf once
            assert files.count("doc.pdf") == 1

    @pytest.mark.asyncio
    async def test_get_files_for_indexing_exception_handling(self):
        """Test exception handling in _get_files_for_indexing."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.collect_project_text_files_stream') as mock_collect:
            mock_collect.side_effect = Exception("Stream error")

            files = await self.service._get_files_for_indexing(mock_project)

            # Should return empty list on error
            assert files == []

    @pytest.mark.asyncio
    async def test_send_event_exception_handling(self):
        """Test that _send_event handles exceptions gracefully."""
        self.mock_sse_manager.send_event.side_effect = Exception("Send failed")

        # Should not raise, just log warning
        await self.service._send_event(
            "task-123",
            {"type": "test_event"}
        )

        # Verify attempt was made
        self.mock_sse_manager.send_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_rebuild_after_delete_sends_all_events(self):
        """Test that rebuild_after_delete sends proper event sequence."""
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

        event_types = [
            call_args[1].get("event_type")
            for call_args in self.mock_sse_manager.send_event.call_args_list
        ]

        # Verify event sequence
        assert "index_started" in event_types
        assert "index_completed" in event_types
        assert "task_completed" in event_types

        # Verify order: started before completed
        started_idx = event_types.index("index_started")
        completed_idx = event_types.index("index_completed")
        task_completed_idx = event_types.index("task_completed")

        assert started_idx < completed_idx < task_completed_idx

    @pytest.mark.asyncio
    async def test_rebuild_manifest_extraction(self):
        """Test that indexed files are properly extracted from manifest."""
        mock_project = MagicMock(id="proj-123", user_id="user-456")

        async def mock_stream():
            yield ("file1.txt", 1, "content1", {})
            yield ("file2.pdf.converted.txt", 1, "content2", {})

        with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.collect_project_text_files_stream') as mock_collect:
            mock_collect.return_value = mock_stream()

            with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.build_bm25_index') as mock_build:
                mock_build.return_value = (
                    b"zip",
                    {
                        "file_count": 2,
                        "chunk_count": 10,
                        "chunks": [
                            {"filename": "file1.txt", "chunk_id": 0},
                            {"filename": "file1.txt", "chunk_id": 1},  # Multiple chunks
                            {"filename": "file2.pdf.converted.txt", "chunk_id": 0},
                        ]
                    }
                )

                with patch('solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service.save_project_index') as mock_save:
                    mock_save.return_value = {"status": "success", "data_version": 1}

                    result = await self.service._rebuild_index_async(mock_project)

                    # indexed_files should have original filenames, deduplicated
                    assert "file1.txt" in result["indexed_files"]
                    assert "file2.pdf" in result["indexed_files"]  # .converted.txt removed
                    # Should only list each file once
                    assert result["indexed_files"].count("file1.txt") == 1
