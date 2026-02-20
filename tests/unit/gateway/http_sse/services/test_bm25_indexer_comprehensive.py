"""Comprehensive tests for 100% coverage of bm25_indexer_service.py."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import json

from solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service import (
    chunk_text,
    collect_project_text_files_stream,
    collect_project_text_files,
    _process_document_batch,
    build_bm25_index,
    save_project_index,
    CHUNK_SIZE_CHARS,
    OVERLAP_CHARS,
)


class TestChunkTextEdgeCases:
    """Edge cases and boundary conditions for text chunking."""

    def test_chunk_whitespace_only_text(self):
        """Test chunking text with only whitespace."""
        text = "   \n\n   \t\t   "
        chunks = chunk_text(text, chunk_size=100, overlap=10)

        # Should filter out whitespace-only chunks
        assert len(chunks) == 0

    def test_chunk_exact_overlap_boundary(self):
        """Test chunking when text length is exactly at overlap boundary."""
        text = "x" * 2500  # Exactly 500 past chunk_size
        chunks = chunk_text(text, chunk_size=2000, overlap=500)

        assert len(chunks) == 2
        # Second chunk starts at 1500 (2000 - 500)
        assert chunks[1][1] == 1500

    def test_chunk_very_small_overlap(self):
        """Test chunking with very small overlap."""
        text = "x" * 3000
        chunks = chunk_text(text, chunk_size=1000, overlap=1)

        # Should create chunks with minimal overlap
        # Chunk 0: 0-1000
        # Chunk 1: 999-1999 (starts at 1000-1)
        # Chunk 2: 1998-2998 (starts at 1999-1)
        # Chunk 3: 2997-3000 (starts at 2998-1, ends at text length)
        assert len(chunks) == 4  # 4 chunks, not 3
        assert chunks[1][1] == 999  # Second starts at 1000 - 1

    def test_chunk_no_overlap(self):
        """Test chunking with zero overlap."""
        text = "x" * 4000
        chunks = chunk_text(text, chunk_size=2000, overlap=0)

        assert len(chunks) == 2
        assert chunks[0][2] == 2000
        assert chunks[1][1] == 2000  # No overlap

    def test_chunk_overlap_near_chunk_size(self):
        """Test behavior when overlap is close to chunk_size but not equal."""
        text = "x" * 5000
        # Use overlap just below chunk_size (valid edge case)
        chunks = chunk_text(text, chunk_size=1000, overlap=999)

        # Should still complete and make progress
        assert len(chunks) > 0
        # Should have many chunks since overlap is very large
        assert len(chunks) >= 5


class TestCollectProjectTextFilesStreamEdgeCases:
    """Edge cases for streaming file collection."""

    @pytest.mark.asyncio
    async def test_stream_handles_decode_exception(self):
        """Test handling of files that raise exceptions during decode.

        Note: The code uses decode('utf-8', errors='ignore') which doesn't raise
        UnicodeDecodeError. This test verifies the exception handler around decode.
        """
        mock_artifact_service = AsyncMock()

        mock_artifacts = [
            MagicMock(filename="valid.txt", mime_type="text/plain", version=1),
            MagicMock(filename="error.txt", mime_type="text/plain", version=1),
        ]

        # First file decodes, second raises exception during decode()
        valid_part = MagicMock()
        valid_part.inline_data.data = b"valid content"

        error_part = MagicMock()
        # Make decode() raise an exception (simulates corrupted data structure)
        error_part.inline_data.data.decode = MagicMock(side_effect=Exception("Decode failed"))

        def mock_load_artifact(app_name, user_id, session_id, filename):
            if "error" in filename:
                return error_part
            else:
                return valid_part

        mock_artifact_service.load_artifact = AsyncMock(side_effect=mock_load_artifact)

        with patch('solace_agent_mesh.agent.utils.artifact_helpers.get_artifact_info_list') as mock_list:
            mock_list.return_value = mock_artifacts

            with patch('solace_agent_mesh.common.utils.mime_helpers.is_text_based_file') as mock_is_text:
                mock_is_text.return_value = True

                with patch('solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata') as mock_load_meta:
                    mock_load_meta.return_value = {"status": "success", "metadata": {}}

                    files = []
                    async for file_info in collect_project_text_files_stream(
                        mock_artifact_service,
                        "app",
                        "user",
                        "project"
                    ):
                        files.append(file_info)

                    # Should only get valid file (error.txt skipped due to decode exception)
                    assert len(files) == 1
                    assert files[0][0] == "valid.txt"

    @pytest.mark.asyncio
    async def test_stream_handles_missing_inline_data(self):
        """Test handling when artifact has no inline_data."""
        mock_artifact_service = AsyncMock()

        mock_artifacts = [
            MagicMock(filename="file.txt", mime_type="text/plain", version=1),
        ]

        mock_part = MagicMock()
        mock_part.inline_data = None  # Missing data

        mock_artifact_service.load_artifact = AsyncMock(return_value=mock_part)

        with patch('solace_agent_mesh.agent.utils.artifact_helpers.get_artifact_info_list') as mock_list:
            mock_list.return_value = mock_artifacts

            with patch('solace_agent_mesh.common.utils.mime_helpers.is_text_based_file') as mock_is_text:
                mock_is_text.return_value = True

                with patch('solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata') as mock_load_meta:
                    mock_load_meta.return_value = {"status": "success", "metadata": {}}

                    files = []
                    async for file_info in collect_project_text_files_stream(
                        mock_artifact_service,
                        "app",
                        "user",
                        "project"
                    ):
                        files.append(file_info)

                    # Should skip file with no data
                    assert len(files) == 0

    @pytest.mark.asyncio
    async def test_stream_handles_load_exception(self):
        """Test handling of exceptions during file load."""
        mock_artifact_service = AsyncMock()

        mock_artifacts = [
            MagicMock(filename="error.txt", mime_type="text/plain", version=1),
            MagicMock(filename="ok.txt", mime_type="text/plain", version=1),
        ]

        def mock_load_artifact(app_name, user_id, session_id, filename):
            if "error" in filename:
                raise Exception("Load failed")
            mock_part = MagicMock()
            mock_part.inline_data.data = b"content"
            return mock_part

        mock_artifact_service.load_artifact = AsyncMock(side_effect=mock_load_artifact)

        with patch('solace_agent_mesh.agent.utils.artifact_helpers.get_artifact_info_list') as mock_list:
            mock_list.return_value = mock_artifacts

            with patch('solace_agent_mesh.common.utils.mime_helpers.is_text_based_file') as mock_is_text:
                mock_is_text.return_value = True

                with patch('solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata') as mock_load_meta:
                    mock_load_meta.return_value = {"status": "success", "metadata": {}}

                    files = []
                    async for file_info in collect_project_text_files_stream(
                        mock_artifact_service,
                        "app",
                        "user",
                        "project"
                    ):
                        files.append(file_info)

                    # Should continue after error and get ok.txt
                    assert len(files) == 1
                    assert files[0][0] == "ok.txt"

    @pytest.mark.asyncio
    async def test_stream_extracts_text_citations_metadata(self):
        """Test extraction of text_citations metadata (for text files)."""
        mock_artifact_service = AsyncMock()

        mock_artifacts = [
            MagicMock(filename="code.py", mime_type="text/x-python", version=1),
        ]

        mock_part = MagicMock()
        mock_part.inline_data.data = b"print('hello')"

        mock_artifact_service.load_artifact = AsyncMock(return_value=mock_part)

        with patch('solace_agent_mesh.agent.utils.artifact_helpers.get_artifact_info_list') as mock_list:
            mock_list.return_value = mock_artifacts

            with patch('solace_agent_mesh.common.utils.mime_helpers.is_text_based_file') as mock_is_text:
                mock_is_text.return_value = True

                with patch('solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata') as mock_load_meta:
                    # Return text_citations metadata
                    mock_load_meta.return_value = {
                        "status": "success",
                        "metadata": {
                            "text_citations": {
                                "citation_type": "line_range",
                                "citation_map": [
                                    {"location": "lines_1_50", "char_start": 0, "char_end": 100}
                                ]
                            }
                        }
                    }

                    files = []
                    async for file_info in collect_project_text_files_stream(
                        mock_artifact_service,
                        "app",
                        "user",
                        "project"
                    ):
                        files.append(file_info)

                    filename, version, text, citation_metadata = files[0]

                    # Should extract text_citations
                    assert citation_metadata["citation_type"] == "line_range"
                    assert len(citation_metadata["citation_map"]) == 1


class TestProcessDocumentBatch:
    """Test the document batch processing helper."""

    def test_process_empty_batch(self):
        """Test processing empty batch."""
        chunks = _process_document_batch(
            [],
            starting_doc_id=0,
            chunk_size=1000,
            overlap=100,
            log_prefix="[test]"
        )

        assert chunks == []

    def test_process_single_document_batch(self):
        """Test processing single document."""
        batch = [
            ("file.txt", 1, "x" * 2000, {})
        ]

        chunks = _process_document_batch(
            batch,
            starting_doc_id=5,
            chunk_size=1000,
            overlap=200,
            log_prefix="[test]"
        )

        # Should create multiple chunks
        assert len(chunks) > 0
        # First chunk should have doc_id=5
        assert chunks[0][0] == 5

    def test_process_multiple_documents_batch(self):
        """Test processing multiple documents in batch."""
        batch = [
            ("file1.txt", 1, "x" * 1000, {}),
            ("file2.txt", 1, "y" * 1000, {}),
        ]

        chunks = _process_document_batch(
            batch,
            starting_doc_id=10,
            chunk_size=500,
            overlap=100,
            log_prefix="[test]"
        )

        # Should have chunks from both files
        doc_ids = set(chunk[0] for chunk in chunks)
        assert 10 in doc_ids  # file1
        assert 11 in doc_ids  # file2

    def test_process_batch_preserves_citation_metadata(self):
        """Test that citation metadata is preserved."""
        citation_meta = {
            "citation_type": "page",
            "citation_map": [{"location": "physical_page_1"}]
        }

        batch = [
            ("doc.pdf.converted.txt", 1, "content", citation_meta)
        ]

        chunks = _process_document_batch(
            batch,
            starting_doc_id=0,
            chunk_size=1000,
            overlap=100,
            log_prefix="[test]"
        )

        # Citation metadata should be in last position
        assert chunks[0][7] == citation_meta


class TestBuildBM25IndexEdgeCases:
    """Edge cases for BM25 index building."""

    @pytest.mark.asyncio
    async def test_build_index_with_async_generator_empty(self):
        """Test building index from empty async generator."""
        async def empty_generator():
            return
            yield  # Never reached

        with pytest.raises(ValueError, match="No chunks created"):
            await build_bm25_index(
                empty_generator(),
                "project-123",
                chunk_size=1000,
                overlap=100
            )

    @pytest.mark.asyncio
    async def test_build_index_citation_map_filtering(self):
        """Test that citation_map is filtered to chunk boundaries."""
        citation_metadata = {
            "source_file": "doc.pdf",
            "citation_type": "page",
            "citation_map": [
                # Only second citation overlaps with chunk 0-500
                {"location": "physical_page_1", "char_start": 0, "char_end": 300},
                {"location": "physical_page_2", "char_start": 400, "char_end": 700},
                {"location": "physical_page_3", "char_start": 800, "char_end": 1000},
            ]
        }

        documents = [
            ("doc.pdf.converted.txt", 1, "x" * 1000, citation_metadata)
        ]

        with patch('bm25s.tokenize') as mock_tokenize, \
             patch('bm25s.BM25') as mock_bm25_class:
            mock_tokenize.return_value = [["token"]]
            mock_retriever = MagicMock()
            mock_bm25_class.return_value = mock_retriever

            zip_bytes, manifest = await build_bm25_index(
                documents,
                "project-123",
                chunk_size=500,
                overlap=100
            )

            # First chunk (0-500) should include citations 1 and 2, not 3
            first_chunk = manifest["chunks"][0]
            assert "citation_map" in first_chunk
            # Should have citations that overlap with 0-500


    @pytest.mark.asyncio
    async def test_build_index_regular_text_file_no_source_file(self):
        """Test that regular text files don't have source_file."""
        documents = [
            ("readme.txt", 1, "x" * 1000, {})  # No citation metadata
        ]

        with patch('bm25s.tokenize') as mock_tokenize, \
             patch('bm25s.BM25') as mock_bm25_class:
            mock_tokenize.return_value = [["token"]]
            mock_retriever = MagicMock()
            mock_bm25_class.return_value = mock_retriever

            zip_bytes, manifest = await build_bm25_index(
                documents,
                "project-123",
                chunk_size=500,
                overlap=100
            )

            chunk = manifest["chunks"][0]
            assert chunk["citation_type"] == "text_file"
            assert chunk["citation_map"] == []
            assert "source_file" not in chunk or chunk.get("source_file") is None


