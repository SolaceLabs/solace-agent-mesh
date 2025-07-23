"""
Exports key functions and constants for embed processing.
"""

from .constants import (
    EMBED_DELIMITER_OPEN,
    EMBED_DELIMITER_CLOSE,
    EMBED_TYPE_SEPARATOR,
    EMBED_FORMAT_SEPARATOR,
    EMBED_CHAIN_DELIMITER,
    EMBED_REGEX,
    EARLY_EMBED_TYPES,
    LATE_EMBED_TYPES,
)
from .resolver import (
    evaluate_embed,
    resolve_embeds_in_string,
    resolve_embeds_recursively_in_string,
)

__all__ = [
    "evaluate_embed",
    "resolve_embeds_in_string",
    "resolve_embeds_recursively_in_string",
    "EMBED_DELIMITER_OPEN",
    "EMBED_DELIMITER_CLOSE",
    "EMBED_TYPE_SEPARATOR",
    "EMBED_FORMAT_SEPARATOR",
    "EMBED_CHAIN_DELIMITER",
    "EMBED_REGEX",
    "EARLY_EMBED_TYPES",
    "LATE_EMBED_TYPES",
]
