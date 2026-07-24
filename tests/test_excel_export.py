"""Excel exception export, selection, security, and persistence coverage."""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from html import unescape

from openpyxl import load_workbook
from sqlalchemy import event
from werkzeug.datastructures import MultiDict

from app import create_app
from app.extensions import db
from app.services.csv_import import EXPECTED_COLUMNS
from app.services.excel_export import (
    build_exception_workbook,
    load_export_snapshot,
    prepare_export,
    select_export_rows,
)
from app.services.validation_engine import (
    AuditException,
    AuditResult,
    RuleDetail,
    UnableToEvaluate,
)


_EXPECTED_FIXED_HEADERS = (
    "CSV source row",
    "Rule ID",
    "Rule name",
    "Exception message",
    "Active settings profile",
    "RecordID",
    "ApplicationNumber",
    "Gateway",
    "AircraftType",
    "TailNumber",
    "ApplicationDate",
    "StartTime",
    "DateCreated",
    "TruckNumber",
    "Operator",
    "Driver",
)


def _synthetic_export_csv(
    *rows: dict[str, str],
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=EXPECTED_COLUMNS,
        lineterminator="\n",
    )
    writer.writeheader()

    for index, overrides in enumerate(rows):
        row = {column: "" for column in EXPECTED_COLUMNS}
        row.update(
            {
                "RecordID": f"export-record-{index}",
                "ApplicationNumber": f"export-application-{index}",
                "GatewayCode": "EXPORT-GATEWAY",
                "ApplicationDate": "2026-01-15",
                "StartTime": "08:00",
                "EndTime": "08:30",
                "DateCreated": "2026-01-15 08:00",
                "AircraftType": "2",
                "TailNumber": "AB-123",
                "TruckNumber": "1",
                "Operator": "Export Operator",
                "Driver": "Export Driver",
                "AmbientTemp": "1",
                "Type1Used": "",
                "Type4Used": "",
                "Notes": "Type I applied by truck 2",
            }
        )
        row.update(overrides)
        writer.writerow(row)

    return output.getvalue().encode("utf-8")


def _upload_for_export(client, *rows: dict[str, str]):
    return client.post(
        "/import",
        data={
            "csv_file": (
                io.BytesIO(_synthetic_export_csv(*rows)),
                "export-source.csv",
            )
        },
        content_type="multipart/form-data",
    )


def _export_form(response) -> tuple[str, tuple[str, ...]]:
    html = response.get_data(as_text=True)
    token_match = re.search(
        r'name="export_token" value="([^"]+)"',
        html,
    )
    assert token_match is not None
    identifiers = tuple(
        re.findall(r'name="exception_id"\s+value="([^"]+)"', html)
    )
    return unescape(token_match.group(1)), identifiers


def _workbook_from_response(response):
    return load_workbook(io.BytesIO(response.data))


def _header_positions(worksheet) -> dict[str, int]:
    return {
        cell.value: index
        for index, cell in enumerate(worksheet[1], start=1)
    }


def _audit_exception(
    *,
    source_row_number: int = 2,
    rule_id: str = "CC-RULE-001",
    rule_name: str = "Application Entry Proceeds Event",
    exception_message: str = "Application entry proceeds event.",
    record_id: str = "record-001",
    application_number: str = "application-001",
    gateway_code: str = "GATEWAY-A",
    aircraft_type: str = "2",
    tail_number: str = "AB-123",
    application_date: str = "2026-01-15",
    start_time: str = "08:00",
    date_created: str = "2026-01-15 07:59",
    truck_number: str = "1",
    operator: str = "Operator",
    driver: str = "Driver",
    details: tuple[RuleDetail, ...] = (
        RuleDetail("Timing difference", "1 minute"),
    ),
) -> AuditException:
    return AuditException(
        rule_id=rule_id,
        rule_name=rule_name,
        exception_message=exception_message,
        source_row_number=source_row_number,
        record_id=record_id,
        application_number=application_number,
        gateway_code=gateway_code,
        aircraft_type=aircraft_type,
        tail_number=tail_number,
        application_date=application_date,
        start_time=start_time,
        date_created=date_created,
        truck_number=truck_number,
        operator=operator,
        driver=driver,
        details=details,
    )


