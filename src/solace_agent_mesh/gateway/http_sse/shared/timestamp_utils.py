"""
Epoch timestamp utilities for database portability and timezone handling.

Matches the Java backend pattern:
- Store as epoch milliseconds in database
- Return as ISO 8601 strings via API
- UI handles timezone conversion

This provides a consistent approach across the platform.
"""

import time
from datetime import datetime, timezone


def now_epoch_ms() -> int:
    """
    Get current time as milliseconds since epoch (matches Java pattern).

    Returns:
        Current time as epoch milliseconds
    """
    return int(time.time() * 1000)


def epoch_ms_to_iso8601(epoch_ms: int) -> str:
    """
    Convert epoch milliseconds to ISO 8601 string (matches Java epochLongToIso8601String).

    Args:
        epoch_ms: Time in milliseconds since epoch

    Returns:
        ISO 8601 formatted string in UTC timezone
    """
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).isoformat()


def iso8601_to_epoch_ms(iso8601_string: str) -> int:
    """
    Convert ISO 8601 string to epoch milliseconds (matches Java iso8601StringToEpochLong).

    Args:
        iso8601_string: ISO 8601 formatted datetime string

    Returns:
        Time as epoch milliseconds
    """
    dt = datetime.fromisoformat(iso8601_string.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1000)


def datetime_to_epoch_ms(dt: datetime) -> int:
    """
    Convert datetime object to epoch milliseconds.

    Args:
        dt: Python datetime object

    Returns:
        Time as epoch milliseconds
    """
    return int(dt.timestamp() * 1000)


def epoch_ms_to_datetime(epoch_ms: int) -> datetime:
    """
    Convert epoch milliseconds to datetime object.

    Args:
        epoch_ms: Time in milliseconds since epoch

    Returns:
        Python datetime object in UTC
    """
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)


def validate_epoch_ms(epoch_ms: int | None) -> bool:
    """
    Validate that an epoch milliseconds value is reasonable.

    Args:
        epoch_ms: Time in milliseconds since epoch

    Returns:
        True if the timestamp appears valid
    """
    if epoch_ms is None:
        return False

    # Check if timestamp is in reasonable range
    # After 1970-01-01 and before year 2100
    min_epoch_ms = 0
    max_epoch_ms = 4102444800000  # 2100-01-01 00:00:00 UTC

    return min_epoch_ms <= epoch_ms <= max_epoch_ms
