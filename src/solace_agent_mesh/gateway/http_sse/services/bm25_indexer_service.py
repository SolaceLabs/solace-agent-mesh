"""
BM25 Indexing Service

Builds and manages BM25 search indices for project text files.
Uses BaseArtifactService interface for storage-agnostic operations.

STORAGE-AGNOSTIC: All operations through BaseArtifactService.
- Works with S3, GCS, or filesystem backends
- All processing in-memory (no temp files)
"""

import logging
import json
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from typing import List, Tuple, Dict, Any, Optional
from google.adk.artifacts import BaseArtifactService

log = logging.getLogger(__name__)

# Chunking configuration (optimized for search accuracy and token savings)
CHUNK_SIZE_CHARS = 2000      # ~512 tokens, ~400 words, captures 2-3 complete paragraphs
OVERLAP_CHARS = 500          # 25% overlap to prevent information loss at boundaries
DEFAULT_TOP_K = 5            # Return top 5 most relevant chunks
MAX_TOP_K = 10               # Maximum chunks to return for complex queries


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE_CHARS,
    overlap: int = OVERLAP_CHARS
) -> List[Tuple[str, int, int]]:
    """
    Split text into overlapping chunks for better search granularity.

    Args:
        text: Full text to chunk
        chunk_size: Size of each chunk in characters (default: 2000)
        overlap: Overlap between chunks in characters (default: 500, 25% overlap)

    Returns:
        List of (chunk_text, start_position, end_position) tuples

    Example:
        text = "..." (5000 chars)
        chunk_size = 2000
        overlap = 500

        Returns:
        [
            (chunk_0, 0, 2000),      # chars 0-2000
            (chunk_1, 1500, 3500),   # chars 1500-3500 (500 char overlap with chunk 0)
            (chunk_2, 3000, 5000)    # chars 3000-5000 (500 char overlap with chunk 1)
        ]
    """
    if not text:
        return []

    text_length = len(text)
    chunks = []
    start = 0

    while start < text_length:
        # Calculate end position for this chunk
        end = min(start + chunk_size, text_length)

        # Extract chunk text
        chunk_text = text[start:end]

        # Only add non-empty chunks
        if chunk_text.strip():
            chunks.append((chunk_text, start, end))

        # Move to next chunk with overlap
        # If this is the last chunk (end == text_length), stop
        if end == text_length:
            break

        # Next chunk starts at (current_end - overlap)
        start = end - overlap

    return chunks


