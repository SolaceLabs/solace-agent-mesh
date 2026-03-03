"""
Utility functions for handling MIME types.
"""

import os
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
    "x-yaml",
    "yml",
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


def is_text_based_file(
    mime_type: Optional[str], content_bytes: Optional[bytes] = None
) -> bool:
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
    elif (
        normalized_mime_type == "application/octet-stream" and content_bytes is not None
    ):
        try:
            sample_size = min(1024, len(content_bytes))
            content_bytes[:sample_size].decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    return False


# Canonical MIME-type ↔ extension mapping.  Both get_extension_for_mime_type()
# and resolve_mime_type() are derived from this single source of truth.
#
# NOTE: When a MIME type maps to more than one extension (e.g. text/yaml → .yaml
# and .yml), only the *primary* extension appears here.  Additional aliases are
# added to _EXTENSION_TO_MIME below.
_MIME_TO_EXTENSION = {
    # Text / code formats
    "text/plain": ".txt",
    "text/html": ".html",
    "text/css": ".css",
    "text/javascript": ".js",
    "text/csv": ".csv",
    "text/markdown": ".md",
    "text/xml": ".xml",
    "text/yaml": ".yaml",
    "text/x-typescript": ".ts",
    "text/jsx": ".jsx",
    "text/x-toml": ".toml",
    "text/x-rust": ".rs",
    "text/x-go": ".go",
    "text/x-kotlin": ".kt",
    "text/x-swift": ".swift",
    "text/x-ruby": ".rb",
    "text/x-php": ".php",
    "text/x-c": ".c",
    "text/x-c++": ".cpp",
    "text/x-python": ".py",
    "text/x-java-source": ".java",
    # Application formats
    "application/json": ".json",
    "application/x-yaml": ".yaml",
    "application/yaml": ".yaml",
    "application/x-sh": ".sh",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    # Image formats
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    # Audio formats
    "audio/wav": ".wav",
    "audio/mp3": ".mp3",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
    "audio/aac": ".aac",
    "audio/m4a": ".m4a",
    # Video formats
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/x-msvideo": ".avi",
    "video/quicktime": ".mov",
}

# Reverse map: extension → MIME type (auto-generated from the canonical map).
_EXTENSION_TO_MIME = {ext: mime for mime, ext in _MIME_TO_EXTENSION.items()}

# Extra extension aliases that can't be derived by inverting _MIME_TO_EXTENSION
# (many-to-one cases where multiple extensions share a single MIME type).
_EXTENSION_TO_MIME.update({
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".jpg": "image/jpeg",
    ".tsx": "text/x-typescript",
    ".bash": "application/x-sh",
    ".env": "text/plain",
    ".ini": "text/plain",
    ".cfg": "text/plain",
    ".hpp": "text/x-c++",
    ".h": "text/x-c",
    ".mmd": "text/plain",
})


def get_extension_for_mime_type(
    mime_type: Optional[str], default_extension: str = ".dat"
) -> str:
    """
    Returns a file extension for a given MIME type.

    Args:
        mime_type: The MIME type string (e.g., 'image/png', 'application/json').
        default_extension: The extension to return if the MIME type is not found.

    Returns:
        The corresponding file extension (e.g., '.png', '.json').
    """
    if not mime_type:
        return default_extension

    normalized = mime_type.lower()
    if normalized == "application/octet-stream":
        return ".bin"

    return _MIME_TO_EXTENSION.get(normalized, default_extension)


def resolve_mime_type(
    filename: Optional[str], provided_mime_type: Optional[str] = None
) -> str:
    """
    Resolves a MIME type from a filename when the provided type is missing or
    ``application/octet-stream`` (the browser default for unrecognised extensions).

    Resolution order:
      1. If *provided_mime_type* is present and not ``application/octet-stream``,
         return it unchanged.
      2. Check the file extension against the canonical extension map.
      3. Return ``application/octet-stream`` if nothing matched.

    Args:
        filename: The original filename (used for extension lookup).
        provided_mime_type: The MIME type reported by the client / browser.

    Returns:
        The best-effort MIME type string.
    """
    fallback = "application/octet-stream"

    if provided_mime_type and provided_mime_type != fallback:
        return provided_mime_type

    if not filename:
        return provided_mime_type or fallback

    ext = os.path.splitext(filename)[1].lower()

    mapped = _EXTENSION_TO_MIME.get(ext)
    if mapped:
        return mapped

    return provided_mime_type or fallback
