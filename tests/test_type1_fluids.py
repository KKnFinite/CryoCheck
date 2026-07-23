"""Coverage for version-controlled Type I manufacturer reference data."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.type1_fluids import (
    TYPE1_FLUID_PROFILES,
    get_type1_fluid_profile,
)
from app.services.settings import TYPE1_FLUID_OPTIONS


def test_cryotech_polar_plus_lt_chart_is_complete_and_exact():
    profile = get_type1_fluid_profile("Cryotech Polar Plus LT")

    assert profile is not None
    assert len(profile.freezing_points) == 71
    assert tuple(profile.freezing_points) == tuple(range(71))
    assert len(profile.freezing_points) == len(set(profile.freezing_points))
    assert all(
        freeze_point is not None
        for freeze_point in profile.freezing_points.values()
    )
    assert profile.freeze_point_for(50) == Decimal("-17.3")
    assert profile.freeze_point_for(60) == Decimal("-39.2")
    assert profile.freeze_point_for(65) == Decimal("-50.0")
    assert profile.freeze_point_for(70) == Decimal("-59.8")


def test_type1_profile_registry_and_chart_are_read_only():
    profile = get_type1_fluid_profile("Cryotech Polar Plus LT")

    assert profile is not None
    with pytest.raises(TypeError):
        TYPE1_FLUID_PROFILES["Another fluid"] = profile  # type: ignore[index]
    with pytest.raises(TypeError):
        profile.freezing_points[50] = Decimal("0")  # type: ignore[index]


def test_unknown_type1_profile_is_not_invented():
    assert get_type1_fluid_profile("Unknown Type I fluid") is None


def test_type1_settings_options_derive_from_profile_registry():
    assert TYPE1_FLUID_OPTIONS == tuple(TYPE1_FLUID_PROFILES)