def _audit_result(
    *exceptions: AuditException,
    warnings: tuple[UnableToEvaluate, ...] = (),
) -> AuditResult:
    return AuditResult(
        filename="request-only.csv",
        rows_audited=2,
        rules_executed=14,
        active_settings_profile_name="Default",
        exceptions=exceptions,
        unable_to_evaluate=warnings,
    )


def test_results_show_one_checkbox_per_exception_and_export_controls(client):
    response = _upload_for_export(
        client,
        {
            "DateCreated": "2026-01-15 07:59",
            "TailNumber": "N121UP",
        },
    )

    assert response.status_code == 200
    assert response.data.count(b'data-exception-checkbox') == 2
    assert b"Select All" in response.data
    assert b"Clear All" in response.data
    assert b"Export Selected" in response.data
    assert b"Export Exceptions" in response.data
    assert re.search(
        rb'<button[^>]+form="exception-export-form"[^>]+'
        rb'value="all"[^>]+data-export-all',
        response.data,
    )
    assert re.search(
        rb'value="selected"\s+disabled\s+data-export-selected',
        response.data,
    )
    token, identifiers = _export_form(response)
    assert token
    assert identifiers == ("exception-1", "exception-2")


def test_export_navigation_is_hidden_when_audit_has_no_exceptions(client):
    response = _upload_for_export(client, {})

    assert response.status_code == 200
    assert b"No exceptions found" in response.data
    assert b"Export Exceptions" not in response.data
    assert b"data-export-all" not in response.data


def test_export_all_downloads_every_exception_in_audit_order(client):
    results = _upload_for_export(
        client,
        {
            "DateCreated": "2026-01-15 07:59",
            "TailNumber": "N121UP",
        },
        {
            "DateCreated": "2026-01-15 07:58",
        },
    )
    token, identifiers = _export_form(results)

    response = client.post(
        "/export",
        data=MultiDict(
            (
                ("export_token", token),
                ("scope", "all"),
                *(("exception_id", identifier) for identifier in identifiers),
            )
        ),
    )

    assert response.status_code == 200
    assert response.mimetype == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert re.search(
        r'attachment; filename=CryoCheck_Exceptions_\d{8}_\d{6}\.xlsx',
        response.headers["Content-Disposition"],
    )
    assert response.headers["Cache-Control"] == "no-store"
    workbook = _workbook_from_response(response)
    worksheet = workbook["Exceptions"]
    headers = _header_positions(worksheet)
    exported_order = tuple(
        (
            worksheet.cell(row=row, column=headers["CSV source row"]).value,
            worksheet.cell(row=row, column=headers["Rule ID"]).value,
        )
        for row in range(2, worksheet.max_row + 1)
    )

    assert exported_order == (
        (2, "CC-RULE-001"),
        (2, "CC-RULE-012"),
        (3, "CC-RULE-001"),
    )
    workbook.close()


def test_export_selected_ignores_submission_order_and_keeps_audit_order(client):
    results = _upload_for_export(
        client,
        {
            "DateCreated": "2026-01-15 07:59",
            "TailNumber": "N121UP",
        },
        {
            "DateCreated": "2026-01-15 07:58",
        },
    )
    token, identifiers = _export_form(results)

    response = client.post(
        "/export",
        data=MultiDict(
            (
                ("export_token", token),
                ("scope", "selected"),
                ("exception_id", identifiers[2]),
                ("exception_id", identifiers[0]),
            )
        ),
    )
    workbook = _workbook_from_response(response)
    worksheet = workbook["Exceptions"]
    headers = _header_positions(worksheet)

    assert response.status_code == 200
    assert tuple(
        (
            worksheet.cell(row=row, column=headers["CSV source row"]).value,
            worksheet.cell(row=row, column=headers["Rule ID"]).value,
        )
        for row in range(2, worksheet.max_row + 1)
    ) == ((2, "CC-RULE-001"), (3, "CC-RULE-001"))
    workbook.close()


