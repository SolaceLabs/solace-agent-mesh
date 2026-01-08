"""
Constants used for embed parsing and processing.
"""

import re
from typing import Set

EMBED_DELIMITER_OPEN = "«"
EMBED_DELIMITER_CLOSE = "»"
EMBED_TYPE_SEPARATOR = ":"
EMBED_FORMAT_SEPARATOR = "|"
EMBED_CHAIN_DELIMITER = ">>>"

# Regex to find potential embeds: «type:expression | format» or «type:expression»
# - Group 1: type (alphanumeric, underscore)
# - Group 2: expression (non-greedy match until | or »)
# - Group 3: (Optional) format specifier (non-greedy match until »)
EMBED_REGEX = re.compile(
    re.escape(EMBED_DELIMITER_OPEN)
    + r"([a-zA-Z0-9_]+)"  # 1: type
    + re.escape(EMBED_TYPE_SEPARATOR)
    + r"(.*?)"  # 2: expression
    + r"(?:"  # Start optional non-capturing group for format
    + r"\s*"  # Optional whitespace before format separator
    + re.escape(EMBED_FORMAT_SEPARATOR)
    + r"\s*"  # Optional whitespace after format separator
    + r"(.*?)"  # 3: format specifier
    + r")?"  # End optional non-capturing group
    + re.escape(EMBED_DELIMITER_CLOSE)
)

EARLY_EMBED_TYPES: Set[str] = {
    "math",
    "datetime",
    "uuid",
    "artifact_meta",
    "status_update",
}
LATE_EMBED_TYPES: Set[str] = {
    "artifact_content",
    "artifact_return",
}

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
