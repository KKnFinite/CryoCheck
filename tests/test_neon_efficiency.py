"""Focused Neon control-plane efficiency monitoring coverage."""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from decimal import Decimal
from urllib.error import HTTPError, URLError

from app.extensions import db
from app.models import User
from app.services.neon_efficiency import (
    NeonEfficiency,
    configuration_status,
    fetch_neon_efficiency,
)
from app.services.settings import create_default_user_settings


VALID_PASSWORD = "SyntheticPassphrase-42"
API_KEY_MARKER = "PRIVATE-NEON-API-KEY-73A9"
PROJECT_ID = "winter-project-12345678"


class _Response:
    def __init__(self, payload):
        self._body = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size=-1):
        return self._body.read(size)


def _project_payload(*, min_cu="0.25", max_cu=2, timeout=300):
    return {
        "project": {
            "id": PROJECT_ID,
            "org_id": "org-winter-12345678",
            "default_endpoint_settings": {
                "autoscaling_limit_min_cu": min_cu,
                "autoscaling_limit_max_cu": max_cu,
                "suspend_timeout_seconds": timeout,
            },
            "compute_last_active_at": "2026-08-15T14:30:00Z",
            "consumption_period_start": "2026-08-01T00:00:00Z",
            "consumption_period_end": "2026-09-01T00:00:00Z",
        }
    }


