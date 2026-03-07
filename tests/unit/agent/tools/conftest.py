"""Shared pytest fixtures for index_search_tools tests."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from io import BytesIO
import zipfile
import json


@pytest.fixture
def mock_bm25_index():
    """Create a mock BM25 index ZIP file for index_search tests."""
    manifest = {
        "schema_version": "1.0",
        "project_id": "test-project",
        "file_count": 2,
        "chunk_count": 5,
        "chunk_size": 2000,
        "overlap": 500,
        "created_at": "2024-01-01T00:00:00Z",
        "chunks": [
            {
                "corpus_index": 0,
                "doc_id": 0,
                "filename": "doc1.txt",
                "version": 1,
                "chunk_id": 0,
                "chunk_start": 0,
                "chunk_end": 100,
                "chunk_text": "This is the first chunk of text about revenue.",
                "citation_type": "text_file",
                "citation_map": []
            },
            {
                "corpus_index": 1,
                "doc_id": 0,
                "filename": "doc1.txt",
                "version": 1,
                "chunk_id": 1,
                "chunk_start": 100,
                "chunk_end": 200,
                "chunk_text": "This is the second chunk with different content.",
                "citation_type": "text_file",
                "citation_map": []
            },
            {
                "corpus_index": 2,
                "doc_id": 1,
                "filename": "report.pdf.converted.txt",
                "source_file": "report.pdf",
                "version": 1,
                "chunk_id": 0,
                "chunk_start": 0,
                "chunk_end": 150,
                "chunk_text": "Financial report showing revenue of $4.2B in 2024.",
                "citation_type": "page",
                "citation_map": [
                    {"location": "physical_page_1", "char_start": 0, "char_end": 150}
                ]
            }
        ]
    }

    # Create ZIP with index files and manifest
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zf:
        zf.writestr("index/data.pkl", b"fake index data")
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    zip_buffer.seek(0)
    return zip_buffer.getvalue(), manifest


@pytest.fixture
def mock_tool_context():
    """Create a mock tool context for index_search tests."""
    context = MagicMock()
    context.state = {}

    invocation_context = MagicMock()
    invocation_context.artifact_service = AsyncMock()
    invocation_context.app_name = "test-app"
    invocation_context.user_id = "test-user"
    invocation_context.session_id = "test-session"

    context._invocation_context = invocation_context

    return context
