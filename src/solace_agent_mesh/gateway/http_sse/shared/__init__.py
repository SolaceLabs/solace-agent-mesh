"""
Shared utilities for the HTTP SSE gateway.

Re-exports commonly used utilities from the main shared module for convenience.
"""

from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from solace_agent_mesh.shared.utils.types import UserId

MINIMUM_INTERVAL_SECONDS = 60


def parse_interval_to_seconds(interval_str: str) -> int:
    """Parse an interval string (e.g. '30s', '5m', '1h', '1d') to seconds.

    Raises ValueError if the interval is below MINIMUM_INTERVAL_SECONDS.
    """
    interval_str = interval_str.strip().lower()

    if interval_str.endswith("s"):
        seconds = int(interval_str[:-1])
    elif interval_str.endswith("m"):
        seconds = int(interval_str[:-1]) * 60
    elif interval_str.endswith("h"):
        seconds = int(interval_str[:-1]) * 3600
    elif interval_str.endswith("d"):
        seconds = int(interval_str[:-1]) * 86400
    else:
        seconds = int(interval_str)

    if seconds < MINIMUM_INTERVAL_SECONDS:
        raise ValueError(
            f"Interval must be at least {MINIMUM_INTERVAL_SECONDS} seconds, got {seconds}s"
        )
    return seconds


__all__ = [
    "now_epoch_ms",
    "UserId",
    "MINIMUM_INTERVAL_SECONDS",
    "parse_interval_to_seconds",
]
