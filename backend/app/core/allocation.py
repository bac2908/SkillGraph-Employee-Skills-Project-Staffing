"""Inclusive calendar-day planning, not timesheets or employee performance."""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta, timezone


def planning_today() -> date:
    # Fixed business calendar for this Vietnamese workspace, independent of host TZ.
    return datetime.now(UTC).astimezone(timezone(timedelta(hours=7))).date()


def day(value: str | date | None, fallback: date) -> date:
    if value is None:
        return fallback
    return value if isinstance(value, date) else date.fromisoformat(value)


def peak_allocation(
    assignments: list[dict],
    start_date: str | date | None = None,
    end_date: str | date | None = None,
) -> int:
    """Maximum simultaneous load, not the sum of all overlapping assignments.

    Null bounds are unbounded (including legacy relationships). Integer ordinals
    avoid timezone/DST issues and safely handle the day after 9999-12-31.
    """
    start = day(start_date, date.min).toordinal()
    end = day(end_date, date.max).toordinal()
    if start > end:
        raise ValueError("end_date must be on or after start_date.")
    events: dict[int, int] = defaultdict(int)
    for assignment in assignments:
        left = max(start, day(assignment.get("start_date"), date.min).toordinal())
        right = min(end, day(assignment.get("end_date"), date.max).toordinal())
        if left <= right:
            events[left] += assignment["allocation"]
            events[right + 1] -= assignment["allocation"]
    current = peak = 0
    for point in sorted(events):
        current += events[point]
        peak = max(peak, current)
    return peak
