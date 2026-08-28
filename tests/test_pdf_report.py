"""Focused PDF Results report and export-chooser coverage."""

from __future__ import annotations

import csv
import io
import re
from html import unescape
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import event

from app import create_app
from app.extensions import db
from app.models import UsageTotals
from app.services.csv_import import EXPECTED_COLUMNS
from app.services.pdf_report import load_pdf_report


def _results_csv(*rows: dict[str, str]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(*EXPECTED_COLUMNS, "RetainedAuditColumn"),
        lineterminator="\n",
    )
    writer.writeheader()
    for index, overrides in enumerate(rows):
        row = {column: "" for column in EXPECTED_COLUMNS}
        row.update(
            {
                "RecordID": f"pdf-record-{index + 1}",
                "ApplicationNumber": f"PDF-APP-{index + 1}",
                "GatewayCode": "PDF-GATEWAY",
                "ApplicationDate": "2026-01-15",
                "StartTime": "08:00",
                "EndTime": "08:30",
                "DateCreated": "2026-01-15 07:59",
                "AircraftType": "2",
                "TailNumber": "AB-123",
                "TruckNumber": "1",
                "AmbientTemp": "1",
                "Type1Used": "10",
                "Type1Concentration": "malformed",
                "ProcessTime1": "1",
                "Notes": "Type I applied by truck 2",
                "RetainedAuditColumn": "review-note",
            }
        )
        row.update(overrides)
        writer.writerow(row)
    return output.getvalue().encode("utf-8")


def _upload_results(client, *rows: dict[str, str]):
    return client.post(
        "/import",
        data={
            "csv_file": (
                io.BytesIO(_results_csv(*rows)),
                "pdf-report-source.csv",
            )
        },
        content_type="multipart/form-data",
    )


def _pdf_token(response) -> str:
    match = re.search(
        r'name="pdf_report_token" value="([^"]+)"',
        response.get_data(as_text=True),
    )
    assert match is not None
    return unescape(match.group(1))


def _pdf_text(response) -> str:
    reader = PdfReader(io.BytesIO(response.data))
    return "\n".join(page.extract_text() for page in reader.pages)


def test_pdf_route_exports_complete_readable_current_results(client):
    results = _upload_results(
        client,
        {},
        {"ApplicationNumber": "PDF-APP-SECOND", "DateCreated": "2026-01-15 07:58"},
    )

    response = client.post(
        "/export/pdf",
        data={"pdf_report_token": _pdf_token(results)},
    )
    text = _pdf_text(response)
    uppercase_text = text.upper()

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-")
    assert "CryoCheck_Audit_Results_" in response.headers["Content-Disposition"]
    assert "Audit Results" in text
    assert "pdf-report-source.csv" in text
    assert "SETTINGS PROFILE" in uppercase_text
    assert "ROWS AUDITED" in uppercase_text
    assert "TOTAL EXCEPTIONS" in uppercase_text
    assert "Application entry proceeds event." in text
    assert "PDF-APP-1" in text
    assert "PDF-APP-SECOND" in text
    assert "ENTRY DATE" in uppercase_text
    assert "ENTERED EARLY BY" in uppercase_text
    assert "RETAINEDAUDITCOLUMN" in uppercase_text


def test_pdf_includes_warnings_but_excludes_interactive_controls(client):
    results = _upload_results(client, {})
    response = client.post(
        "/export/pdf",
        data={"pdf_report_token": _pdf_token(results)},
    )
    text = _pdf_text(response)

    assert "Unable to Evaluate" in text
    assert "Type1Concentration" in text
    assert "pdf-record-1" in text
    assert "Select All" not in text
    assert "Clear All" not in text
    assert "Export Selected" not in text
    assert "Export All" not in text
    assert "navigation" not in text.lower()


def test_pdf_snapshot_uses_concise_results_fields_and_failure_roles(app, client):
    results = _upload_results(client, {})
    with client.session_transaction() as browser_session:
        context_id = browser_session["export_context_id"]
    snapshot = load_pdf_report(
        _pdf_token(results),
        secret_key=app.config["SECRET_KEY"],
        max_age_seconds=app.config["EXPORT_TOKEN_MAX_AGE_SECONDS"],
        expected_context_id=context_id,
    )

    assert snapshot.rows_audited == 1
    assert snapshot.exception_count >= 1
    exception = snapshot.exceptions[0]
    assert exception.entry_date_invalid is True
    assert [detail.label for detail in exception.details] == [
        "Application Date/Time",
        "Entered Early By",
    ]
    assert all(detail.invalid is False for detail in exception.details)
    assert snapshot.warning_count >= 1


def test_pdf_request_is_csrf_and_current_result_scoped(client):
    first = _upload_results(client, {})
    first_token = _pdf_token(first)
    second = _upload_results(client, {"ApplicationNumber": "NEW-REPORT"})

    stale = client.post(
        "/export/pdf",
        data={"pdf_report_token": first_token},
    )
    malformed = client.post(
        "/export/pdf",
        data={"pdf_report_token": f"{_pdf_token(second)}tampered"},
    )

    assert stale.status_code == 400
    assert b"no longer the current audit result" in stale.data
    assert malformed.status_code == 400
    assert b"PDF request is invalid" in malformed.data


def test_production_pdf_route_requires_csrf():
    production_app = create_app("production")
    client = production_app.test_client()

    response = client.post(
        "/export/pdf",
        base_url="https://localhost",
        data={"pdf_report_token": "not-reached"},
    )

    assert response.status_code == 400
    assert b"Security check failed" in response.data


def test_pdf_generation_persists_only_the_existing_usage_counter(app, client):
    results = _upload_results(client, {})
    statements: list[str] = []

    def record_statement(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        del connection, cursor, parameters, context, executemany
        statements.append(statement)

    with app.app_context():
        event.listen(db.engine, "before_cursor_execute", record_statement)
        try:
            response = client.post(
                "/export/pdf",
                data={"pdf_report_token": _pdf_token(results)},
            )
        finally:
            event.remove(db.engine, "before_cursor_execute", record_statement)

    mutations = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith(
            ("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")
        )
    ]
    assert response.status_code == 200
    assert len(mutations) == 1
    assert "usage_totals" in mutations[0]
    with app.app_context():
        totals = db.session.get(UsageTotals, 1)
        assert totals is not None
        assert totals.anonymous_export_count == 1


def test_export_results_chooser_has_approved_pdf_and_excel_copy(client):
    page = _upload_results(client, {}).get_data(as_text=True)

    assert 'id="export-results-dialog"' in page
    assert "Export Results" in page
    assert "PDF Report" in page
    assert "Readable Audit Results" in page
    assert (
        "Export this Audit Results page as a clean report for review,\n"
        "                printing, or sharing."
    ) in page
    assert "Excel Exception Data" in page
    assert "Filtered Log Data" in page
    assert "Export exception rows and full technical audit details for" in page
    assert "Export Selected" in page
    assert "Export All" in page
    assert 'action="/export/pdf"' in page
    assert 'action="/export"' in page


def test_export_chooser_mobile_layout_is_compact_and_overflow_safe():
    stylesheet = Path("app/static/css/app.css").read_text(encoding="utf-8")
    script = Path("app/static/js/exception-export.js").read_text(
        encoding="utf-8"
    )

    assert ".export-results-dialog" in stylesheet
    assert "max-height: calc(100dvh - 1rem);" in stylesheet
    assert "env(safe-area-inset-bottom)" in stylesheet
    assert ".mobile-export-bar--chooser" in stylesheet
    assert 'document.querySelectorAll("[data-export-dialog-open]")' in script
    assert 'exportDialog.showModal()' in script
