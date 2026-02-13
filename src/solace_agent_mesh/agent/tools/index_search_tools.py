"""
Index Search Tools for Solace Agent Mesh

Provides BM25-based document search capabilities for project documents.
Searches across uploaded files (PDFs, DOCX, PPTX, text files) with precise location citations.
"""

import logging
import json
import zipfile
import tempfile
import shutil
import os
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple
from datetime import datetime, timezone

import bm25s
from google.adk.tools import ToolContext
from google.genai import types as adk_types

from .tool_definition import BuiltinTool
from .registry import tool_registry
from ...common.rag_dto import create_rag_source, create_rag_search_result
from ...agent.utils.artifact_helpers import load_artifact_content_or_metadata
from ...agent.utils.context_helpers import get_original_session_id

log = logging.getLogger(__name__)

# Security limits for ZIP extraction (protection against zip bombs)
MAX_ZIP_SIZE = 500 * 1024 * 1024  # 500MB max compressed size
MAX_UNCOMPRESSED_SIZE = 2 * 1024 * 1024 * 1024  # 2GB max uncompressed size
MAX_FILE_COUNT = 20  # Maximum number of files in archive
MAX_COMPRESSION_RATIO = 100  # Maximum compression ratio (uncompressed:compressed)
MAX_SINGLE_FILE_SIZE = 500 * 1024 * 1024  # 500MB max per file

CATEGORY_NAME = "document_search"
CATEGORY_DESCRIPTION = "Search within project documents using BM25 indexing"

# State key for turn tracking (session-scoped)
_INDEX_SEARCH_TURN_STATE_KEY = "index_search_turn_counter"


def _validate_and_extract_zip(zip_bytes: bytes, extract_path: str, log_prefix: str) -> None:
    """
    Securely validate and extract ZIP archive with protection against zip bombs.

    Security validations:
    1. Check compressed size limit
    2. Validate file count
    3. Check total uncompressed size
    4. Validate compression ratio per file
    5. Check individual file sizes
    6. Sanitize file paths (prevent path traversal)

    Args:
        zip_bytes: Raw ZIP file bytes
        extract_path: Directory to extract files to
        log_prefix: Logging prefix for context

    Raises:
        ValueError: If ZIP file fails security validation
        zipfile.BadZipFile: If ZIP file is corrupted
    """
    # 1. Check compressed size
    compressed_size = len(zip_bytes)
    if compressed_size > MAX_ZIP_SIZE:
        raise ValueError(
            f"ZIP file too large: {compressed_size} bytes "
            f"(max {MAX_ZIP_SIZE} bytes / {MAX_ZIP_SIZE // 1024 // 1024}MB)"
        )

    log.debug(f"{log_prefix} ZIP compressed size: {compressed_size} bytes")

    # Open ZIP for validation
    with zipfile.ZipFile(BytesIO(zip_bytes), 'r') as zf:
        # 2. Validate file count
        file_list = zf.namelist()
        file_count = len(file_list)

        if file_count > MAX_FILE_COUNT:
            raise ValueError(
                f"Too many files in ZIP: {file_count} files "
                f"(max {MAX_FILE_COUNT} files)"
            )

        log.debug(f"{log_prefix} ZIP contains {file_count} files")

        # 3. Calculate total uncompressed size and validate each file
        total_uncompressed = 0

        for zip_info in zf.infolist():
            # Skip directories
            if zip_info.is_dir():
                continue

            file_size = zip_info.file_size
            compressed_file_size = zip_info.compress_size

            # Validate individual file size
            if file_size > MAX_SINGLE_FILE_SIZE:
                raise ValueError(
                    f"File too large: {zip_info.filename} is {file_size} bytes "
                    f"(max {MAX_SINGLE_FILE_SIZE} bytes / {MAX_SINGLE_FILE_SIZE // 1024 // 1024}MB)"
                )

            # Validate compression ratio (avoid division by zero)
            if compressed_file_size > 0:
                compression_ratio = file_size / compressed_file_size
                if compression_ratio > MAX_COMPRESSION_RATIO:
                    raise ValueError(
                        f"Suspicious compression ratio for {zip_info.filename}: "
                        f"{compression_ratio:.1f}x (max {MAX_COMPRESSION_RATIO}x). "
                        f"Possible zip bomb attack."
                    )

            # Validate path traversal (ensure file stays within extract path)
            # Normalize the path and check for ".." components
            normalized_path = os.path.normpath(zip_info.filename)
            if normalized_path.startswith("..") or os.path.isabs(normalized_path):
                raise ValueError(
                    f"Path traversal detected in ZIP: {zip_info.filename}. "
                    f"Possible security attack."
                )

            total_uncompressed += file_size

        # 4. Validate total uncompressed size
        if total_uncompressed > MAX_UNCOMPRESSED_SIZE:
            raise ValueError(
                f"Total uncompressed size too large: {total_uncompressed} bytes "
                f"(max {MAX_UNCOMPRESSED_SIZE} bytes / {MAX_UNCOMPRESSED_SIZE // 1024 // 1024}MB)"
            )

        log.debug(
            f"{log_prefix} ZIP validation passed: "
            f"compressed={compressed_size} bytes, "
            f"uncompressed={total_uncompressed} bytes, "
            f"files={file_count}"
        )

        # 5. Safe extraction with path validation
        # Use extract() instead of extractall() for better control
        for zip_info in zf.infolist():
            # Double-check path safety before extraction
            target_path = os.path.join(extract_path, zip_info.filename)
            normalized_target = os.path.normpath(target_path)

            if not normalized_target.startswith(os.path.normpath(extract_path)):
                raise ValueError(
                    f"Path traversal detected during extraction: {zip_info.filename}"
                )

            # Extract file
            zf.extract(zip_info, extract_path)

        log.info(
            f"{log_prefix} ZIP extracted securely: {file_count} files, "
            f"{total_uncompressed} bytes uncompressed"
        )