def test_export_selected_requires_at_least_one_selection(client):
    results = _upload_for_export(
        client,
        {"DateCreated": "2026-01-15 07:59"},
    )
    token, _identifiers = _export_form(results)

    response = client.post(
        "/export",
        data={"export_token": token, "scope": "selected"},
    )

    assert response.status_code == 400
    assert b"The exception export could not be created" in response.data
    assert b"Select at least one exception" in response.data


def test_export_rejects_unknown_and_duplicate_identifiers(client):
    results = _upload_for_export(
        client,
        {"DateCreated": "2026-01-15 07:59"},
    )
    token, identifiers = _export_form(results)

    unknown = client.post(
        "/export",
        data={
            "export_token": token,
            "scope": "selected",
            "exception_id": "exception-999",
        },
    )
    duplicate = client.post(
        "/export",
        data=MultiDict(
            (
                ("export_token", token),
                ("scope", "selected"),
                ("exception_id", identifiers[0]),
                ("exception_id", identifiers[0]),
            )
        ),
    )

    assert unknown.status_code == 400
    assert b"not part of this audit result" in unknown.data
    assert duplicate.status_code == 400
    assert b"duplicate exception selections" in duplicate.data


def test_export_rejects_malformed_and_expired_snapshots(app, client):
    results = _upload_for_export(
        client,
        {"DateCreated": "2026-01-15 07:59"},
    )
    token, identifiers = _export_form(results)

    malformed = client.post(
        "/export",
        data={
            "export_token": f"{token}tampered",
            "scope": "all",
        },
    )
    app.config["EXPORT_TOKEN_MAX_AGE_SECONDS"] = -1
    expired = client.post(
        "/export",
        data={
            "export_token": token,
            "scope": "selected",
            "exception_id": identifiers[0],
        },
    )

    assert malformed.status_code == 400
    assert b"export request is invalid" in malformed.data
    assert expired.status_code == 400
    assert b"export request expired" in expired.data


def test_new_import_invalidates_an_older_results_export(client):
    older_results = _upload_for_export(
        client,
        {"DateCreated": "2026-01-15 07:59"},
    )
    older_token, _older_identifiers = _export_form(older_results)
    newer_results = _upload_for_export(
        client,
        {"TailNumber": "N121UP"},
    )
    newer_token, _newer_identifiers = _export_form(newer_results)

    stale = client.post(
        "/export",
        data={"export_token": older_token, "scope": "all"},
    )
    current = client.post(
        "/export",
        data={"export_token": newer_token, "scope": "all"},
    )

    assert stale.status_code == 400
    assert b"no longer the current audit result" in stale.data
    assert current.status_code == 200


def test_export_workbook_has_required_headers_values_and_formatting():
    audit = _audit_result(
        _audit_exception(
            details=(
                RuleDetail("Timing difference", "1 minute"),
                RuleDetail("Comparison", "Entry preceded event."),
            )
        )
    )
    prepared = prepare_export(
        audit,
        secret_key="export-test-secret",
        context_id="export-test-context",
    )
    snapshot = load_export_snapshot(
        prepared.token,
        secret_key="export-test-secret",
        max_age_seconds=60,
        expected_context_id="export-test-context",
    )
    selected = select_export_rows(
        snapshot,
        scope="all",
        selected_identifiers=(),
    )
    stream, filename = build_exception_workbook(
        selected,
        now=datetime(2026, 7, 23, 12, 34, 56, tzinfo=timezone.utc),
    )
    workbook = load_workbook(stream)
    worksheet = workbook["Exceptions"]
    headers = tuple(cell.value for cell in worksheet[1])
    positions = _header_positions(worksheet)

    assert filename == "CryoCheck_Exceptions_20260723_123456.xlsx"
    assert headers[: len(_EXPECTED_FIXED_HEADERS)] == _EXPECTED_FIXED_HEADERS
    assert "Detail — Timing difference" in headers
    assert "Detail — Comparison" in headers
    assert headers[-1] == "Combined details"
    assert worksheet.freeze_panes == "A2"
    assert worksheet.auto_filter.ref == worksheet.dimensions
    assert all(cell.font.bold for cell in worksheet[1])
    assert all(cell.alignment.wrap_text for cell in worksheet[1])
    assert worksheet["A2"].value == 2
    assert worksheet.cell(
        row=2,
        column=positions["Active settings profile"],
    ).value == "Default"
    assert worksheet.cell(
        row=2,
        column=positions["Detail — Timing difference"],
    ).value == "1 minute"
    assert worksheet.cell(
        row=2,
        column=positions["Combined details"],
    ).value == (
        "Timing difference: 1 minute; Comparison: Entry preceded event."
    )
    assert worksheet.column_dimensions["A"].width >= 12
    workbook.close()