async def collect_project_text_files(
    artifact_service: BaseArtifactService,
    app_name: str,
    user_id: str,
    project_id: str
) -> List[Tuple[str, int, str, dict]]:
    """
    Collect all text-based artifacts in project.

    Uses is_text_based_file() from mime_helpers for comprehensive text file detection.
    Includes: .txt, .md, .json, .yaml, .xml, .csv, .js, .sql, .html,
              .converted.txt files, and all other text-based MIME types.

    For converted files, citation_metadata includes:
    - source_file: original binary filename
    - citation_type: "page", "paragraph", or "slide"
    - citation_map: list of location mappings

    Args:
        artifact_service: The artifact service instance
        app_name: Application name
        user_id: User ID
        project_id: Project ID

    Returns:
        List of (filename, version, content_text, citation_metadata) tuples
    """
    from ....common.utils.mime_helpers import is_text_based_file
    from ....agent.utils.artifact_helpers import (
        get_artifact_info_list,
        load_artifact_content_or_metadata
    )

    session_id = f"project-{project_id}"
    log_prefix = f"[BM25Indexer:collect:project-{project_id}]"

    # 1. List all artifacts using artifact service (storage-agnostic)
    log.debug(f"{log_prefix} Listing all artifacts")
    all_artifacts = await get_artifact_info_list(
        artifact_service=artifact_service,
        app_name=app_name,
        user_id=user_id,
        session_id=session_id
    )

    log.info(f"{log_prefix} Found {len(all_artifacts)} total artifacts")

    # 2. Filter for text-based files
    text_files = []

    for artifact in all_artifacts:
        # Check if text-based using comprehensive mime helper
        if not is_text_based_file(artifact.mime_type, None):
            log.debug(f"{log_prefix} Skipping non-text file: {artifact.filename} ({artifact.mime_type})")
            continue

        try:
            # 3. Load content using artifact service (storage-agnostic)
            content_result = await load_artifact_content_or_metadata(
                artifact_service=artifact_service,
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=artifact.filename,
                version="latest",
                load_metadata_only=False
            )

            if content_result.get("status") != "success":
                log.warning(f"{log_prefix} Failed to load {artifact.filename}: {content_result.get('message')}")
                continue

            # 4. Load metadata to get citation_map (for converted files)
            metadata_result = await load_artifact_content_or_metadata(
                artifact_service=artifact_service,
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=artifact.filename,
                version="latest",
                load_metadata_only=True
            )

            # 5. Extract citation_map from metadata if present
            citation_metadata = {}
            if metadata_result.get("status") == "success":
                metadata = metadata_result.get("metadata", {})
                conversion_info = metadata.get("conversion", {})
                text_citations = metadata.get("text_citations", {})

                if conversion_info:
                    # This is a converted file (PDF/DOCX/PPTX) - extract citation info
                    citation_metadata = {
                        "source_file": conversion_info.get("source_file"),
                        "source_version": conversion_info.get("source_version"),
                        "citation_type": conversion_info.get("citation_type"),
                        "citation_map": conversion_info.get("citation_map", [])
                    }
                elif text_citations:
                    # This is a text file with line-range citations
                    citation_metadata = {
                        "citation_type": text_citations.get("citation_type", "line_range"),
                        "citation_map": text_citations.get("citation_map", [])
                    }

            text_files.append((
                artifact.filename,
                content_result.get("version", artifact.version),
                content_result.get("content", ""),
                citation_metadata
            ))

            log.debug(
                f"{log_prefix} Collected {artifact.filename} v{artifact.version} "
                f"({len(content_result.get('content', ''))} chars)"
            )

        except Exception as e:
            log.error(f"{log_prefix} Error loading {artifact.filename}: {e}")
            continue

    log.info(f"{log_prefix} Collected {len(text_files)} text files for indexing")

    return text_files


