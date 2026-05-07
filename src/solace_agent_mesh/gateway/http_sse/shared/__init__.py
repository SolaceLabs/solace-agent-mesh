"""
Shared utilities for the HTTP SSE gateway.

Re-exports commonly used utilities from the main shared module for convenience.
"""

import re

from croniter import croniter

from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from solace_agent_mesh.shared.utils.types import UserId

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
    if seconds > MAXIMUM_INTERVAL_SECONDS:
        raise ValueError(
            f"Interval must be at most {MAXIMUM_INTERVAL_SECONDS} seconds (1 year), got {seconds}s"
        )
    return seconds


# Quartz-style day-of-week tokens used by the scheduled-task UI's "monthly
# weekday" mode: `D#N` (Nth weekday) and `DL` (last weekday). croniter
# accepts `D#N` but not `DL`, and APScheduler's `from_crontab` accepts
# neither — so we recognise them explicitly and route to APScheduler's
# programmatic CronTrigger (`day="2nd mon"` / `day="last fri"`) at schedule
# time. This regex is also used to keep DTO validation aligned with the
# scheduler so a valid expression isn't rejected at create time.
_QUARTZ_WEEKDAY_RE = re.compile(r"^(\d)(#[1-4]|L)$", re.IGNORECASE)


def is_quartz_weekday_cron(expression: str) -> bool:
    """Return True if ``expression`` is a 5-field cron whose day-of-week field
    uses a Quartz extension (Nth weekday `1#2`, last weekday `5L`) and the
    other fields are plain enough that we can translate unambiguously.

    The non-day-of-week fields are validated via croniter (with the Quartz
    token replaced by ``*``) so malformed minute/hour values don't slip
    through this helper and only blow up later at schedule time.
    """
    parts = expression.strip().split()
    if len(parts) != 5:
        return False
    minute, hour, day_of_month, month, day_of_week = parts
    # Only translate when the rest of the expression is plain enough to map
    # onto APScheduler's `day` field unambiguously: month must be `*` and
    # day_of_month must be `*` (otherwise we'd be combining day-of-month and
    # day-of-week constraints, which Quartz allows but cron doesn't).
    if month != "*" or day_of_month != "*":
        return False
    match = _QUARTZ_WEEKDAY_RE.match(day_of_week)
    if not match:
        return False
    weekday = int(match.group(1))
    if not 0 <= weekday <= 6:
        return False
    # Validate minute/hour by substituting the Quartz token with `*` so
    # croniter can sanity-check the remaining standard fields.
    sanitised = " ".join([minute, hour, day_of_month, month, "*"])
    return bool(croniter.is_valid(sanitised))


__all__ = [
    "now_epoch_ms",
    "UserId",
    "MINIMUM_INTERVAL_SECONDS",
    "MAXIMUM_INTERVAL_SECONDS",
    "parse_interval_to_seconds",
    "is_quartz_weekday_cron",
]
