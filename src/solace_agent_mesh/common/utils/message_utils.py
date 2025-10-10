"""Message utility functions for size calculation and validation.

This module provides utilities for calculating and validating message sizes
to ensure they don't exceed configured limits. The size calculation matches
the exact serialization format used by the Solace AI Connector (JSON + UTF-8).
"""

import logging
import json
from typing import Any, Dict, Tuple

log = logging.getLogger(__name__)

# Maximum bytes per character in UTF-8 encoding (4 bytes for full Unicode range)
MAX_UTF8_BYTES_PER_CHARACTER = 4


def calculate_message_size(payload: Dict[str, Any]) -> int:
    """Calculate the exact size of a message payload in bytes.

    Uses JSON serialization followed by UTF-8 encoding to match the exact
    format used by the Solace AI Connector.

    Args:
        payload: The message payload dictionary to calculate size for.

    Returns:
        The size of the payload in bytes.

    Note:
        If JSON serialization fails, falls back to string representation
        for size estimation.
    """
    try:
        # Use JSON serialization + UTF-8 encoding to match Solace AI Connector
        json_str = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        return len(json_str.encode("utf-8"))
    except (TypeError, ValueError) as e:
        # Graceful fallback if JSON serialization fails
        log.warning(
            f"Failed to serialize payload to JSON for size calculation: {e}. "
            f"Using string representation fallback."
        )
        try:
            return len(str(payload).encode("utf-8"))
        except Exception as fallback_error:
            log.error(
                f"Fallback size calculation also failed: {fallback_error}. "
                f"Returning conservative estimate."
            )
            # Conservative estimate using maximum UTF-8 bytes per character
            return len(str(payload)) * MAX_UTF8_BYTES_PER_CHARACTER


def validate_message_size(
    payload: Dict[str, Any], max_size_bytes: int, component_identifier: str = "Unknown"
) -> Tuple[bool, int]:
    """Validate that a message payload doesn't exceed the maximum size limit.

    Args:
        payload: The message payload dictionary to validate.
        max_size_bytes: The maximum allowed size in bytes.
        component_identifier: Identifier for the component performing validation
                             (used in log messages).

    Returns:
        A tuple containing:
        - bool: True if the payload is within size limits, False otherwise
        - int: The actual size of the payload in bytes

    Note:
        Logs an error if size exceeds the limit.
    """
    actual_size = calculate_message_size(payload)

    # Check if size exceeds the limit
    if actual_size > max_size_bytes:
        return False, actual_size

    return True, actual_size
