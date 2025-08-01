"""Message utility functions for size calculation and validation.

This module provides utilities for calculating and validating message sizes
to ensure they don't exceed configured limits. The size calculation matches
the exact serialization format used by the Solace AI Connector (JSON + UTF-8).
"""

import json
from typing import Any, Dict, Tuple

from solace_ai_connector.common.log import log


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
            # Conservative estimate - assume each character is 4 bytes (max UTF-8)
            return len(str(payload)) * 4


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
        Logs a warning if size exceeds 80% of the limit.
        Logs an error if size exceeds the limit.
    """
    actual_size = calculate_message_size(payload)

    # Check if size exceeds the limit
    if actual_size > max_size_bytes:
        log.error(
            f"Message size validation failed for {component_identifier}: "
            f"payload size ({actual_size} bytes) exceeds maximum allowed "
            f"size ({max_size_bytes} bytes)"
        )
        return False, actual_size

    # Check if size exceeds 80% of the limit (warning threshold)
    warning_threshold = int(max_size_bytes * 0.8)
    if actual_size > warning_threshold:
        log.warning(
            f"Message size warning for {component_identifier}: "
            f"payload size ({actual_size} bytes) exceeds 80% of maximum "
            f"allowed size ({max_size_bytes} bytes)"
        )

    return True, actual_size