def _get_next_index_search_turn(tool_context: Optional[ToolContext]) -> int:
    """
    Get the next search turn number using tool context state.

    This approach stores the turn counter in the tool context state, which is:
    - Per-session scoped (not global)
    - Automatically cleaned up when the session ends

    Each search within a session gets a unique turn number, so citations from
    different searches never collide (e.g., idx0r0, idx0r1 for first search,
    idx1r0, idx1r1 for second search).

    Args:
        tool_context: Tool context for state management

    Returns:
        Turn number (0, 1, 2, ...)
    """
    if not tool_context:
        # Fallback: return 0 if no context (shouldn't happen in practice)
        log.warning("[index_search] No tool_context provided, using turn=0")
        return 0

    # Get current turn from state, defaulting to 0
    current_turn = tool_context.state.get(_INDEX_SEARCH_TURN_STATE_KEY, 0)

    # Increment for next search
    tool_context.state[_INDEX_SEARCH_TURN_STATE_KEY] = current_turn + 1

    return current_turn


def format_location_string(location: str, citation_type: str) -> str:
    """
    Convert raw location to human-readable format.

    Examples:
        "physical_page_3" → "Page 3"
        "physical_paragraph_5" → "Paragraph 5"
        "physical_slide_2" → "Slide 2"
        "lines_1-50" → "Lines 1-50"

    Args:
        location: Raw location string from citation_map
        citation_type: Type of citation (page, paragraph, slide, line_range)

    Returns:
        Human-readable location string
    """
    if not location:
        return ""

    if citation_type == "page" and location.startswith("physical_page_"):
        page_num = location.replace("physical_page_", "")
        return f"Page {page_num}"

    elif citation_type == "paragraph" and location.startswith("physical_paragraph_"):
        para_num = location.replace("physical_paragraph_", "")
        return f"Paragraph {para_num}"

    elif citation_type == "slide" and location.startswith("physical_slide_"):
        slide_num = location.replace("physical_slide_", "")
        return f"Slide {slide_num}"

    elif citation_type == "line_range" and location.startswith("lines_"):
        line_range = location.replace("lines_", "")
        return f"Lines {line_range}"

    # Fallback: return as-is
    return location


def extract_locations(chunk: Dict[str, Any]) -> List[str]:
    """
    Extract human-readable location strings from citation_map.

    Args:
        chunk: Chunk data from manifest with citation_map

    Returns:
        List of human-readable locations (e.g., ["Page 3", "Page 4"])
    """
    citation_map = chunk.get("citation_map", [])
    citation_type = chunk.get("citation_type", "text_file")

    locations = []
    for citation in citation_map:
        location_str = citation.get("location", "")
        formatted = format_location_string(location_str, citation_type)
        if formatted:
            locations.append(formatted)

    return locations