def test_export_escapes_formula_like_text_in_source_and_detail_fields():
    audit = _audit_result(
        _audit_exception(
            record_id="=SUM(A1:A2)",
            application_number="+1",
            gateway_code="-2",
            tail_number="@command",
            details=(
                RuleDetail("Entered value", "=HYPERLINK(\"bad\")"),
                RuleDetail("Negative text", "-1"),
            ),
        )
    )
    prepared = prepare_export(
        audit,
        secret_key="formula-test-secret",
        context_id="formula-test-context",
    )
    snapshot = load_export_snapshot(
        prepared.token,
        secret_key="formula-test-secret",
        max_age_seconds=60,
        expected_context_id="formula-test-context",
    )
    stream, _filename = build_exception_workbook(
        snapshot.rows,
        now=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )
    workbook = load_workbook(stream, data_only=False)
    worksheet = workbook["Exceptions"]
    positions = _header_positions(worksheet)

    assert worksheet.cell(row=2, column=positions["RecordID"]).value == (
        "'=SUM(A1:A2)"
    )
    assert worksheet.cell(
        row=2,
        column=positions["ApplicationNumber"],
    ).value == "'+1"
    assert worksheet.cell(row=2, column=positions["Gateway"]).value == "'-2"
    assert worksheet.cell(row=2, column=positions["TailNumber"]).value == (
        "'@command"
    )
    assert worksheet.cell(
        row=2,
        column=positions["Detail — Entered value"],
    ).value == "'=HYPERLINK(\"bad\")"
    assert worksheet.cell(
        row=2,
        column=positions["Detail — Negative text"],
    ).value == "'-1"
    assert all(
        cell.data_type != "f"
        for row in worksheet.iter_rows(min_row=2)
        for cell in row
    )
    workbook.close()


def test_unable_to_evaluate_warnings_are_excluded_from_export(client):
    results = _upload_for_export(
        client,
        {
            "DateCreated": "malformed",
            "TailNumber": "N121UP",
        },
    )

    assert b"Some rule evaluations could not run" in results.data
    token, _identifiers = _export_form(results)
    response = client.post(
        "/export",
        data={"export_token": token, "scope": "all"},
    )
    workbook = _workbook_from_response(response)
    worksheet = workbook["Exceptions"]
    positions = _header_positions(worksheet)

    assert response.status_code == 200
    assert worksheet.max_row == 2
    assert worksheet.cell(row=2, column=positions["Rule ID"]).value == (
        "CC-RULE-012"
    )
    assert "unable" not in " ".join(
        str(cell.value or "")
        for row in worksheet.iter_rows()
        for cell in row
    ).lower()
    workbook.close()


def test_export_request_performs_no_database_operations(app, client):
    results = _upload_for_export(
        client,
        {"DateCreated": "2026-01-15 07:59"},
    )
    token, _identifiers = _export_form(results)
    executed_statements: list[str] = []

    def record_statement(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        del connection, cursor, parameters, context, executemany
        executed_statements.append(statement)

    with app.app_context():
        engine = db.engine
        event.listen(engine, "before_cursor_execute", record_statement)
        try:
            response = client.post(
                "/export",
                data={"export_token": token, "scope": "all"},
            )
        finally:
            event.remove(engine, "before_cursor_execute", record_statement)

    assert response.status_code == 200
    assert executed_statements == []


def test_production_export_route_requires_csrf():
    production_app = create_app("production")
    client = production_app.test_client()

    response = client.post(
        "/export",
        base_url="https://localhost",
        data={"export_token": "not-reached", "scope": "all"},
    )

    assert response.status_code == 400
    assert b"Security check failed" in response.data
