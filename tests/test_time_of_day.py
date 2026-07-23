"""Focused coverage for reusable whole-minute time-of-day helpers."""

from __future__ import annotations

from datetime import time

import pytest

from app.services.time_of_day import (
    MINUTES_PER_DAY,
    crosses_midnight,
    elapsed_minutes,
    minutes_since_midnight,
    parse_military_time,
)


@pytest.mark.parametrize(
    ("source_text", "expected"),
    (
        ("00:00", time(0, 0)),
        ("08:05", time(8, 5)),
        ("23:59", time(23, 59)),
        (" 08:05 ", time(8, 5)),
    ),
)
def test_parse_military_time_accepts_exact_whole_minute_text(
    source_text,
    expected,
):
    assert parse_military_time(source_text) == expected


@pytest.mark.parametrize(
    "source_text",
    ("", "8:05", "08:5", "24:00", "23:60", "08:05:00", "8:05 AM"),
)
def test_parse_military_time_rejects_non_hhmm_text(source_text):
    assert parse_military_time(source_text) is None


def test_minutes_since_midnight_is_exact():
    assert minutes_since_midnight(time(0, 0)) == 0
    assert minutes_since_midnight(time(23, 59)) == MINUTES_PER_DAY - 1


def test_crosses_midnight_only_when_end_is_earlier():
    assert crosses_midnight(time(23, 45), time(0, 10)) is True
    assert crosses_midnight(time(8, 0), time(8, 0)) is False
    assert crosses_midnight(time(8, 0), time(9, 0)) is False


def test_elapsed_minutes_supports_same_day_and_overnight_gaps():
    assert elapsed_minutes(time(8, 10), time(8, 10)) == 0
    assert elapsed_minutes(time(8, 10), time(8, 15)) == 5
    assert (
        elapsed_minutes(
            time(23, 58),
            time(0, 3),
            crossed_midnight=True,
        )
        == 5
    )


def test_elapsed_minutes_returns_none_for_same_day_overlap():
    assert elapsed_minutes(time(8, 40), time(8, 30)) is None