def get_primary_location(chunk: Dict[str, Any]) -> Optional[str]:
    """
    Get the primary (first) location for this chunk.

    Args:
        chunk: Chunk data from manifest

    Returns:
        First location string or None
    """
    locations = extract_locations(chunk)
    return locations[0] if locations else None


def format_location_range(chunk: Dict[str, Any]) -> str:
    """
    Format location range compactly for display.

    Examples:
        Single page: "Page 3"
        Multiple pages: "Pages 3-5"
        Single paragraph: "Paragraph 5"
        Multiple paragraphs: "Paragraphs 5-7"
        Single slide: "Slide 2"
        Multiple slides: "Slides 2-4"
        Lines: "Lines 1-50"

    Args:
        chunk: Chunk data from manifest

    Returns:
        Compact location range string
    """
    citation_map = chunk.get("citation_map", [])
    citation_type = chunk.get("citation_type", "text_file")

    if not citation_map:
        return "Unknown location"

    # Extract numbers from locations
    location_numbers = []
    for citation in citation_map:
        location_str = citation.get("location", "")

        # Extract number based on type
        if citation_type == "page" and "physical_page_" in location_str:
            num = int(location_str.replace("physical_page_", ""))
            location_numbers.append(num)
        elif citation_type == "paragraph" and "physical_paragraph_" in location_str:
            num = int(location_str.replace("physical_paragraph_", ""))
            location_numbers.append(num)
        elif citation_type == "slide" and "physical_slide_" in location_str:
            num = int(location_str.replace("physical_slide_", ""))
            location_numbers.append(num)
        elif citation_type == "line_range" and "lines_" in location_str:
            # For line ranges, return as-is
            return format_location_string(location_str, citation_type)

    if not location_numbers:
        return "Unknown location"

    # Sort numbers
    location_numbers.sort()

    # Format range
    if len(location_numbers) == 1:
        # Single location
        if citation_type == "page":
            return f"Page {location_numbers[0]}"
        elif citation_type == "paragraph":
            return f"Paragraph {location_numbers[0]}"
        elif citation_type == "slide":
            return f"Slide {location_numbers[0]}"
    else:
        # Range
        first = location_numbers[0]
        last = location_numbers[-1]
        if citation_type == "page":
            return f"Pages {first}-{last}"
        elif citation_type == "paragraph":
            return f"Paragraphs {first}-{last}"
        elif citation_type == "slide":
            return f"Slides {first}-{last}"

    return "Unknown location"


