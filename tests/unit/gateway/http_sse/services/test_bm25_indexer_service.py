"""Unit tests for BM25 indexer service."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import json

from solace_agent_mesh.gateway.http_sse.services.bm25_indexer_service import (
    chunk_text,
    collect_project_text_files_stream,
    collect_project_text_files,
    build_bm25_index,
    save_project_index,
    CHUNK_SIZE_CHARS,
    OVERLAP_CHARS,
)


class TestChunkText:
    """Tests for text chunking functionality."""

    def test_chunk_empty_text(self):
        """Test chunking empty text returns empty list."""
        chunks = chunk_text("")
        assert chunks == []

    def test_chunk_short_text(self):
        """Test chunking text shorter than chunk size."""
        text = "Short text"
        chunks = chunk_text(text, chunk_size=100, overlap=10)

        assert len(chunks) == 1
        assert chunks[0][0] == text
        assert chunks[0][1] == 0  # start position
        assert chunks[0][2] == len(text)  # end position

    def test_chunk_long_text_with_overlap(self):
        """Test chunking long text creates overlapping chunks."""
        # Create text of 5000 chars
        text = "x" * 5000

        chunks = chunk_text(text, chunk_size=2000, overlap=500)

        # Should create multiple chunks with overlap
        assert len(chunks) > 1

        # First chunk
        assert chunks[0][1] == 0  # starts at 0
        assert chunks[0][2] == 2000  # ends at chunk_size

        # Second chunk should start at (2000 - 500) = 1500
        assert chunks[1][1] == 1500
        assert chunks[1][2] == 3500

    def test_chunk_exact_size_no_remainder(self):
        """Test chunking text that's exactly divisible by chunk size."""
        text = "x" * 4000
        chunks = chunk_text(text, chunk_size=2000, overlap=0)

        assert len(chunks) == 2
        assert chunks[0][2] == 2000
        assert chunks[1][1] == 2000
        assert chunks[1][2] == 4000

    def test_chunk_positions_are_sequential(self):
        """Test that chunk positions are sequential and cover full text."""
        text = "a" * 3000
        chunks = chunk_text(text, chunk_size=1000, overlap=200)

        # Verify all text is covered
        covered_ranges = [(start, end) for _, start, end in chunks]

        # First chunk should start at 0
        assert covered_ranges[0][0] == 0

        # Last chunk should end at text length
        assert covered_ranges[-1][1] == len(text)