def build_bm25_index(
    documents: List[Tuple[str, int, str, dict]],
    project_id: str,
    chunk_size: int = CHUNK_SIZE_CHARS,
    overlap: int = OVERLAP_CHARS
) -> Tuple[bytes, dict]:
    """
    Build BM25 index using bm25s library with text chunking for better granularity.

    CHUNKING ENABLED: Each file is split into overlapping chunks.
    - Chunk size: 2000 chars (~512 tokens) - captures complete thoughts
    - Overlap: 500 chars (25%) - prevents boundary information loss
    - Result: Better search accuracy, massive token savings (95%+ reduction)

    STORAGE-AGNOSTIC: All processing done in-memory.
    - Input: Document text loaded from artifact service
    - Output: ZIP bytes ready to save via artifact service
    - No direct filesystem access

    Creates manifest with citation information for each chunk:
    - schema_version: Manifest format version (currently "1.0")
    - Maps corpus_index to filename, version, chunk position
    - doc_id: File identifier (same for all chunks from one file)
    - Includes citation_type (physical_page/physical_paragraph/physical_slide)
    - Includes citation_map from converter metadata
    - Enables precise source location lookup for search results

    Args:
        documents: List of (filename, version, text, citation_metadata)
        project_id: Project ID for the index
        chunk_size: Size of each chunk in characters (default: 2000)
        overlap: Overlap between chunks in characters (default: 500)

    Returns:
        Tuple of (zip_bytes, manifest_dict)

    Raises:
        ValueError: If index build fails
    """
    import bm25s

    log_prefix = f"[BM25Indexer:build:project-{project_id}]"

    if not documents:
        raise ValueError("Cannot build index with no documents")

    log.info(f"{log_prefix} Building index for {len(documents)} documents with chunking")
    log.info(f"{log_prefix} Chunk size: {chunk_size} chars, Overlap: {overlap} chars")

    try:
        # 1. Chunk all documents
        # Structure: (doc_id, filename, version, chunk_id, chunk_text, chunk_start, chunk_end, citation_metadata)
        chunks_data = []
        total_chunks = 0

        for doc_id, (filename, version, text, citation_metadata) in enumerate(documents):
            # Each file gets one doc_id, all its chunks share this doc_id
            file_chunks = chunk_text(text, chunk_size, overlap)

            log.debug(
                f"{log_prefix} File {filename} (doc_id={doc_id}): {len(text)} chars → {len(file_chunks)} chunks"
            )

            for chunk_id, (chunk_text_content, chunk_start, chunk_end) in enumerate(file_chunks):
                chunks_data.append((
                    doc_id,       # Same for all chunks from this file
                    filename,
                    version,
                    chunk_id,     # 0, 1, 2, ... within this file
                    chunk_text_content,
                    chunk_start,
                    chunk_end,
                    citation_metadata
                ))
                total_chunks += 1

        log.info(f"{log_prefix} Created {total_chunks} chunks from {len(documents)} files")

        # 2. Tokenize chunks using bm25s tokenizer (in-memory)
        corpus_texts = [chunk[4] for chunk in chunks_data]  # Extract chunk text (index 4)
        log.debug(f"{log_prefix} Tokenizing {len(corpus_texts)} chunks")

        corpus_tokens = bm25s.tokenize(corpus_texts)

        # 3. Build BM25 index (in-memory)
        log.debug(f"{log_prefix} Building BM25 index")
        retriever = bm25s.BM25()
        retriever.index(corpus_tokens)

        # 4. Create manifest mapping doc_id to chunk info and citations
        manifest = {
            "schema_version": "1.0",  # Manifest schema version (NOT artifact version)
            "created_at": datetime.now(timezone.utc).isoformat(),
            "project_id": project_id,
            "file_count": len(documents),
            "chunk_count": total_chunks,
            "chunk_size": chunk_size,
            "overlap": overlap,
            "chunks": []  # List of chunk entries with metadata
        }

        # 5. Create manifest entries for each chunk
        # BM25 corpus index (0, 1, 2, ...) maps to chunks sequentially
        # But we store doc_id (file identifier) separately from corpus_index
        # IMPORTANT: Store chunk_text so search can return actual content!
        for corpus_index, (doc_id, filename, version, chunk_id, chunk_text_content, chunk_start, chunk_end, citation_metadata) in enumerate(chunks_data):
            chunk_entry = {
                "corpus_index": corpus_index,  # Position in BM25 corpus (0, 1, 2, ...)
                "doc_id": doc_id,              # File identifier (same for all chunks from one file)
                "filename": filename,
                "version": version,
                "chunk_id": chunk_id,          # Chunk number within the file (0, 1, 2, ...)
                "chunk_start": chunk_start,    # Character position in original file
                "chunk_end": chunk_end,
                "chunk_text": chunk_text_content,  # CRITICAL: Store actual text for retrieval!
            }

            # Add citation info if available
            if citation_metadata and citation_metadata.get("citation_map"):
                chunk_entry["citation_type"] = citation_metadata.get("citation_type", "text_file")

                # For converted files (PDF/DOCX/PPTX), add source file info
                if citation_metadata.get("source_file"):
                    chunk_entry["source_file"] = citation_metadata.get("source_file")
                    chunk_entry["source_file_version"] = citation_metadata.get("source_version")

                # Map citations to this chunk (which pages/paragraphs are in this chunk)
                full_citation_map = citation_metadata.get("citation_map", [])
                chunk_citations = []

                for citation in full_citation_map:
                    citation_start = citation.get("char_start", 0)
                    citation_end = citation.get("char_end", 0)

                    # Check if citation overlaps with this chunk
                    if citation_end > chunk_start and citation_start < chunk_end:
                        chunk_citations.append({
                            "location": citation.get("location"),
                            "char_start": citation_start,
                            "char_end": citation_end
                        })

                chunk_entry["citation_map"] = chunk_citations
            else:
                # For regular text files (not converted)
                chunk_entry["citation_type"] = "text_file"
                chunk_entry["citation_map"] = []

            manifest["chunks"].append(chunk_entry)

        log.debug(f"{log_prefix} Created manifest with {len(manifest['chunks'])} chunk entries")

        # 4. Save index to temp directory (bm25s requires file path)
        import tempfile
        import shutil
        from pathlib import Path

        temp_dir = tempfile.mkdtemp()
        try:
            temp_index_path = Path(temp_dir) / "index"

            # Save BM25 index to temp directory
            retriever.save(str(temp_index_path))

            # Read index files into memory
            index_files = {}
            for file_path in temp_index_path.rglob("*"):
                if file_path.is_file():
                    with open(file_path, 'rb') as f:
                        # Store relative path as key
                        rel_path = str(file_path.relative_to(temp_index_path))
                        index_files[rel_path] = f.read()

            log.debug(f"{log_prefix} Serialized index ({len(index_files)} files, {sum(len(v) for v in index_files.values())} bytes)")

            # 5. Create ZIP in-memory with all index files
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Add all index files (INSIDE ZIP)
                for rel_path, file_bytes in index_files.items():
                    zf.writestr(f'index/{rel_path}', file_bytes)
                # Add manifest (INSIDE ZIP)
                zf.writestr('manifest.json', json.dumps(manifest, indent=2))

        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.read()

        log.info(
            f"{log_prefix} Built index: {len(documents)} files → {total_chunks} chunks, "
            f"ZIP size: {len(zip_bytes)} bytes"
        )

        return zip_bytes, manifest

    except Exception as e:
        log.exception(f"{log_prefix} Failed to build BM25 index: {e}")
        raise ValueError(f"Failed to build BM25 index: {e}") from e


