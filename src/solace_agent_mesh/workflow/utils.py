"""
Utility functions for workflow execution.
"""

import re
from typing import Union


def parse_duration(duration_str: Union[str, int, float]) -> float:
    """
    Parse duration string to seconds.

    Supports formats:
    - '5s', '30s' - seconds
    - '1m', '5m' - minutes
    - '1h', '2h' - hours
    - '1d' - days
    - Plain numbers (int/float) treated as seconds
    - '30' (string without suffix) treated as seconds

    Args:
        duration_str: Duration as string (e.g., '5s', '1m') or number

    Returns:
        Duration in seconds as float

    Raises:
        ValueError: If format is invalid
    """
    # Handle numeric input directly
    if isinstance(duration_str, (int, float)):
        return float(duration_str)

    # Handle string input
    duration_str = str(duration_str).strip().lower()

    # Try to match duration pattern
    match = re.match(r"^(\d+(?:\.\d+)?)\s*(s|m|h|d)?$", duration_str)
    if not match:
        raise ValueError(
            f"Invalid duration format: '{duration_str}'. "
            "Expected format: number with optional suffix (s/m/h/d), e.g., '30s', '5m', '1h'"
        )

    value = float(match.group(1))
    unit = match.group(2) or "s"  # Default to seconds if no suffix

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
    }

    return value * multipliers[unit]
