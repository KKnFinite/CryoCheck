"""Focused coverage for precipitation interpretation."""

from __future__ import annotations

import pytest

from app.services.precipitation import has_active_precipitation


@pytest.mark.parametrize(
    "source_value",
    ("", "   ", "None", "NONE", "none", " NoNe "),
)
def test_no_active_precipitation_forms(source_value):
    assert has_active_precipitation(source_value) is False


@pytest.mark.parametrize(
    "source_value",
    (
        "Snow",
        "Freezing Rain",
        "Rain",
        "Sleet",
        "Ice Pellets",
        "Mixed Precipitation",
        "Unfamiliar Condition",
    ),
)
def test_every_other_nonblank_value_is_active(source_value):
    assert has_active_precipitation(source_value) is True
