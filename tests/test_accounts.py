"""Account registration, login, logout, and password-security coverage."""

from __future__ import annotations

from app.extensions import db
from app.models import User
from app.services.settings import DEFAULT_SETTINGS


VALID_PASSWORD = "SyntheticPassphrase-42"


def register(client, username: str, password: str = VALID_PASSWORD):
    return client.post(
        "/register",
        data={
            "username": username,
            "password": password,
            "confirm_password": password,
        },
    )


def create_user(username: str, password: str = VALID_PASSWORD) -> User:
    from app.services.settings import create_default_user_settings

    user = User(username=username, username_normalized=username.lower())
    user.set_password(password)
    create_default_user_settings(user)
    db.session.add(user)
    db.session.commit()
    return user


def test_registration_creates_account_and_private_default_settings(app, client):
    response = register(client, "  Flight_Ops-1  ")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/settings")
    with app.app_context():
        user = User.query.one()
        assert user.username == "Flight_Ops-1"
        assert user.username_normalized == "flight_ops-1"
        assert user.settings.late_entry_threshold_hours == (
            DEFAULT_SETTINGS.late_entry_threshold_hours
        )
        assert user.settings.type1_fluid == DEFAULT_SETTINGS.type1_fluid
        assert user.settings.type4_fluid == DEFAULT_SETTINGS.type4_fluid
        assert user.settings.allowed_gap_minutes == (
            DEFAULT_SETTINGS.allowed_gap_minutes
        )
        assert user.settings.max_type1_rate_gpm == (
            DEFAULT_SETTINGS.max_type1_rate_gpm
        )
        assert user.settings.max_type4_rate_gpm == (
            DEFAULT_SETTINGS.max_type4_rate_gpm
        )
        assert user.settings.max_event_time_minutes == (
            DEFAULT_SETTINGS.max_event_time_minutes
        )
        assert user.settings.include_gap_in_event_time is False


def test_account_names_are_unique_case_insensitively(app, client):
    assert register(client, "RampLead").status_code == 302
    client.post("/logout")

    response = register(client, "ramplead")

    assert response.status_code == 400
    assert b"That account name is unavailable." in response.data
    with app.app_context():
        assert User.query.count() == 1


def test_invalid_account_names_are_rejected(client):
    for username in ("ab", "has space", "bad.name", "x" * 41):
        response = register(client, username)

        assert response.status_code == 400


def test_short_password_is_rejected(client):
    response = register(client, "Valid_Name", "short")

    assert response.status_code == 400
    assert b"Field must be between 8 and 128 characters long." in response.data


def test_password_confirmation_mismatch_is_rejected(client):
    response = client.post(
        "/register",
        data={
            "username": "Valid_Name",
            "password": VALID_PASSWORD,
            "confirm_password": "DifferentPassphrase-42",
        },
    )

    assert response.status_code == 400
    assert b"Passwords must match." in response.data


def test_password_is_stored_only_as_scrypt_hash(app, client):
    register(client, "Secure_User")

    with app.app_context():
        user = User.query.one()
        assert user.password_hash != VALID_PASSWORD
        assert VALID_PASSWORD not in user.password_hash
        assert user.password_hash.startswith("scrypt:")
        assert user.check_password(VALID_PASSWORD)
        assert not user.check_password("incorrect-password")


def test_valid_login_updates_last_login_and_succeeds(app, client):
    with app.app_context():
        create_user("LoginUser")

    response = client.post(
        "/login",
        data={
            "username": "loginuser",
            "password": VALID_PASSWORD,
            "remember": "y",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/settings")
    with client.session_transaction() as session:
        assert session.permanent is True
    with app.app_context():
        assert User.query.one().last_login_at is not None


def test_invalid_login_uses_same_generic_message(app, client):
    with app.app_context():
        create_user("ExistingUser")

    wrong_password = client.post(
        "/login",
        data={"username": "ExistingUser", "password": "wrong-password"},
    )
    nonexistent = client.post(
        "/login",
        data={"username": "MissingUser", "password": "wrong-password"},
    )

    expected = b"Invalid account name or password."
    assert wrong_password.status_code == 400
    assert nonexistent.status_code == 400
    assert expected in wrong_password.data
    assert expected in nonexistent.data
    assert b"does not exist" not in nonexistent.data


def test_logout_restores_anonymous_session(client):
    register(client, "LogoutUser")

    response = client.post("/logout", follow_redirects=True)

    assert response.status_code == 200
    assert b"Default settings are now active." in response.data
    assert b"Settings: Default" in b" ".join(response.data.split())


def test_login_form_has_checked_persistent_login_option(client):
    response = client.get("/login")

    assert response.status_code == 200
    assert b"Keep me signed in" in response.data
    assert b'checked id="remember"' in response.data


def test_registration_discloses_no_password_recovery(client):
    response = client.get("/register")
    normalized = b" ".join(response.data.split())

    assert b"Password recovery is not currently available." in response.data
    assert b"does not require or retain an email address" in normalized