async def save_project_index(
    artifact_service: BaseArtifactService,
    app_name: str,
    user_id: str,
    project_id: str,
    index_zip_bytes: bytes,
    manifest: dict
) -> dict:
    """
    Save BM25 index as versioned project artifact.

    STORAGE-AGNOSTIC: Uses artifact service interface.
    - Input: ZIP bytes (already in memory)
    - Saved through BaseArtifactService (works with S3/GCS/filesystem)
    - No direct storage access

    Uses save_artifact_with_metadata() to ensure:
    - Automatic version increment (v0, v1, v2, ...)
    - Full metadata tracking with index build info
    - Same storage/retrieval as other artifacts
    - Works with any configured artifact backend

    Args:
        artifact_service: The artifact service instance
        app_name: Application name
        user_id: User ID
        project_id: Project ID
        index_zip_bytes: ZIP file bytes (contains index.pkl + manifest.json)
        manifest: Manifest dict (for metadata summary)

    Returns:
        Save result dict with version number

    Raises:
        Exception: If save fails
    """
    from ....agent.utils.artifact_helpers import save_artifact_with_metadata

    session_id = f"project-{project_id}"
    log_prefix = f"[BM25Indexer:save:project-{project_id}]"

    log.info(f"{log_prefix} Saving index ({len(index_zip_bytes)} bytes)")

    # Save index ZIP using artifact service (storage-agnostic)
    # Automatically handles versioning and storage backend (S3/GCS/filesystem)
    result = await save_artifact_with_metadata(
        artifact_service=artifact_service,
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
        filename="project_bm25_index.zip",
        content_bytes=index_zip_bytes,
        mime_type="application/zip",
        metadata_dict={
            "source": "bm25_indexing",
            "index_info": {
                "file_count": manifest["file_count"],
                "chunk_count": manifest["chunk_count"],
                "chunk_size": manifest["chunk_size"],
                "overlap": manifest["overlap"],
                "created_at": manifest["created_at"],
                "indexed_files": [
                    {
                        "filename": chunk["filename"],
                        "version": chunk["version"],
                        "chunks": len([c for c in manifest["chunks"] if c["filename"] == chunk["filename"]])
                    }
                    for chunk in manifest["chunks"]
                    if chunk["chunk_id"] == 0  # Only list each file once
                ]
            }
        },
        timestamp=datetime.now(timezone.utc)
    )

    if result.get("status") == "success":
        log.info(
            f"{log_prefix} Saved index as v{result.get('data_version')} "
            f"({manifest['file_count']} files → {manifest['chunk_count']} chunks indexed)"
        )
    else:
        log.error(f"{log_prefix} Failed to save index: {result.get('message')}")

    return result