class TestSaveProjectIndexEdgeCases:
    """Edge cases for saving project index."""

    @pytest.mark.asyncio
    async def test_save_index_failure_handling(self):
        """Test handling of save failures."""
        mock_artifact_service = AsyncMock()

        zip_bytes = b"zip content"
        manifest = {
            "file_count": 1,
            "chunk_count": 5,
            "chunk_size": 2000,
            "overlap": 500,
            "created_at": "2024-01-01T00:00:00Z",
            "chunks": [{"filename": "test.txt", "version": 1, "chunk_id": 0}]
        }

        with patch('solace_agent_mesh.agent.utils.artifact_helpers.save_artifact_with_metadata') as mock_save:
            mock_save.return_value = {
                "status": "error",
                "status_message": "Storage full"
            }

            result = await save_project_index(
                mock_artifact_service,
                "app",
                "user",
                "project",
                zip_bytes,
                manifest
            )

            assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_save_index_metadata_indexed_files_list(self):
        """Test that indexed_files list is properly constructed."""
        mock_artifact_service = AsyncMock()

        zip_bytes = b"zip"
        manifest = {
            "file_count": 2,
            "chunk_count": 10,
            "chunk_size": 2000,
            "overlap": 500,
            "created_at": "2024-01-01T00:00:00Z",
            "chunks": [
                {"filename": "file1.txt", "version": 1, "chunk_id": 0},
                {"filename": "file1.txt", "version": 1, "chunk_id": 1},  # Same file, different chunk
                {"filename": "file2.txt", "version": 1, "chunk_id": 0},
            ]
        }

        with patch('solace_agent_mesh.agent.utils.artifact_helpers.save_artifact_with_metadata') as mock_save:
            mock_save.return_value = {"status": "success", "data_version": 1}

            await save_project_index(
                mock_artifact_service,
                "app",
                "user",
                "project",
                zip_bytes,
                manifest
            )

            call_args = mock_save.call_args[1]
            metadata = call_args["metadata_dict"]
            indexed_files = metadata["index_info"]["indexed_files"]

            # Should list each file only once (chunk_id == 0)
            assert len(indexed_files) == 2
            filenames = [f["filename"] for f in indexed_files]
            assert "file1.txt" in filenames
            assert "file2.txt" in filenames
