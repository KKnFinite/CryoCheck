"""Reusable whole-minute time-of-day parsing and arithmetic."""

from __future__ import annotations

import re
from datetime import time
from typing import Final


MINUTES_PER_DAY: Final = 24 * 60
_MILITARY_TIME_PATTERN: Final = re.compile(
    r"^(?P<hour>[01]\d|2[0-3]):(?P<minute>[0-5]\d)$"
)


def parse_military_time(source_value: str) -> time | None:
    """Parse exact whole-minute HH:MM text without changing the source value."""
    match = _MILITARY_TIME_PATTERN.fullmatch(source_value.strip())
    if match is None:
        return None
    return time(
        hour=int(match.group("hour")),
        minute=int(match.group("minute")),
    )


def minutes_since_midnight(value: time) -> int:
    """Return the exact whole-minute offset represented by a time of day."""
    return value.hour * 60 + value.minute


def crosses_midnight(event_start: time, event_end: time) -> bool:
    """Return whether an overall event end is earlier than its start."""
    return minutes_since_midnight(event_end) < minutes_since_midnight(
        event_start
    )


def elapsed_minutes(
    start: time,
    end: time,
    *,
    crossed_midnight: bool = False,
) -> int | None:
    """Return a forward gap, or None for a same-day end-before-start overlap."""
    difference = minutes_since_midnight(end) - minutes_since_midnight(start)
    if difference >= 0:
        return difference
    if crossed_midnight:
        return difference + MINUTES_PER_DAY
    return None


__all__ = [
    "MINUTES_PER_DAY",
    "crosses_midnight",
    "elapsed_minutes",
    "minutes_since_midnight",
    "parse_military_time",
]
