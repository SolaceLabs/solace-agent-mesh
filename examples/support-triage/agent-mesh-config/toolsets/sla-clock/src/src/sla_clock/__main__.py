# Copyright Solace Corporation
# SPDX-License-Identifier: Apache-2.0

"""Works out when a support ticket must get its first response.

Response targets are counted in the support team's business hours, in its
own time zone, skipping weekends and the team's holidays. A P3 that arrives
at 16:30 on a Friday before a holiday Monday is due on Tuesday morning, not
eight hours later. This is calendar arithmetic, so it lives in code rather
than in a prompt.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sam_tool_sdk import (
    ConfigSchemaField,
    SandboxToolContextFacade,
    ToolResult,
    tool_cli,
    with_config_schema,
)

DEFAULT_TIMEZONE = "America/Toronto"
DEFAULT_BUSINESS_HOURS = "09:00-17:00"
DEFAULT_TARGETS = "P1=1h,P2=4bh,P3=8bh,P4=24bh"
WEEKEND = {5, 6}
MAX_DAYS_SEARCHED = 366


@dataclass(frozen=True)
class Target:
    hours: int
    business_hours_only: bool

    def describe(self) -> str:
        unit = "business hour" if self.business_hours_only else "hour, around the clock"
        plural = "s" if self.hours != 1 else ""
        if self.business_hours_only:
            return f"{self.hours} {unit}{plural}"
        return f"{self.hours} hour{plural}, around the clock"


@dataclass(frozen=True)
class SupportCalendar:
    zone: ZoneInfo
    opens: time
    closes: time
    holidays: frozenset[date]

    def is_working_day(self, day: date) -> bool:
        return day.weekday() not in WEEKEND and day not in self.holidays

    def add_business_time(self, start: datetime, remaining: timedelta) -> datetime:
        cursor = start.astimezone(self.zone)
        for _ in range(MAX_DAYS_SEARCHED):
            day = cursor.date()
            day_open = datetime.combine(day, self.opens, self.zone)
            day_close = datetime.combine(day, self.closes, self.zone)
            if not self.is_working_day(day) or cursor >= day_close:
                cursor = datetime.combine(day + timedelta(days=1), self.opens, self.zone)
                continue
            cursor = max(cursor, day_open)
            available = day_close - cursor
            if remaining <= available:
                return cursor + remaining
            remaining -= available
            cursor = datetime.combine(day + timedelta(days=1), self.opens, self.zone)
        raise ValueError("no working day found within a year; check business_hours and holidays")


def parse_targets(spec: str) -> dict[str, Target]:
    targets: dict[str, Target] = {}
    for entry in filter(None, (part.strip() for part in spec.split(","))):
        priority, _, amount = entry.partition("=")
        amount = amount.strip().lower()
        business_hours_only = amount.endswith("bh")
        digits = amount.removesuffix("bh").removesuffix("h")
        if not digits.isdigit():
            raise ValueError(f"response target {entry!r} must look like P2=4bh or P1=1h")
        targets[priority.strip().upper()] = Target(int(digits), business_hours_only)
    return targets


def parse_business_hours(spec: str) -> tuple[time, time]:
    opens, _, closes = spec.partition("-")
    opening, closing = time.fromisoformat(opens.strip()), time.fromisoformat(closes.strip())
    if closing <= opening:
        raise ValueError(f"business_hours {spec!r} must close after it opens")
    return opening, closing


def parse_holidays(spec: str) -> frozenset[date]:
    return frozenset(date.fromisoformat(d.strip()) for d in spec.split(",") if d.strip())


def parse_created_at(value: str) -> datetime:
    if not value.strip():
        return datetime.now(timezone.utc)
    created = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if created.tzinfo is None:
        raise ValueError(f"created_at {value!r} has no UTC offset, so the deadline would be a guess")
    return created


@with_config_schema(
    [
        ConfigSchemaField(
            key="support_timezone",
            description="IANA time zone the support team works in.",
            default=DEFAULT_TIMEZONE,
        ),
        ConfigSchemaField(
            key="business_hours",
            description="Opening and closing time on working days, as HH:MM-HH:MM.",
            default=DEFAULT_BUSINESS_HOURS,
        ),
        ConfigSchemaField(
            key="holidays",
            description="Comma-separated YYYY-MM-DD dates the support team is closed.",
            default="",
        ),
        ConfigSchemaField(
            key="response_targets",
            description="First-response target per priority: Nh is clock hours, Nbh is business hours.",
            default=DEFAULT_TARGETS,
        ),
    ]
)
def compute_response_due(
    priority: str, ctx: SandboxToolContextFacade, created_at: str = ""
) -> ToolResult:
    """Work out when a support ticket must get its first response, in the support team's business hours.

    Args:
        priority: Ticket priority, P1 to P4.
        created_at: When the ticket was created, ISO 8601 with a UTC offset (for example 2026-10-09T20:30:00Z). Leave empty to use the current time.
    """
    try:
        zone_name = ctx.get_config("support_timezone", DEFAULT_TIMEZONE)
        opens, closes = parse_business_hours(ctx.get_config("business_hours", DEFAULT_BUSINESS_HOURS))
        calendar = SupportCalendar(
            zone=ZoneInfo(zone_name),
            opens=opens,
            closes=closes,
            holidays=parse_holidays(ctx.get_config("holidays", "")),
        )
        targets = parse_targets(ctx.get_config("response_targets", DEFAULT_TARGETS))
        created = parse_created_at(created_at)
    except (ValueError, ZoneInfoNotFoundError) as err:
        return ToolResult.error(f"sla-clock is misconfigured or got a bad input: {err}", code="INVALID_INPUT")

    target = targets.get(priority.strip().upper())
    if target is None:
        return ToolResult.error(
            f"no response target for priority {priority!r}; known: {', '.join(sorted(targets))}",
            code="UNKNOWN_PRIORITY",
        )

    allowed = timedelta(hours=target.hours)
    if target.business_hours_only:
        due = calendar.add_business_time(created, allowed)
    else:
        due = (created + allowed).astimezone(calendar.zone)

    respond_by_text = f"{due:%A %-d %B %Y, %H:%M} {due.tzname()}"
    return ToolResult.ok(
        message=f"{priority.upper()} first response due {respond_by_text}",
        data={
            "respond_by": due.isoformat(timespec="minutes"),
            "respond_by_text": respond_by_text,
            "target": target.describe(),
            "support_timezone": zone_name,
        },
    )


cli = tool_cli(compute_response_due)


if __name__ == "__main__":
    cli()
