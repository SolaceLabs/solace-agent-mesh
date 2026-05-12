"""
Shared utilities for the HTTP SSE gateway.

Re-exports commonly used utilities from the main shared module for convenience.
"""

from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from solace_agent_mesh.shared.utils.types import UserId

from .cron import is_quartz_weekday_cron, parse_quartz_weekday_token

MINIMUM_INTERVAL_SECONDS = 60
# 1 year. APScheduler's IntervalTrigger ultimately constructs a timedelta
# whose internal C-int conversion overflows for values past ~68 years; we
# cap well below that and at a value that is operationally sane for a
# recurring task.
MAXIMUM_INTERVAL_SECONDS = 365 * 86400


def parse_interval_to_seconds(interval_str: str) -> int:
    """Parse an interval string (e.g. '30s', '5m', '1h', '1d') to seconds.

    Raises ValueError if the interval is below MINIMUM_INTERVAL_SECONDS or
    above MAXIMUM_INTERVAL_SECONDS.
    """
    original = interval_str
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

    # Include both the original input ("30d") and the resolved seconds in the
    # error so the user sees the value they actually typed — "got 2592000s"
    # by itself is hard to recognise as their "30d" entry.
    if seconds < MINIMUM_INTERVAL_SECONDS:
        raise ValueError(
            f"Interval must be at least {MINIMUM_INTERVAL_SECONDS} seconds, "
            f"got {original!r} ({seconds}s)"
        )
    if seconds > MAXIMUM_INTERVAL_SECONDS:
        raise ValueError(
            f"Interval must be at most {MAXIMUM_INTERVAL_SECONDS} seconds (1 year), "
            f"got {original!r} ({seconds}s)"
        )
    return seconds


__all__ = [
    "now_epoch_ms",
    "UserId",
    "MINIMUM_INTERVAL_SECONDS",
    "MAXIMUM_INTERVAL_SECONDS",
    "parse_interval_to_seconds",
    "is_quartz_weekday_cron",
    "parse_quartz_weekday_token",
]