async def _load_bm25_index(
    artifact_service,
    app_name: str,
    user_id: str,
    session_id: str,
    tool_context: Optional[ToolContext]
) -> Tuple[Optional[Any], Optional[Dict]]:
    """
    Load BM25 index from project_bm25_index.zip artifact.

    NOTE: Caching is NOT used because BM25 retriever objects are not JSON serializable
    and cannot be stored in tool_context.state (which persists to database).

    DEPLOYMENT SUPPORT:
    - Local terminal: Loads from filesystem storage, uses /tmp
    - K8s container: Loads from GCS/S3, uses container /tmp

    PROCESS:
    1. Load ZIP from artifact service (storage-agnostic)
    2. Create temp directory using tempfile.mkdtemp()
    3. Unzip to temp directory
    4. Load BM25 index using BM25.load() class method
    5. Parse manifest.json
    6. Clean up temp directory immediately
    7. Return retriever and manifest (loaded fresh each time)

    Args:
        artifact_service: Storage-agnostic artifact service
        app_name: Application name
        user_id: User ID
        session_id: Session ID
        tool_context: Tool context for caching

    Returns:
        (retriever, manifest) tuple or (None, None) if not found
    """
    log_prefix = "[IndexSearch:load]"

    # NOTE: Caching removed because BM25 objects are not JSON serializable
    # tool_context.state persists to database, so we can't cache complex objects
    log.info(f"{log_prefix} Loading index from artifact service")

    # 2. Load ZIP artifact bytes (storage-agnostic)
    try:
        load_result = await load_artifact_content_or_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename="project_bm25_index.zip",
            version="latest",
            return_raw_bytes=True,
            load_metadata_only=False
        )

        if load_result["status"] != "success":
            log.warning(f"{log_prefix} Index artifact not found: {load_result.get('message')}")
            return None, None

        zip_bytes = load_result["raw_bytes"]  # FIXED: Use "raw_bytes" not "content_bytes"
        log.info(f"{log_prefix} Loaded ZIP artifact ({len(zip_bytes)} bytes)")

    except Exception as e:
        log.warning(f"{log_prefix} Failed to load index artifact: {e}")
        return None, None

    # 3. Create temporary directory (portable - works for local and K8s)
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp(prefix="bm25_index_")
        log.debug(f"{log_prefix} Created temp directory: {temp_dir}")

        # 4. Validate and extract ZIP securely (protection against zip bombs)
        try:
            _validate_and_extract_zip(zip_bytes, temp_dir, log_prefix)
        except ValueError as ve:
            log.error(f"{log_prefix} ZIP validation failed: {ve}")
            return None, None

        # 5. Load manifest.json
        manifest_path = Path(temp_dir) / "manifest.json"
        if not manifest_path.exists():
            log.error(f"{log_prefix} manifest.json not found in ZIP")
            return None, None

        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        log.info(
            f"{log_prefix} Loaded manifest: "
            f"{manifest.get('file_count')} files, "
            f"{manifest.get('chunk_count')} chunks"
        )

        # 6. Load BM25 index using BM25.load() class method
        index_path = Path(temp_dir) / "index"
        if not index_path.exists():
            log.error(f"{log_prefix} index/ directory not found in ZIP")
            return None, None

        retriever = bm25s.BM25.load(str(index_path))
        log.info(f"{log_prefix} BM25 index loaded into memory successfully")

        # NOTE: No caching - BM25 objects are not JSON serializable
        # Index is loaded fresh for each search (acceptable performance trade-off)

        return retriever, manifest

    except zipfile.BadZipFile as e:
        log.error(f"{log_prefix} Corrupted ZIP file: {e}")
        return None, None

    except Exception as e:
        log.exception(f"{log_prefix} Error loading BM25 index: {e}")
        return None, None

    finally:
        # CRITICAL: Always clean up temp directory
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
            log.debug(f"{log_prefix} Cleaned up temp directory: {temp_dir}")


