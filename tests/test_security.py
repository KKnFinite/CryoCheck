"""CSRF, rate-limit, cookies, and safe-return security coverage."""

from __future__ import annotations

import re

from app import create_app
from app.extensions import db, limiter
from app.models import User
from app.services.settings import create_default_user_settings


VALID_PASSWORD = "SyntheticPassphrase-42"


def test_csrf_is_enabled_outside_testing():
    production_app = create_app("production")

    assert production_app.config["WTF_CSRF_ENABLED"] is True


def test_authentication_forms_contain_csrf_tokens():
    production_app = create_app("production")
    client = production_app.test_client()

    login_page = client.get("/login", base_url="https://localhost")
    register_page = client.get("/register", base_url="https://localhost")

    assert b'name="csrf_token"' in login_page.data
    assert b'name="csrf_token"' in register_page.data


def test_login_and_registration_limits_are_configured(app):
    configured_limits = repr(limiter.limit_manager._decorated_limits)

    assert app.config["LOGIN_RATE_LIMIT"] == "10 per 15 minutes"
    assert app.config["REGISTRATION_RATE_LIMIT"] == "5 per hour"
    assert "10 per 15 minutes" in configured_limits
    assert "5 per hour" in configured_limits


def test_production_cookie_security_configuration():
    app = create_app("production")

    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["REMEMBER_COOKIE_HTTPONLY"] is True
    assert app.config["REMEMBER_COOKIE_SAMESITE"] == "Lax"
    assert app.config["REMEMBER_COOKIE_SECURE"] is True
    assert app.config["REMEMBER_COOKIE_DURATION"].days == 30
    assert app.config["PERMANENT_SESSION_LIFETIME"].days == 30


def test_development_and_testing_do_not_require_secure_cookies(app):
    development_app = create_app("development")

    assert development_app.config["SESSION_COOKIE_SECURE"] is False
    assert development_app.config["REMEMBER_COOKIE_SECURE"] is False
    assert app.config["SESSION_COOKIE_SECURE"] is False
    assert app.config["REMEMBER_COOKIE_SECURE"] is False


def test_unsafe_next_url_is_not_followed(app, client):
    with app.app_context():
        user = User(username="SafeUser", username_normalized="safeuser")
        user.set_password(VALID_PASSWORD)
        create_default_user_settings(user)
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/login",
        data={
            "username": "SafeUser",
            "password": VALID_PASSWORD,
            "next_url": "https://attacker.invalid/collect",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/settings")
    assert "attacker.invalid" not in response.headers["Location"]


def test_safe_next_url_is_followed(app, client):
    with app.app_context():
        user = User(username="RulesReturn", username_normalized="rulesreturn")
        user.set_password(VALID_PASSWORD)
        create_default_user_settings(user)
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/login",
        data={
            "username": "RulesReturn",
            "password": VALID_PASSWORD,
            "next_url": "/rules",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/rules")


def test_missing_csrf_token_uses_branded_error_page():
    production_app = create_app("production")
    client = production_app.test_client()

    response = client.post("/login", base_url="https://localhost")

    assert response.status_code == 400
    assert b"Security check failed" in response.data
    assert b"CryoCheck" in response.data


def test_registration_rate_limit_uses_branded_error_page():
    production_app = create_app("production")
    client = production_app.test_client()
    page = client.get("/register", base_url="https://rate-limit.local")
    token_match = re.search(
        rb'name="csrf_token" type="hidden" value="([^"]+)"',
        page.data,
    )
    assert token_match is not None
    token = token_match.group(1).decode()

    responses = [
            client.post(
                "/register",
                base_url="https://rate-limit.local",
                headers={"Referer": "https://rate-limit.local/register"},
                data={
                "csrf_token": token,
                "username": "bad name",
                "password": VALID_PASSWORD,
                "confirm_password": VALID_PASSWORD,
            },
        )
        for _ in range(6)
    ]

    assert responses[-1].status_code == 429
    assert b"Too many attempts" in responses[-1].data
    assert b"CryoCheck" in responses[-1].data
