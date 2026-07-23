"""Ownership, validation, reset, and active-settings service coverage."""

from __future__ import annotations

import re
from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import User
from app.services.settings import (
    DEFAULT_SETTINGS,
    create_default_user_settings,
    get_active_settings,
)


VALID_PASSWORD = "SyntheticPassphrase-42"


def _create_user(username: str) -> User:
    user = User(username=username, username_normalized=username.lower())
    user.set_password(VALID_PASSWORD)
    create_default_user_settings(user)
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, username: str):
    return client.post(
        "/login",
        data={"username": username, "password": VALID_PASSWORD},
    )


def _valid_settings(**overrides):
    values = {
        "late_entry_threshold_hours": "48",
        "type1_fluid": "Cryotech Polar Plus LT",
        "type4_fluid": "Cryotech Polar Guard Xtend",
        "allowed_gap_minutes": "9",
        "max_type1_rate_gpm": "72.5",
        "max_type4_rate_gpm": "34.25",
        "max_event_time_minutes": "45",
        "include_gap_in_event_time": "y",
    }
    values.update(overrides)
    return values


def test_default_settings_definition_is_immutable():
    with pytest.raises(FrozenInstanceError):
        DEFAULT_SETTINGS.allowed_gap_minutes = 99  # type: ignore[misc]


def test_anonymous_settings_page_is_read_only(client):
    response = client.get("/settings")

    assert response.status_code == 200
    assert b"Default Settings" in response.data
    assert b"You are using Default settings." in response.data
    assert b"Create Account" in response.data
    assert b"Save Changes" not in response.data
    assert b'name="allowed_gap_minutes"' not in response.data


def test_anonymous_settings_post_redirects_to_login(client):
    response = client.post("/settings", data=_valid_settings())

    assert response.status_code == 302
    assert "/login?next=/settings" in response.headers["Location"]


def test_logged_in_user_can_save_personal_settings(app, client):
    with app.app_context():
        _create_user("SettingsUser")
    _login(client, "SettingsUser")

    response = client.post("/settings", data=_valid_settings())

    assert response.status_code == 302
    with app.app_context():
        settings = User.query.one().settings
        assert settings.late_entry_threshold_hours == 48
        assert settings.allowed_gap_minutes == 9
        assert settings.max_type1_rate_gpm == Decimal("72.500000")
        assert settings.max_type4_rate_gpm == Decimal("34.250000")
        assert settings.max_event_time_minutes == 45
        assert settings.include_gap_in_event_time is True


def test_one_users_changes_do_not_affect_another_or_default(app, client):
    with app.app_context():
        _create_user("UserA")
        _create_user("UserB")
    _login(client, "UserA")

    client.post("/settings", data=_valid_settings(allowed_gap_minutes="27"))

    with app.app_context():
        user_a = User.query.filter_by(username_normalized="usera").one()
        user_b = User.query.filter_by(username_normalized="userb").one()
        assert user_a.settings.allowed_gap_minutes == 27
        assert user_b.settings.allowed_gap_minutes == 5
        assert DEFAULT_SETTINGS.allowed_gap_minutes == 5


def test_reset_to_default_restores_all_values(app, client):
    with app.app_context():
        _create_user("ResetUser")
    _login(client, "ResetUser")
    client.post("/settings", data=_valid_settings())

    response = client.post(
        "/settings/reset",
        data={"confirm_reset": "y"},
    )

    assert response.status_code == 302
    with app.app_context():
        settings = User.query.one().settings
        assert settings.late_entry_threshold_hours == 24
        assert settings.type1_fluid == DEFAULT_SETTINGS.type1_fluid
        assert settings.type4_fluid == DEFAULT_SETTINGS.type4_fluid
        assert settings.allowed_gap_minutes == 5
        assert settings.max_type1_rate_gpm == Decimal("60.000000")
        assert settings.max_type4_rate_gpm == Decimal("30.000000")
        assert settings.max_event_time_minutes == 30
        assert settings.include_gap_in_event_time is False


def test_reset_requires_confirmation(app, client):
    with app.app_context():
        _create_user("ResetConfirmUser")
    _login(client, "ResetConfirmUser")

    response = client.post("/settings/reset", data={})

    assert response.status_code == 400
    assert b"Confirm the reset before continuing." in response.data


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("late_entry_threshold_hours", "12"),
        ("type1_fluid", "Unapproved Type I"),
        ("type4_fluid", "Unapproved Type IV"),
        ("allowed_gap_minutes", "-1"),
        ("allowed_gap_minutes", "100"),
        ("max_type1_rate_gpm", "0"),
        ("max_type1_rate_gpm", "999.01"),
        ("max_type1_rate_gpm", "NaN"),
        ("max_type1_rate_gpm", "0.0000001"),
        ("max_type4_rate_gpm", "0"),
        ("max_type4_rate_gpm", "1000"),
        ("max_type4_rate_gpm", "Infinity"),
        ("max_event_time_minutes", "0"),
        ("max_event_time_minutes", "1000"),
    ),
)
def test_settings_boundaries_reject_invalid_values(
    app,
    client,
    field,
    value,
):
    with app.app_context():
        _create_user(f"Boundary_{field}_{value}".replace(".", "_"))
    _login(client, f"Boundary_{field}_{value}".replace(".", "_"))

    response = client.post("/settings", data=_valid_settings(**{field: value}))

    assert response.status_code == 400


def test_settings_boundary_values_are_accepted(app, client):
    with app.app_context():
        _create_user("BoundaryValid")
    _login(client, "BoundaryValid")

    low = client.post(
        "/settings",
        data=_valid_settings(
            late_entry_threshold_hours="24",
            allowed_gap_minutes="0",
            max_type1_rate_gpm="0.001",
            max_type4_rate_gpm="0.001",
            max_event_time_minutes="1",
        ),
    )
    high = client.post(
        "/settings",
        data=_valid_settings(
            allowed_gap_minutes="99",
            max_type1_rate_gpm="999",
            max_type4_rate_gpm="999",
            max_event_time_minutes="999",
        ),
    )

    assert low.status_code == 302
    assert high.status_code == 302


def test_active_settings_service_returns_default_for_anonymous():
    assert get_active_settings() is DEFAULT_SETTINGS


def test_active_settings_service_returns_private_values_for_user(app):
    with app.app_context():
        user = _create_user("ActiveUser")
        user.settings.allowed_gap_minutes = 22
        db.session.commit()

        active = get_active_settings(user)

        assert active.is_default is False
        assert active.name == "Personal — ActiveUser"
        assert active.allowed_gap_minutes == 22
        assert DEFAULT_SETTINGS.allowed_gap_minutes == 5


def test_import_page_displays_default_and_personal_indicators(app, client):
    anonymous_page = client.get("/").get_data(as_text=True)
    with app.app_context():
        _create_user("IndicatorUser")
    _login(client, "IndicatorUser")
    personal_page = client.get("/").get_data(as_text=True)

    assert re.search(r"Settings:\s+Default", anonymous_page)
    assert re.search(
        r"Settings:\s+Personal &mdash; IndicatorUser",
        personal_page,
    )