async def _perform_search(
    retriever,
    manifest: Dict,
    query: str,
    top_k: int,
    min_score: float,
    search_turn: int
) -> List[Dict[str, Any]]:
    """
    Execute BM25 search and map results to chunks with metadata.

    CRITICAL: Uses sequential indexing (0, 1, 2...) for citation IDs,
    NOT chunk_id or corpus_index!

    Normalizes scores using min-max normalization per result set.

    Args:
        retriever: BM25 retriever object
        manifest: Manifest dict with chunks metadata
        query: Search query
        top_k: Number of results to return
        min_score: Minimum score threshold (raw BM25 score)
        search_turn: Search turn number for citation IDs

    Returns:
        List of result dicts with citation_id, chunk_text, score, location info
    """
    log_prefix = f"[IndexSearch:search:turn={search_turn}]"

    # 1. Tokenize query
    log.debug(f"{log_prefix} Tokenizing query: {query}")
    query_tokens = bm25s.tokenize([query])

    # 2. Retrieve top results from BM25
    log.debug(f"{log_prefix} Retrieving top {top_k} results")
    results, scores = retriever.retrieve(query_tokens, k=top_k)

    # results is a 2D array: [[corpus_idx1, corpus_idx2, ...]]
    # scores is a 2D array: [[score1, score2, ...]]
    # Extract first row (single query)
    corpus_indices = results[0].tolist() if len(results) > 0 else []
    bm25_scores = scores[0].tolist() if len(scores) > 0 else []

    log.info(f"{log_prefix} BM25 returned {len(corpus_indices)} results")

    # 3. Map corpus indices to manifest chunks and filter by min_score
    chunks_list = manifest.get("chunks", [])
    search_results = []

    # CRITICAL: Use separate counter for citation IDs to ensure sequential numbering
    # even when filtering results with min_score
    result_index = 0

    for i, (corpus_idx, score) in enumerate(zip(corpus_indices, bm25_scores)):
        # Filter by min_score (using raw BM25 score)
        if score < min_score:
            log.debug(f"{log_prefix} Filtered out BM25 result {i} (score {score:.2f} < {min_score})")
            continue

        # Get chunk data from manifest
        if corpus_idx < len(chunks_list):
            chunk = chunks_list[corpus_idx]

            # CRITICAL: Use result_index (sequential counter), NOT enumerate index i!
            # This ensures idx0r0, idx0r1, idx0r2... even when some results are filtered
            citation_id = f"idx{search_turn}r{result_index}"

            # Extract location information
            location_range = format_location_range(chunk)
            locations = extract_locations(chunk)
            primary_location = get_primary_location(chunk)

            # Build result dict
            result = {
                "citation_id": citation_id,  # Sequential: idx0r0, idx0r1, idx0r2...
                "chunk_text": chunk.get("chunk_text", ""),
                "filename": chunk.get("filename", ""),
                "source_file": chunk.get("source_file") or chunk.get("filename"),
                "score": score,  # Raw BM25 score
                "corpus_index": corpus_idx,  # Store but don't use in citation ID
                "chunk_id": chunk.get("chunk_id"),
                "doc_id": chunk.get("doc_id"),
                "chunk_start": chunk.get("chunk_start"),
                "chunk_end": chunk.get("chunk_end"),
                "citation_type": chunk.get("citation_type"),
                "location_range": location_range,
                "locations": locations,
                "primary_location": primary_location,
                "citation_map": chunk.get("citation_map", []),
                "file_version": chunk.get("version"),
                "source_file_version": chunk.get("source_file_version"),
            }

            search_results.append(result)
            result_index += 1  # Increment only when result is added

    # 4. Normalize scores using min-max normalization (per result set)
    # This makes the top result have relevance_score=1.0, others relative to it
    if search_results:
        max_score = max(r["score"] for r in search_results)
        if max_score > 0:
            for result in search_results:
                result["relevance_score"] = result["score"] / max_score
        else:
            for result in search_results:
                result["relevance_score"] = 0.0

        log.debug(
            f"{log_prefix} Normalized scores: "
            f"raw range=[{min(r['score'] for r in search_results):.2f}, {max_score:.2f}], "
            f"normalized=[{min(r['relevance_score'] for r in search_results):.2f}, 1.0]"
        )

    # Log results
    for i, result in enumerate(search_results):
        log.debug(
            f"{log_prefix} Result {i}: {result['citation_id']} → {result['source_file']} "
            f"({result['location_range']}), raw_score={result['score']:.2f}, "
            f"normalized={result.get('relevance_score', 0):.2f}"
        )

    log.info(f"{log_prefix} Returning {len(search_results)} results after filtering")
    return search_results


def _format_results_for_llm(
    query: str,
    search_turn: int,
    results: List[Dict[str, Any]],
    valid_citation_ids: List[str]
) -> str:
    """
    Format search results in a clear, structured way that helps the LLM
    correctly associate citation IDs with content.

    IMPORTANT: Results must already have citation_id set to idx{turn}r{i}
    where i is the sequential result index (0, 1, 2...)

    Args:
        query: The search query
        search_turn: Search turn number
        results: List of search results with citation_id already set
        valid_citation_ids: List of valid citation IDs for this search

    Returns:
        Formatted string for LLM consumption
    """
    formatted = []

    # Header
    formatted.append(f"=== DOCUMENT SEARCH RESULTS (Turn {search_turn}) ===")
    formatted.append(f"Query: {query}")
    formatted.append(f"Valid citation IDs: {', '.join(valid_citation_ids)}")
    formatted.append(f"Total results: {len(results)}")
    formatted.append("")

    # Each result
    for i, result in enumerate(results):
        citation_id = result["citation_id"]  # Should be idx{turn}r{i}
        formatted.append(f"--- RESULT {i+1} ---")
        formatted.append(f"CITATION ID: [[cite:{citation_id}]]")
        formatted.append(f"SOURCE FILE: {result.get('source_file') or result['filename']}")
        formatted.append(f"LOCATION: {result.get('location_range', 'N/A')}")
        formatted.append(f"RELEVANCE SCORE: {result['score']:.2f}")
        formatted.append(f"CONTENT:")
        formatted.append(f"{result['chunk_text']}")
        formatted.append(f"")
        formatted.append(f"USE [[cite:{citation_id}]] to cite facts from THIS result only")
        formatted.append("")

    # Footer with instructions
    formatted.append("=== END DOCUMENT SEARCH RESULTS ===")
    formatted.append("")
    formatted.append("IMPORTANT CITATION RULES:")
    formatted.append("1. Each citation ID is UNIQUE to its result")
    formatted.append("2. Only use a citation ID for facts that appear in THAT specific result's CONTENT")
    formatted.append("3. Multiple searches in this session use different turn numbers to prevent collisions")
    formatted.append("4. When referencing the original source, use the SOURCE FILE name (e.g., 'report.pdf', not 'report.pdf.converted.txt')")
    formatted.append("")

    return "\n".join(formatted)


