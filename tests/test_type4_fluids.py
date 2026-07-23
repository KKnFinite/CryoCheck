"""Coverage for version-controlled Type IV BRIX reference data."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from app.services.settings import TYPE4_FLUID_OPTIONS
from app.services.type4_fluids import (
    TYPE4_FLUID_PROFILES,
    get_type4_fluid_profile,
    load_type4_fluid_profiles,
)


def test_cryotech_polar_guard_xtend_profile_is_exact():
    profile = get_type4_fluid_profile("Cryotech Polar Guard Xtend")

    assert profile is not None
    assert profile.minimum_brix == Decimal("34.6")
    assert profile.maximum_brix == Decimal("36.6")


def test_type4_settings_options_derive_from_profile_registry():
    assert TYPE4_FLUID_OPTIONS == tuple(TYPE4_FLUID_PROFILES)


def test_type4_registry_and_profiles_are_immutable():
    profile = get_type4_fluid_profile("Cryotech Polar Guard Xtend")

    assert profile is not None
    with pytest.raises(TypeError):
        TYPE4_FLUID_PROFILES["Another fluid"] = profile  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        profile.minimum_brix = Decimal("0")  # type: ignore[misc]


def test_type4_reference_loading_requires_no_app_context_or_network(
    tmp_path,
    monkeypatch,
):
    reference_path = tmp_path / "type4.csv"
    reference_path.write_text(
        "Fluid,Minimum BRIX,Maximum BRIX\n"
        "Offline Test Fluid,1.2,3.4\n",
        encoding="utf-8",
    )

    def fail_network(*args, **kwargs):
        del args, kwargs
        raise AssertionError("Network access was attempted.")

    monkeypatch.setattr("socket.create_connection", fail_network)

    profiles = load_type4_fluid_profiles(reference_path)

    assert profiles["Offline Test Fluid"].minimum_brix == Decimal("1.2")
    assert profiles["Offline Test Fluid"].maximum_brix == Decimal("3.4")


@pytest.mark.parametrize(
    ("contents", "message_fragment"),
    (
        (
            "Fluid,Minimum BRIX,Maximum BRIX\n"
            "Duplicate,1.0,2.0\n"
            "Duplicate,1.0,2.0\n",
            "Duplicate Type IV",
        ),
        (
            "Fluid,Minimum BRIX,Maximum BRIX\n"
            "Missing Minimum,,2.0\n",
            "Missing Type IV",
        ),
        (
            "Fluid,Minimum BRIX,Maximum BRIX\n"
            "Missing Maximum,1.0,\n",
            "Missing Type IV",
        ),
        (
            "Fluid,Minimum BRIX,Maximum BRIX\n"
            "Malformed,not-a-number,2.0\n",
            "Malformed Type IV",
        ),
        (
            "Fluid,Minimum BRIX,Maximum BRIX\n"
            "Non-finite,NaN,2.0\n",
            "Non-finite Type IV",
        ),
        (
            "Fluid,Minimum BRIX,Maximum BRIX\n"
            "Reversed,2.1,2.0\n",
            "minimum exceeds maximum",
        ),
        (
            "Name,Minimum BRIX,Maximum BRIX\n"
            "Wrong Header,1.0,2.0\n",
            "headers",
        ),
        (
            "Fluid,Minimum BRIX,Maximum BRIX\n",
            "contains no profiles",
        ),
    ),
)
def test_invalid_type4_reference_data_is_rejected(
    tmp_path,
    contents,
    message_fragment,
):
    reference_path = tmp_path / "invalid-type4.csv"
    reference_path.write_text(contents, encoding="utf-8")

    with pytest.raises(RuntimeError, match=message_fragment):
        load_type4_fluid_profiles(reference_path)


def test_unknown_type4_profile_is_not_invented():
    assert get_type4_fluid_profile("Unknown Type IV fluid") is None
