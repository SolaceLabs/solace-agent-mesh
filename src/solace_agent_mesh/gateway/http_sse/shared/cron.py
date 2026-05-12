"""Shared Quartz-style cron helpers.

The scheduled-task UI's "monthly weekday" mode emits day-of-week tokens that
neither plain `croniter` nor APScheduler's `from_crontab` accepts:

    `D#N`  — Nth weekday of the month, e.g. "1#1" = first Monday
    `DL`   — last weekday of the month, e.g. "5L"  = last Friday

We recognise these explicitly and route them to APScheduler's programmatic
`CronTrigger`. This module owns the regex + parsing so the validation path
(DTOs / `is_quartz_weekday_cron`) and the trigger-construction path
(`scheduler_service`) can't drift apart.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from croniter import croniter

# Day-of-week token only: `D#N` (1#1..6#4) or `DL` (0L..6L), case-insensitive.
_QUARTZ_WEEKDAY_RE = re.compile(r"^(\d)(#[1-4]|L)$", re.IGNORECASE)


@dataclass(frozen=True)
class QuartzWeekday:
    """Parsed Quartz day-of-week token.

    `weekday` is 0-6 (Sun-Sat). `nth` is "1".."4" for D#N forms, or None for
    DL (last) — represented separately by `is_last`.
    """

    weekday: int
    nth: Optional[str]
    is_last: bool


def parse_quartz_weekday_token(token: str) -> Optional[QuartzWeekday]:
    """Parse a single day-of-week token. Returns None when the token doesn't
    use the Quartz extensions (so callers can fall through to standard cron).
    """
    match = _QUARTZ_WEEKDAY_RE.match(token)
    if not match:
        return None
    weekday = int(match.group(1))
    if not 0 <= weekday <= 6:
        return None
    qualifier = match.group(2)
    if qualifier.upper() == "L":
        return QuartzWeekday(weekday=weekday, nth=None, is_last=True)
    return QuartzWeekday(weekday=weekday, nth=qualifier[1], is_last=False)


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
    parsed = parse_quartz_weekday_token(day_of_week)
    if parsed is None:
        return False
    sanitised = " ".join([minute, hour, day_of_month, month, "*"])
    return bool(croniter.is_valid(sanitised))


# Names used when translating into APScheduler's CronTrigger `day=` field
# (e.g. "2nd mon", "last fri"). Indexes match croniter's weekday numbering
# (0=Sunday).
WEEKDAY_NAMES = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
NTH_WORDS = {"1": "1st", "2": "2nd", "3": "3rd", "4": "4th"}


__all__ = [
    "QuartzWeekday",
    "WEEKDAY_NAMES",
    "NTH_WORDS",
    "is_quartz_weekday_cron",
    "parse_quartz_weekday_token",
]