async def index_search(
    query: str,
    top_k: int = 5,
    min_score: float = 0.0,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Search project documents using BM25 full-text indexing.

    Args:
        query: The search query
        top_k: Number of results to return (1-10)
        min_score: Minimum BM25 score threshold (0.0-100.0)
        tool_context: ADK tool context
        tool_config: Tool configuration

    Returns:
        Dict with status, results, rag_metadata, formatted_results, etc.
    """
    log_identifier = "[index_search]"

    try:
        # Get session context
        if not tool_context:
            log.error(f"{log_identifier} No tool_context provided")
            return {
                "status": "error",
                "message": "Tool context is missing",
                "error_code": "NO_CONTEXT"
            }

        inv_context = tool_context._invocation_context
        if not inv_context:
            log.error(f"{log_identifier} No invocation context")
            return {
                "status": "error",
                "message": "Invocation context is missing",
                "error_code": "NO_CONTEXT"
            }

        artifact_service = inv_context.artifact_service
        app_name = inv_context.app_name
        user_id = inv_context.user_id
        session_id = get_original_session_id(inv_context)

        log.info(
            f"{log_identifier} Starting document search: query='{query}', "
            f"top_k={top_k}, min_score={min_score}"
        )

        # Get search turn number for citation tracking
        search_turn = _get_next_index_search_turn(tool_context)
        log.debug(f"{log_identifier} Search turn: {search_turn}")

        # Load BM25 index (with caching)
        retriever, manifest = await _load_bm25_index(
            artifact_service,
            app_name,
            user_id,
            session_id,
            tool_context
        )

        if retriever is None or manifest is None:
            log.warning(f"{log_identifier} No BM25 index found")
            return {
                "status": "error",
                "message": (
                    "No document index found. Project indexing may not be enabled, "
                    "or no documents have been indexed yet. "
                    "Please upload documents to the project or contact your administrator."
                ),
                "error_code": "INDEX_NOT_FOUND"
            }

        # Perform search
        results = await _perform_search(
            retriever,
            manifest,
            query,
            top_k,
            min_score,
            search_turn
        )

        # Handle empty results
        if len(results) == 0:
            log.info(f"{log_identifier} No results found for query: {query}")
            return {
                "status": "success",
                "message": (
                    "No relevant results found for your query. "
                    "Try rephrasing your search with different keywords, "
                    "or use a more general query."
                ),
                "results": [],
                "num_results": 0,
                "formatted_results": (
                    f"No results found for query: {query}\n"
                    "Suggestions:\n"
                    "- Try different keywords\n"
                    "- Use more general terms\n"
                    "- Check if the information exists in the uploaded documents"
                ),
                "valid_citation_ids": [],
                "search_turn": search_turn,
                "rag_metadata": create_rag_search_result(
                    query=query,
                    search_type="document_search",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    sources=[],
                    turn_number=search_turn
                )
            }

        # Create RAG sources
        rag_sources = []
        valid_citation_ids = []

        log.debug(f"{log_identifier} === CITATION TO SOURCE MAPPING (turn {search_turn}) ===")

        # FIXED: Use enumerate here since results are already filtered and sequential
        for i, result in enumerate(results):
            citation_id = result["citation_id"]
            valid_citation_ids.append(citation_id)

            # Log citation mapping
            log.debug(
                f"{log_identifier} Citation [[cite:{citation_id}]] → "
                f"File: {result['source_file']} ({result['location_range']}), "
                f"Raw score: {result['score']:.2f}, Normalized: {result['relevance_score']:.2f}"
            )

            # Create RAG source
            # Use 'i' here since results are already filtered - i matches the citation numbering
            rag_source = create_rag_source(
                citation_id=citation_id,
                file_id=f"index_search_{search_turn}_{i}",
                filename=result["source_file"],
                title=f"{result['source_file']} ({result['location_range']})",
                source_type="document",
                source_url=None,  # Internal file, no URL
                content_preview=result["chunk_text"][:200],
                relevance_score=result["relevance_score"],  # Normalized 0-1 (min-max)
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                metadata={
                    "corpus_index": result["corpus_index"],
                    "chunk_id": result["chunk_id"],
                    "doc_id": result["doc_id"],
                    "citation_type": result["citation_type"],
                    "locations": result["locations"],
                    "primary_location": result["primary_location"],
                    "location_range": result["location_range"],
                    "source_file": result["source_file"],
                    "source_file_version": result.get("source_file_version"),
                    "file_version": result["file_version"],
                    "chunk_start": result["chunk_start"],
                    "chunk_end": result["chunk_end"],
                    "citation_map": result["citation_map"],
                    "search_type": "document_search",
                    "bm25_score": result["score"],  # Preserve raw BM25 score
                }
            )
            rag_sources.append(rag_source)

        log.debug(f"{log_identifier} === END CITATION MAPPING ===")
        log.debug(f"{log_identifier} Valid citation IDs for this search: {valid_citation_ids}")

        # Create RAG metadata
        rag_metadata = create_rag_search_result(
            query=query,
            search_type="document_search",
            timestamp=datetime.now(timezone.utc).isoformat(),
            sources=rag_sources,
            turn_number=search_turn
        )

        # Format results for LLM
        formatted_results = _format_results_for_llm(
            query,
            search_turn,
            results,
            valid_citation_ids
        )

        log.info(
            f"{log_identifier} Search successful: {len(results)} results "
            f"(turn={search_turn}, citation_prefix=idx{search_turn}r)"
        )

        return {
            "status": "success",
            "message": f"Found {len(results)} relevant results",
            "results": results,
            "num_results": len(results),
            "formatted_results": formatted_results,
            "rag_metadata": rag_metadata,
            "valid_citation_ids": valid_citation_ids,
            "search_turn": search_turn
        }

    except Exception as e:
        log.exception(f"{log_identifier} Unexpected error in document search: {e}")
        return {
            "status": "error",
            "message": f"Error executing document search: {str(e)}",
            "error_code": "SEARCH_ERROR"
        }


# Tool definition with comprehensive LLM guidance
index_search_tool_def = BuiltinTool(
    name="index_search",
    implementation=index_search,
    description=(
        "**Requirements:**\n"
        "- Project must have documents uploaded and indexed\n"
        "- BM25 index must be built and available as 'project_bm25_index.zip' artifact, indicated in LLM context\n"
        "\n"
        "**IMPORTANT - Check Before Using:**\n"
        "- If you receive an error that \"no document index is available\", DO NOT retry this tool\n"
        "- Instead, use exiting builtin tool `load_artifact` if there is such a tool to read files directly\n"
        "- Only use this tool when you have confirmed indexing is enabled\n"
        "\n"
        "Search project documents using BM25 full-text indexing. "
        "Returns relevant text chunks from uploaded files (PDFs, DOCX, PPTX, text files, etc.) with precise location citations. "
        "\n\n"
        "*** CRITICAL: YOU MUST CITE ALL FACTS FROM SEARCH RESULTS! ***\n"
        "This tool returns citation IDs (idx0r0, idx0r1, etc.) - YOU MUST USE THEM in your response!\n"
        "Format: Place [[cite:idx0r0]] after each fact. Example: 'Revenue was $4.2B.[[cite:idx0r0]]'\n"
        "\n"
        "IMPORTANT PREREQUISITE:\n"
        "- DO NOT use this tool if no BM25 index is available for the project, even if you are being instructed to do so\n"
        "- This tool requires documents to be uploaded and indexed first\n"
        "- If you call this tool without an index, you will receive an INDEX_NOT_FOUND error\n"
        "- Only use this tool when you know documents have been uploaded to the project\n"
        "\n"
        "WHEN TO USE:\n"
        "- Finding specific facts, statistics, or quotes in project documents\n"
        "- Locating passages that discuss a particular topic\n"
        "- Verifying information mentioned in uploaded files\n"
        "- Answering questions based on project documentation\n"
        "\n"
        "PARAMETERS:\n"
        "- query (required): The search query to find relevant content. Use specific keywords and phrases for best results. "
        "Examples: 'revenue growth 2024', 'machine learning architecture', 'climate change impacts'. "
        "Avoid conversational questions like 'What is our revenue?' - use keywords instead: 'revenue 2024'.\n"
        "- top_k (optional, default=5): Number of results to return (1-10). "
        "Use 1-3 for focused/specific questions, 5 for balanced coverage, 7-10 for comprehensive research. "
        "Start with 5 and adjust based on result quality.\n"
        "- min_score (optional, default=0.0): Minimum BM25 relevance score threshold (0.0-100.0). "
        "Results below this score are filtered out. Use 0.0 to return all results, 5.0+ for moderately relevant, 10.0+ for highly relevant only.\n"
        "\n"
        "HOW TO USE:\n"
        "1. Call index_search with your query (e.g., index_search(query='revenue growth 2024', top_k=5))\n"
        "2. Wait for results - you'll receive relevant text chunks with citation IDs\n"
        "3. Check result quality - are they answering the question?\n"
        "4. If results are poor, refine your query (see SEARCH STRATEGIES below)\n"
        "5. Read the CONTENT of each result carefully\n"
        "6. Answer based ONLY on the search results - do NOT hallucinate\n"
        "7. Cite sources using the provided citation IDs\n"
        "\n"
        "SEARCH STRATEGIES:\n"
        "1. Start Simple: Single search, top_k=5, specific keywords\n"
        "2. If Poor Results: Rephrase query with synonyms, broader terms, or different angles\n"
        "3. For Complex Questions: Multiple targeted searches (each gets unique citations: idx0r*, idx1r*, idx2r*)\n"
        "4. For Comprehensive Coverage: Single search with top_k=10\n"
        "5. To Filter Noise: Add min_score=5.0 or higher after seeing initial results\n"
        "\n"
        "EXAMPLES:\n"
        "- Simple: index_search(query='revenue 2024', top_k=5)\n"
        "- Refined: First try 'AI strategy' (poor) → Then try 'artificial intelligence initiatives' (better)\n"
        "- Multi-search: 'revenue and margins' → Search 'revenue 2024' + 'profit margin 2024' separately\n"
        "- Broad: index_search(query='sustainability', top_k=10) for all mentions\n"
        "- Filtered: index_search(query='employee count', top_k=5, min_score=8.0) for precision\n"
        "\n"
        "CITATION RULES:\n"
        "- Each result has a unique citation ID in format [[cite:idxTrN]] where T=turn number, N=result index\n"
        "- First search: idx0r0, idx0r1, idx0r2, etc.\n"
        "- Second search: idx1r0, idx1r1, idx1r2, etc.\n"
        "- ONLY cite facts that appear in that specific result's CONTENT\n"
        "- Place citations AFTER the period: 'This is a fact.[[cite:idx0r0]]'\n"
        "- Multiple citations: 'Fact from two sources.[[cite:idx0r0]][[cite:idx0r1]]'\n"
        "- DO NOT manually list sources - the UI displays them automatically\n"
        "\n"
        "LOCATION INFORMATION:\n"
        "- Results include precise locations: 'Page 5', 'Paragraph 8', 'Slide 3', or 'Lines 1-50'\n"
        "- When referencing sources, use the SOURCE FILE name (e.g., 'report.pdf', not 'report.pdf.converted.txt')\n"
        "- The formatted_results field shows each result with its citation ID and location\n"
        "\n"
        "IMPORTANT:\n"
        "- You MUST call this tool BEFORE answering questions about documents\n"
        "- You MUST wait for results before responding\n"
        "- You MUST base answers on actual results, not assumptions\n"
        "- Each citation ID is UNIQUE to its result - don't mix them up\n"
        "- If results are insufficient, try rephrasing your query or searching multiple times with different keywords\n"
        "- Multiple searches are encouraged for complex questions - each gets unique citation IDs"
    ),
    category=CATEGORY_NAME,
    category_name="Document Search",
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:document_search:execute"],
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results (1-10)",
                "minimum": 1,
                "maximum": 10,
                "default": 5
            },
            "min_score": {
                "type": "number",
                "description": "Minimum relevance score (0.0-100.0)",
                "minimum": 0.0,
                "maximum": 100.0,
                "default": 0.0
            }
        },
        "required": ["query"]
    },
)

# Register the tool
tool_registry.register(index_search_tool_def)

log.info("Document search tool registered: index_search")
