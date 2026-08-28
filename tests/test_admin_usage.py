"""Focused admin authorization and lightweight usage tracking coverage."""

from __future__ import annotations

import csv
import io
import re
from datetime import timedelta
from html import unescape

from sqlalchemy import inspect

from app.extensions import db
from app.models import UsageTotals, User, utc_now
from app.services.csv_import import EXPECTED_COLUMNS
from app.services.settings import create_default_user_settings


VALID_PASSWORD = "SyntheticPassphrase-42"


def _create_user(username: str, **values) -> User:
    user = User(
        username=username,
        username_normalized=username.strip().lower(),
        **values,
    )
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


def _audit_csv(*, marker: str = "Synthetic Operator", exception: bool = False):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=EXPECTED_COLUMNS,
        lineterminator="\n",
    )
    writer.writeheader()
    row = {column: "" for column in EXPECTED_COLUMNS}
    row.update(
        {
            "RecordID": "usage-record",
            "ApplicationNumber": "usage-application",
            "GatewayCode": "USAGE-GATEWAY",
            "ApplicationDate": "2026-08-27",
            "StartTime": "08:00",
            "EndTime": "08:30",
            "DateCreated": (
                "2026-08-27 07:59" if exception else "2026-08-27 08:00"
            ),
            "AircraftType": "2",
            "TailNumber": "AB-123",
            "TruckNumber": "1",
            "Operator": marker,
            "Driver": "Synthetic Driver",
            "AmbientTemp": "1",
            "Type1Used": "10",
            "Type1Concentration": "50",
            "FreezingPoint1": "-17.3",
            "EndTime1": "08:10",
            "ProcessTime1": "1",
            "Type4Used": "0",
            "Type4AConcentration": "100",
            "StartTime4": "08:15",
            "ProcessTime4": "1",
            "Notes": "Type I applied by truck 2",
        }
    )
    writer.writerow(row)
    return output.getvalue().encode("utf-8")


def _upload(client, *, marker: str = "Synthetic Operator", exception=False):
    return client.post(
        "/import",
        data={
            "csv_file": (
                io.BytesIO(_audit_csv(marker=marker, exception=exception)),
                f"{marker}.csv",
            )
        },
        content_type="multipart/form-data",
    )


def _export_token(response) -> str:
    match = re.search(
        r'name="export_token" value="([^"]+)"',
        response.get_data(as_text=True),
    )
    assert match is not None
    return unescape(match.group(1))


def _summary_card(page: str, name: str) -> str:
    match = re.search(
        rf'<article class="usage-summary__card" data-summary="{name}">(.*?)</article>',
        page,
        flags=re.DOTALL,
    )
    assert match is not None
    return " ".join(re.sub(r"<[^>]+>", " ", match.group(1)).split())


def test_admin_env_matching_uses_normalized_authenticated_username(app, client):
    app.config["CRYOCHECK_ADMIN_USERNAME"] = "  KESSLER  "
    with app.app_context():
        _create_user("Kessler")

    assert _login(client, "kessler").status_code == 302
    response = client.get("/admin/usage")

    assert response.status_code == 200
    assert b"Usage Dashboard" in response.data
    assert b'href="/admin/usage"' in response.data
    assert b"KESSLER" not in response.data


def test_missing_admin_env_grants_nobody_access(app, client):
    app.config["CRYOCHECK_ADMIN_USERNAME"] = "   "
    with app.app_context():
        _create_user("Kessler")
    _login(client, "Kessler")

    assert client.get("/admin/usage").status_code == 403
    assert b'href="/admin/usage"' not in client.get("/").data


def test_non_admin_is_denied_without_exposing_admin_identity(app, client):
    app.config["CRYOCHECK_ADMIN_USERNAME"] = "private-admin-name"
    with app.app_context():
        _create_user("RegularUser")
    _login(client, "RegularUser")

    response = client.get("/admin/usage")

    assert response.status_code == 403
    assert b"private-admin-name" not in response.data
    assert b'href="/admin/usage"' not in client.get("/").data


def test_signed_in_validation_and_completed_export_update_one_account(app, client):
    with app.app_context():
        user_id = _create_user("TrackedUser").id
    _login(client, "TrackedUser")

    results = _upload(client, exception=True)

    assert results.status_code == 200
    token = _export_token(results)
    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.validation_count == 1
        assert user.last_validation_at is not None
        assert user.export_count == 0
        assert user.last_export_at is None

    preflight = client.post(
        "/export",
        data={"export_token": token, "scope": "all", "delivery": "validate"},
    )
    assert preflight.status_code == 200
    with app.app_context():
        assert db.session.get(User, user_id).export_count == 0

    export = client.post(
        "/export",
        data={"export_token": token, "scope": "all"},
    )

    assert export.status_code == 200
    assert export.mimetype == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.export_count == 1
        assert user.last_export_at is not None


def test_anonymous_validations_use_only_the_single_aggregate(app, client):
    assert _upload(client).status_code == 200
    assert _upload(client).status_code == 200

    with app.app_context():
        assert User.query.count() == 0
        totals = db.session.get(UsageTotals, 1)
        assert totals is not None
        assert totals.anonymous_validation_count == 2


def test_dashboard_totals_and_account_table_use_metadata_only(app, client):
    now = utc_now()
    app.config["CRYOCHECK_ADMIN_USERNAME"] = "AdminUser"
    with app.app_context():
        _create_user(
            "AdminUser",
            created_at=now - timedelta(days=40),
            validation_count=2,
            export_count=1,
        )
        _create_user(
            "RecentUser",
            created_at=now - timedelta(days=5),
            last_validation_at=now - timedelta(days=2),
            validation_count=3,
            export_count=2,
        )
        _create_user(
            "MonthlyUser",
            created_at=now - timedelta(days=20),
            last_export_at=now - timedelta(days=10),
            validation_count=6,
            export_count=2,
        )
        db.session.add(UsageTotals(id=1, anonymous_validation_count=7))
        db.session.commit()

    _login(client, "AdminUser")
    response = client.get("/admin/usage")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert _summary_card(page, "total-accounts") == "Total accounts 3"
    assert _summary_card(page, "accounts-created") == (
        "Accounts created 1 7 days 2 30 days"
    )
    assert _summary_card(page, "active-accounts") == (
        "Active accounts 2 7 days 3 30 days"
    )
    assert _summary_card(page, "signed-in-validations") == (
        "Signed-in validations 11"
    )
    assert _summary_card(page, "anonymous-validations") == (
        "Anonymous validations 7"
    )
    assert _summary_card(page, "exports") == "Exports 5"
    assert page.index("AdminUser") < page.index("MonthlyUser") < page.index(
        "RecentUser"
    )


def test_audit_payload_and_filename_are_never_persisted(app, client):
    private_marker = "PRIVATE-AUDIT-PAYLOAD-93A7"

    response = _upload(client, marker=private_marker)

    assert response.status_code == 200
    with app.app_context():
        assert set(inspect(db.engine).get_table_names()) == {
            "usage_totals",
            "user_settings",
            "users",
        }
        totals = db.session.get(UsageTotals, 1)
        assert private_marker not in repr(totals.__dict__)


def test_new_account_usage_fields_default_to_zero(app):
    with app.app_context():
        user = _create_user("DefaultCounters")

        assert user.validation_count == 0
        assert user.last_validation_at is None
        assert user.export_count == 0
        assert user.last_export_at is None
