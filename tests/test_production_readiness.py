"""Focused production-readiness coverage for CryoCheck."""

from __future__ import annotations

import warnings
from datetime import timezone
from email.utils import parsedate_to_datetime

from flask import abort

from app import create_app
from app.extensions import db
from app.models import User
from app.services.settings import create_default_user_settings


_VALID_PASSWORD = "SyntheticPassphrase-42"


def test_remember_cookie_uses_timezone_aware_utc_without_deprecation(
    app,
    client,
):
    with app.app_context():
        user = User(
            username="AwareCookieUser",
            username_normalized="awarecookieuser",
        )
        user.set_password(_VALID_PASSWORD)
        create_default_user_settings(user)
        db.session.add(user)
        db.session.commit()

    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always", DeprecationWarning)
        response = client.post(
            "/login",
            data={
                "username": "AwareCookieUser",
                "password": _VALID_PASSWORD,
                "remember": "y",
            },
        )

    remember_cookie = next(
        header
        for header in response.headers.getlist("Set-Cookie")
        if header.startswith("remember_token=")
    )
    expires_value = remember_cookie.split("Expires=", 1)[1].split(";", 1)[0]
    expires_at = parsedate_to_datetime(expires_value)

    assert response.status_code == 302
    assert caught_warnings == []
    assert expires_at.tzinfo is not None
    assert expires_at.utcoffset() == timezone.utc.utcoffset(expires_at)


def test_favicon_is_linked_and_served_from_conventional_path(client):
    landing = client.get("/")
    favicon = client.get("/favicon.ico")

    assert landing.status_code == 200
    assert b'href="/favicon.ico"' in landing.data
    assert favicon.status_code == 200
    assert favicon.mimetype == "image/svg+xml"
    assert favicon.data.startswith(b"<svg")
    assert b"CryoCheck snowflake" in favicon.data


def test_generic_400_and_403_are_branded_and_hide_descriptions(app, client):
    internal_marker = "private-internal-error-description"

    @app.get("/test-only-bad-request")
    def trigger_bad_request():
        abort(400, description=internal_marker)

    @app.get("/test-only-forbidden")
    def trigger_forbidden():
        abort(403, description=internal_marker)

    bad_request = client.get("/test-only-bad-request")
    forbidden = client.get("/test-only-forbidden")

    assert bad_request.status_code == 400
    assert b"Request could not be processed" in bad_request.data
    assert forbidden.status_code == 403
    assert b"Access denied" in forbidden.data
    for response in (bad_request, forbidden):
        assert b"CryoCheck" in response.data
        assert b'class="error-panel"' in response.data
        assert internal_marker.encode() not in response.data


def test_export_request_size_limit_fails_cleanly_without_echoing_data(
    app,
    client,
):
    private_marker = "private-export-payload-marker"
    app.config["MAX_CONTENT_LENGTH"] = 512

    response = client.post(
        "/export",
        data={
            "export_token": private_marker * 200,
            "scope": "all",
        },
    )

    assert response.status_code == 413
    assert b"CryoCheck" in response.data
    assert b'class="error-panel"' in response.data
    assert b"Exception export request is too large" in response.data
    assert private_marker.encode() not in response.data


def test_production_config_stays_non_debug_when_flask_debug_is_set(
    monkeypatch,
):
    monkeypatch.setenv("FLASK_DEBUG", "1")

    production_app = create_app("production")

    assert production_app.debug is False
    assert production_app.testing is False
    assert production_app.config["DEBUG"] is False
    assert production_app.config["TESTING"] is False
    assert production_app.config["PROPAGATE_EXCEPTIONS"] is False
