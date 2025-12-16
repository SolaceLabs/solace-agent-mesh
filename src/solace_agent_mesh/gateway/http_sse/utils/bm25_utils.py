"""
Utility functions for working with BM25 indexes.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

log = logging.getLogger(__name__)


def get_bm25_indexed_documents(
    session_root_path: str,
    log_prefix: str = "",
) -> List[Dict[str, Any]]:
    """
    List all documents that have BM25 indexes in a session.
    
    Scans the bm25_index directory and extracts document metadata from each
    index's metadata.json file.
    
    Args:
        session_root_path: Root path of the session storage
                          (e.g., /tmp/samv2/sam_dev_user/session-abc123)
        log_prefix: Optional prefix for log messages
    
    Returns:
        List of document metadata dictionaries, each containing:
        - filename: Name of the indexed document
        - filepath: Original path to the document
        - file_type: File extension (e.g., '.pdf', '.docx')
        - size_bytes: File size in bytes
        - total_pages: Number of pages (for PDFs)
        - description: Document description
        - num_chunks: Number of chunks in the index
        - total_chars: Total characters in the document
        - index_dir: Path to the BM25 index directory
    """
    indexed_docs = []
    
    try:
        session_root = Path(session_root_path)
        bm25_index_dir = session_root / "bm25_index"
        
        # Check if BM25 index directory exists
        if not bm25_index_dir.exists():
            log.debug("%sNo BM25 index directory found at %s", log_prefix, bm25_index_dir)
            return []
        
        if not bm25_index_dir.is_dir():
            log.warning("%sBM25 index path is not a directory: %s", log_prefix, bm25_index_dir)
            return []
        
        # Iterate through all subdirectories in bm25_index
        # Each subdirectory represents an indexed document
        for index_subdir in bm25_index_dir.iterdir():
            if not index_subdir.is_dir():
                continue
            
            metadata_file = index_subdir / "metadata.json"
            
            # Check if metadata.json exists
            if not metadata_file.exists():
                log.warning(
                    "%sNo metadata.json found in %s, skipping",
                    log_prefix,
                    index_subdir.name,
                )
                continue
            
            try:
                # Load metadata
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                # Extract document section
                if 'document' not in metadata:
                    log.warning(
                        "%sNo 'document' section in metadata for %s, skipping",
                        log_prefix,
                        index_subdir.name,
                    )
                    continue
                
                doc_info = metadata['document'].copy()
                
                # Add additional index information
                doc_info['num_chunks'] = metadata.get('num_chunks', 0)
                doc_info['total_chars'] = metadata.get('total_chars', 0)
                doc_info['index_dir'] = str(index_subdir)
                doc_info['index_name'] = index_subdir.name
                
                indexed_docs.append(doc_info)
                
                log.debug(
                    "%sFound indexed document: %s (%d chunks)",
                    log_prefix,
                    doc_info.get('filename', 'unknown'),
                    doc_info.get('num_chunks', 0),
                )
                
            except json.JSONDecodeError as e:
                log.error(
                    "%sError parsing metadata.json in %s: %s",
                    log_prefix,
                    index_subdir.name,
                    e,
                )
            except Exception as e:
                log.error(
                    "%sError processing index %s: %s",
                    log_prefix,
                    index_subdir.name,
                    e,
                )
        
        log.info(
            "%sFound %d indexed documents in %s",
            log_prefix,
            len(indexed_docs),
            bm25_index_dir,
        )
        
        return indexed_docs
        
    except Exception as e:
        log.error(
            "%sError listing BM25 indexed documents: %s",
            log_prefix,
            e,
        )
        return []


async def get_bm25_indexed_documents_from_session(
    artifact_service,
    app_name: str,
    user_id: str,
    session_id: str,
    log_prefix: str = "",
) -> List[Dict[str, Any]]:
    """
    List all BM25 indexed documents in a session using the artifact service.
    
    This is an async wrapper that:
    1. Gets an artifact from the session to determine the session root path
    2. Calls get_bm25_indexed_documents() to scan the bm25_index directory
    
    Args:
        artifact_service: Artifact service instance
        app_name: Application name for artifact storage
        user_id: User ID
        session_id: Session ID
        log_prefix: Optional prefix for log messages
    
    Returns:
        List of document metadata dictionaries (same as get_bm25_indexed_documents)
    """
    try:
        from ....agent.utils.artifact_helpers import get_artifact_info_list
        
        # Get session artifacts to determine session root path
        session_artifacts = await get_artifact_info_list(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )
        
        if not session_artifacts:
            log.warning(
                "%sNo artifacts in session, cannot determine session root path",
                log_prefix,
            )
            return []
        
        # Get canonical_uri of first artifact to extract session root
        first_artifact = session_artifacts[0]
        artifact_version = await artifact_service.get_artifact_version(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=first_artifact.filename,
            version=first_artifact.version if first_artifact.version else 0,
        )
        
        if not artifact_version or not artifact_version.canonical_uri:
            log.warning(
                "%sCannot get canonical_uri for session artifacts",
                log_prefix,
            )
            return []
        
        # Extract session root from canonical_uri
        parsed_uri = urlparse(artifact_version.canonical_uri)
        artifact_path = Path(parsed_uri.path)
        session_root = artifact_path.parent.parent

        log.info(
            "%sDetermined session root path for fetching index: %s",
            log_prefix,
            session_root,
        )
        
        # Get indexed documents
        return get_bm25_indexed_documents(
            session_root_path=str(session_root),
            log_prefix=log_prefix,
        )
        
    except Exception as e:
        log.error(
            "%sError getting BM25 indexed documents from session: %s",
            log_prefix,
            e,
        )
        return []
