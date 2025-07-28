"""
Utility functions for handling MIME types.
"""

from typing import Optional, Set

TEXT_CONTAINER_MIME_TYPES: Set[str] = {
    "text/plain",
    "text/markdown",
    "text/html",
    "application/json",
    "application/yaml",
    "text/yaml",
    "application/x-yaml",
    "text/x-yaml",
    "application/xml",
    "text/xml",
    "text/csv",
}

_TEXT_BASED_PRIMARY_TYPES = {"text"}
_TEXT_BASED_SUBTYPE_WHOLE = {
    "json",
    "xml",
    "yaml",
    "csv",
    "javascript",
    "ecmascript",
    "xhtml+xml",
    "svg+xml",
    "atom+xml",
    "rss+xml",
    "sparql-query",
    "sparql-update",
    "sql",
    "graphql",
    "markdown",
    "html",
    "rtf",
    "sgml",
}
_TEXT_BASED_SUBTYPE_SUFFIXES_AFTER_PLUS = {
    "json",
    "xml",
    "yaml",
    "csv",
    "svg",
    "xhtml",
}

def is_text_based_mime_type(mime_type: Optional[str]) -> bool:
    """
    Checks if a given MIME type is considered text-based.

    Args:
        mime_type: The MIME type string (e.g., "text/plain", "application/json").

    Returns:
        True if the MIME type is text-based, False otherwise.
    """
    if not mime_type:
        return False

    normalized_mime_type = mime_type.lower().strip()

    if normalized_mime_type.startswith("text/"):
        return True

    if normalized_mime_type in TEXT_CONTAINER_MIME_TYPES:
        return True

    return False


def is_text_based_file(mime_type: Optional[str], content_bytes: Optional[bytes] = None) -> bool:
    """
    Determines if a file is text-based based on its MIME type and content.
    Args:
        mime_type: The MIME type of the file.
        content_bytes: The content of the file as bytes.
    Returns:
        True if the file is text-based, False otherwise.
    """
    if not mime_type:
        return False
        
    normalized_mime_type = mime_type.lower().strip()
    primary_type, _, subtype = normalized_mime_type.partition("/")
    
    if primary_type in _TEXT_BASED_PRIMARY_TYPES:
        return True
    elif subtype in _TEXT_BASED_SUBTYPE_WHOLE:
        return True
    elif "+" in subtype:
        specific_format = subtype.split("+")[-1]
        if specific_format in _TEXT_BASED_SUBTYPE_SUFFIXES_AFTER_PLUS:
            return True
    elif normalized_mime_type == "application/octet-stream" and content_bytes is not None:
        try:
            sample_size = min(1024, len(content_bytes))
            content_bytes[:sample_size].decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
        
    return False