class TestCollectProjectTextFilesStream:
    """Tests for streaming text file collection."""

    @pytest.mark.asyncio
    async def test_stream_filters_non_text_files(self):
        """Test that non-text files are filtered out."""
        mock_artifact_service = AsyncMock()

        # Mock get_artifact_info_list
        mock_artifacts = [
            MagicMock(filename="doc.txt", mime_type="text/plain", version=1),
            MagicMock(filename="image.png", mime_type="image/png", version=1),
            MagicMock(filename="data.json", mime_type="application/json", version=1),
        ]

        mock_artifact_part = MagicMock()
        mock_artifact_part.inline_data.data = b"test content"

        with patch('solace_agent_mesh.agent.utils.artifact_helpers.get_artifact_info_list') as mock_list:
            mock_list.return_value = mock_artifacts

            with patch('solace_agent_mesh.common.utils.mime_helpers.is_text_based_file') as mock_is_text:
                # Only .txt and .json are text-based
                mock_is_text.side_effect = lambda mime, _: mime in ["text/plain", "application/json"]

                mock_artifact_service.load_artifact = AsyncMock(return_value=mock_artifact_part)

                with patch('solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata') as mock_load_meta:
                    mock_load_meta.return_value = {"status": "success", "metadata": {}}

                    files = []
                    async for file_info in collect_project_text_files_stream(
                        mock_artifact_service,
                        "test-app",
                        "user-123",
                        "project-456"
                    ):
                        files.append(file_info)

                    # Should only get .txt and .json files
                    assert len(files) == 2
                    assert files[0][0] == "doc.txt"
                    assert files[1][0] == "data.json"

    @pytest.mark.asyncio
    async def test_stream_yields_files_one_at_a_time(self):
        """Test that files are yielded one at a time (streaming)."""
        mock_artifact_service = AsyncMock()

        mock_artifacts = [
            MagicMock(filename="file1.txt", mime_type="text/plain", version=1),
            MagicMock(filename="file2.txt", mime_type="text/plain", version=1),
        ]

        mock_artifact_part = MagicMock()
        mock_artifact_part.inline_data.data = b"content"

        with patch('solace_agent_mesh.agent.utils.artifact_helpers.get_artifact_info_list') as mock_list:
            mock_list.return_value = mock_artifacts

            with patch('solace_agent_mesh.common.utils.mime_helpers.is_text_based_file') as mock_is_text:
                mock_is_text.return_value = True

                mock_artifact_service.load_artifact = AsyncMock(return_value=mock_artifact_part)

                with patch('solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata') as mock_load_meta:
                    mock_load_meta.return_value = {"status": "success", "metadata": {}}

                    files_yielded = []
                    async for file_info in collect_project_text_files_stream(
                        mock_artifact_service,
                        "test-app",
                        "user-123",
                        "project-456"
                    ):
                        # Verify each yield returns tuple
                        assert len(file_info) == 4  # (filename, version, text, citation_metadata)
                        files_yielded.append(file_info[0])

                    assert files_yielded == ["file1.txt", "file2.txt"]

    @pytest.mark.asyncio
    async def test_stream_extracts_citation_metadata_for_converted_files(self):
        """Test that citation metadata is extracted for converted files."""
        mock_artifact_service = AsyncMock()

        mock_artifacts = [
            MagicMock(filename="doc.pdf.converted.txt", mime_type="text/plain", version=1),
        ]

        mock_artifact_part = MagicMock()
        mock_artifact_part.inline_data.data = b"converted content"

        with patch('solace_agent_mesh.agent.utils.artifact_helpers.get_artifact_info_list') as mock_list:
            mock_list.return_value = mock_artifacts

            with patch('solace_agent_mesh.common.utils.mime_helpers.is_text_based_file') as mock_is_text:
                mock_is_text.return_value = True

                mock_artifact_service.load_artifact = AsyncMock(return_value=mock_artifact_part)

                with patch('solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata') as mock_load_meta:
                    # Return metadata with conversion info
                    mock_load_meta.return_value = {
                        "status": "success",
                        "metadata": {
                            "conversion": {
                                "source_file": "doc.pdf",
                                "source_version": 1,
                                "citation_type": "page",
                                "citation_map": [
                                    {"location": "physical_page_1", "char_start": 0, "char_end": 100}
                                ]
                            }
                        }
                    }

                    files = []
                    async for file_info in collect_project_text_files_stream(
                        mock_artifact_service,
                        "test-app",
                        "user-123",
                        "project-456"
                    ):
                        files.append(file_info)

                    assert len(files) == 1
                    filename, version, text, citation_metadata = files[0]

                    # Verify citation metadata was extracted
                    assert citation_metadata["source_file"] == "doc.pdf"
                    assert citation_metadata["citation_type"] == "page"
                    assert len(citation_metadata["citation_map"]) == 1