def _history_payload(*, compute_unit_seconds=7200):
    return {
        "projects": [
            {
                "project_id": PROJECT_ID,
                "periods": [
                    {
                        "period_id": "7d6ea9a8-b0f0-49f2-88bf-8aa14777081f",
                        "period_plan": "launch",
                        "period_start": "2026-08-01T00:00:00Z",
                        "consumption": [
                            {
                                "timeframe_start": "2026-08-01T00:00:00Z",
                                "timeframe_end": "2026-08-16T00:00:00Z",
                                "metrics": [
                                    {
                                        "metric_name": "compute_unit_seconds",
                                        "value": compute_unit_seconds,
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
        "pagination": {},
    }


def _successful_opener(*, seconds=7200):
    requests = []

    def open_request(request, timeout):
        requests.append((request, timeout))
        if "/consumption_history/" in request.full_url:
            return _Response(_history_payload(compute_unit_seconds=seconds))
        return _Response(_project_payload())

    return open_request, requests


def _create_admin(app, client):
    app.config["CRYOCHECK_ADMIN_USERNAME"] = "AdminUser"
    with app.app_context():
        user = User(username="AdminUser", username_normalized="adminuser")
        user.set_password(VALID_PASSWORD)
        create_default_user_settings(user)
        db.session.add(user)
        db.session.commit()
    return client.post(
        "/login",
        data={"username": "AdminUser", "password": VALID_PASSWORD},
    )


def test_missing_configuration_returns_quiet_setup_state():
    result = fetch_neon_efficiency("", "")

    assert result.state == "setup"
    assert "NEON_API_KEY and NEON_PROJECT_ID" in result.message
    assert result.configuration_status is None


def test_testing_configuration_never_inherits_neon_credentials(app):
    assert app.config["NEON_API_KEY"] == ""
    assert app.config["NEON_PROJECT_ID"] == ""


def test_successful_project_and_consumption_metrics_are_exact():
    opener, requests = _successful_opener(seconds=9000)
    result = fetch_neon_efficiency(
        API_KEY_MARKER,
        PROJECT_ID,
        now=datetime(2026, 8, 16, tzinfo=timezone.utc),
        opener=opener,
    )

    assert result.state == "available"
    assert result.history_state == "available"
    assert result.min_cu == Decimal("0.25")
    assert result.max_cu == Decimal("2")
    assert result.suspend_timeout == "5 minutes"
    assert result.last_compute_activity == "2026-08-15 14:30 UTC"
    assert result.consumption_period == (
        "2026-08-01 00:00 UTC – 2026-09-01 00:00 UTC"
    )
    assert result.consumption_plan == "launch"
    assert result.cu_hours_month_to_date == Decimal("2.5")
    assert result.projected_cu_hours == Decimal(31) / Decimal(6)
    assert result.configuration_status == "Good"
    assert len(requests) == 2
    assert all(timeout == 5 for _request, timeout in requests)
    assert requests[0][0].get_header("Authorization") == (
        f"Bearer {API_KEY_MARKER}"
    )
    assert "metrics=compute_unit_seconds" in requests[1][0].full_url
    assert "project_ids=winter-project-12345678" in requests[1][0].full_url


def test_compute_unit_seconds_are_not_replaced_with_runtime_estimates():
    opener, _requests = _successful_opener(seconds=1)

    result = fetch_neon_efficiency(
        API_KEY_MARKER,
        PROJECT_ID,
        now=datetime(2026, 8, 16, tzinfo=timezone.utc),
        opener=opener,
    )

    assert result.cu_hours_month_to_date == Decimal(1) / Decimal(3600)


def test_unsupported_consumption_endpoint_keeps_project_sanity_metrics():
    def opener(request, timeout):
        del timeout
        if "/consumption_history/" in request.full_url:
            raise HTTPError(request.full_url, 403, "Forbidden", None, None)
        return _Response(_project_payload())

    result = fetch_neon_efficiency(
        API_KEY_MARKER,
        PROJECT_ID,
        opener=opener,
    )

    assert result.state == "available"
    assert result.history_state == "unsupported"
    assert result.cu_hours_month_to_date is None
    assert result.configuration_status == "Good"
    assert result.message == "CU-hour history unavailable for this Neon plan."


def test_api_failure_uses_sanitized_graceful_fallback():
    def failing_opener(request, timeout):
        del request, timeout
        raise URLError(f"credential={API_KEY_MARKER}")

    result = fetch_neon_efficiency(
        API_KEY_MARKER,
        PROJECT_ID,
        opener=failing_opener,
    )

    assert result.state == "unavailable"
    assert result.message == "Neon efficiency data is temporarily unavailable."
    assert API_KEY_MARKER not in result.message


def test_good_and_review_configuration_statuses_explain_the_reason():
    good = configuration_status(Decimal("0.25"), 300)
    high_minimum = configuration_status(Decimal("0.5"), 300)
    no_suspend = configuration_status(Decimal("0.25"), -1)

    assert good[0] == "Good"
    assert "scale-to-zero is enabled" in good[1].lower()
    assert high_minimum == (
        "Review",
        "Minimum compute is 0.5 CU; Neon's minimum practical setting is 0.25 CU.",
    )
    assert no_suspend == (
        "Review",
        "Scale-to-zero is disabled, so idle compute stays active.",
    )


def test_admin_page_renders_metrics_without_rendering_credential(
    app,
    client,
    monkeypatch,
):
    _create_admin(app, client)
    app.config["NEON_API_KEY"] = API_KEY_MARKER
    app.config["NEON_PROJECT_ID"] = PROJECT_ID

    def fake_fetch(api_key, project_id):
        assert api_key == API_KEY_MARKER
        assert project_id == PROJECT_ID
        return NeonEfficiency(
            state="available",
            message="Neon project configuration loaded.",
            min_cu=Decimal("0.25"),
            max_cu=Decimal("2"),
            suspend_timeout="5 minutes",
            last_compute_activity="2026-08-15 14:30 UTC",
            consumption_period=(
                "2026-08-01 00:00 UTC – 2026-09-01 00:00 UTC"
            ),
            consumption_plan="launch",
            cu_hours_month_to_date=Decimal("2.5"),
            projected_cu_hours=Decimal("5.1666666667"),
            history_state="available",
            configuration_status="Good",
            configuration_reason=(
                "Scale-to-zero is enabled and minimum compute is set to "
                "Neon's 0.25 CU minimum."
            ),
        )

    monkeypatch.setattr("app.routes.fetch_neon_efficiency", fake_fetch)
    response = client.get("/admin/usage")

    assert response.status_code == 200
    assert b"Database Efficiency" in response.data
    assert b"CU-hours this month" in response.data
    assert b"Projected month-end" in response.data
    assert b"Configuration status" in response.data
    assert b"Good" in response.data
    assert API_KEY_MARKER.encode() not in response.data


def test_admin_page_handles_missing_neon_setup_without_network(app, client):
    _create_admin(app, client)
    app.config["NEON_API_KEY"] = ""
    app.config["NEON_PROJECT_ID"] = ""

    response = client.get("/admin/usage")

    assert response.status_code == 200
    assert b'data-neon-state="setup"' in response.data
    assert b"NEON_API_KEY and NEON_PROJECT_ID" in response.data