class TestBuildBM25Index:
    """Tests for BM25 index building."""

    @pytest.mark.asyncio
    async def test_build_index_from_empty_documents(self):
        """Test that building index from empty documents raises error."""
        empty_documents = []

        with pytest.raises(ValueError, match="No chunks created from documents"):
            await build_bm25_index(
                empty_documents,
                "project-123",
                chunk_size=2000,
                overlap=500
            )

    @pytest.mark.asyncio
    async def test_build_index_creates_manifest(self):
        """Test that index building creates proper manifest."""
        documents = [
            ("file1.txt", 1, "x" * 3000, {}),
            ("file2.txt", 1, "y" * 2500, {}),
        ]

        with patch('bm25s.tokenize') as mock_tokenize, \
             patch('bm25s.BM25') as mock_bm25_class:
            mock_tokenize.return_value = [["token1"], ["token2"]]
            mock_retriever = MagicMock()
            mock_bm25_class.return_value = mock_retriever

            zip_bytes, manifest = await build_bm25_index(
                documents,
                "project-123",
                chunk_size=1000,
                overlap=200
            )

            # Verify manifest structure
            assert manifest["schema_version"] == "1.0"
            assert manifest["project_id"] == "project-123"
            assert manifest["file_count"] == 2
            assert manifest["chunk_count"] > 0
            assert manifest["chunk_size"] == 1000
            assert manifest["overlap"] == 200
            assert len(manifest["chunks"]) > 0

            # Verify ZIP was created
            assert isinstance(zip_bytes, bytes)
            assert len(zip_bytes) > 0

    @pytest.mark.asyncio
    async def test_build_index_with_citation_metadata(self):
        """Test that citation metadata is preserved in manifest."""
        citation_metadata = {
            "source_file": "doc.pdf",
            "citation_type": "page",
            "citation_map": [
                {"location": "physical_page_1", "char_start": 0, "char_end": 1000}
            ]
        }

        documents = [
            ("doc.pdf.converted.txt", 1, "x" * 2000, citation_metadata),
        ]

        with patch('bm25s.tokenize') as mock_tokenize, \
             patch('bm25s.BM25') as mock_bm25_class:
            mock_tokenize.return_value = [["token1"]]
            mock_retriever = MagicMock()
            mock_bm25_class.return_value = mock_retriever

            zip_bytes, manifest = await build_bm25_index(
                documents,
                "project-123",
                chunk_size=1000,
                overlap=200
            )

            # Verify citation metadata in manifest
            chunk = manifest["chunks"][0]
            assert chunk["source_file"] == "doc.pdf"
            assert chunk["citation_type"] == "page"
            assert "citation_map" in chunk

    @pytest.mark.asyncio
    async def test_build_index_batch_processing(self):
        """Test that batch processing works correctly."""
        # Create 5 documents
        documents = [
            (f"file{i}.txt", 1, "x" * 1000, {})
            for i in range(5)
        ]

        with patch('bm25s.tokenize') as mock_tokenize, \
             patch('bm25s.BM25') as mock_bm25_class:
            mock_tokenize.return_value = [["token"]] * 5
            mock_retriever = MagicMock()
            mock_bm25_class.return_value = mock_retriever

            # Build with batch_size=2
            zip_bytes, manifest = await build_bm25_index(
                documents,
                "project-123",
                chunk_size=500,
                overlap=100,
                batch_size=2
            )

            # Should process all 5 files
            assert manifest["file_count"] == 5
            # Each file should produce chunks
            assert manifest["chunk_count"] > 0

    @pytest.mark.asyncio
    async def test_build_index_streaming_mode(self):
        """Test building index with async generator (streaming mode)."""
        async def document_generator():
            for i in range(3):
                yield (f"file{i}.txt", 1, "x" * 1000, {})

        with patch('bm25s.tokenize') as mock_tokenize, \
             patch('bm25s.BM25') as mock_bm25_class:
            mock_tokenize.return_value = [["token"]] * 3
            mock_retriever = MagicMock()
            mock_bm25_class.return_value = mock_retriever

            zip_bytes, manifest = await build_bm25_index(
                document_generator(),
                "project-123",
                chunk_size=500,
                overlap=100,
                batch_size=1
            )

            # Should process all 3 files from generator
            assert manifest["file_count"] == 3


class TestSaveProjectIndex:
    """Tests for saving project index."""

    @pytest.mark.asyncio
    async def test_save_index_success(self):
        """Test successful index save."""
        mock_artifact_service = AsyncMock()

        zip_bytes = b"fake zip content"
        manifest = {
            "file_count": 2,
            "chunk_count": 10,
            "chunk_size": 2000,
            "overlap": 500,
            "created_at": "2024-01-01T00:00:00Z",
            "chunks": [
                {"filename": "file1.txt", "version": 1, "chunk_id": 0},
                {"filename": "file2.txt", "version": 1, "chunk_id": 0}
            ]
        }

        with patch('solace_agent_mesh.agent.utils.artifact_helpers.save_artifact_with_metadata') as mock_save:
            mock_save.return_value = {
                "status": "success",
                "data_version": 1
            }

            result = await save_project_index(
                mock_artifact_service,
                "test-app",
                "user-123",
                "project-456",
                zip_bytes,
                manifest
            )

            assert result["status"] == "success"
            assert result["data_version"] == 1

            # Verify save was called with correct parameters
            mock_save.assert_called_once()
            call_args = mock_save.call_args
            assert call_args[1]["filename"] == "project_bm25_index.zip"
            assert call_args[1]["content_bytes"] == zip_bytes
            assert call_args[1]["mime_type"] == "application/zip"

    @pytest.mark.asyncio
    async def test_save_index_includes_metadata(self):
        """Test that saved index includes proper metadata."""
        mock_artifact_service = AsyncMock()

        zip_bytes = b"zip content"
        manifest = {
            "file_count": 1,
            "chunk_count": 5,
            "chunk_size": 2000,
            "overlap": 500,
            "created_at": "2024-01-01T00:00:00Z",
            "chunks": [
                {"filename": "test.txt", "version": 1, "chunk_id": 0}
            ]
        }

        with patch('solace_agent_mesh.agent.utils.artifact_helpers.save_artifact_with_metadata') as mock_save:
            mock_save.return_value = {"status": "success", "data_version": 1}

            await save_project_index(
                mock_artifact_service,
                "test-app",
                "user-123",
                "project-456",
                zip_bytes,
                manifest
            )

            # Verify metadata includes index info
            call_args = mock_save.call_args
            metadata = call_args[1]["metadata_dict"]

            assert metadata["source"] == "bm25_indexing"
            assert "index_info" in metadata
            assert metadata["index_info"]["file_count"] == 1
            assert metadata["index_info"]["chunk_count"] == 5
