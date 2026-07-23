"""Synthetic, offline coverage for the CryoCheck CSV import workflow."""

from __future__ import annotations

import csv
import io

import pytest
from sqlalchemy import event
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import User
from app.services.csv_import import EXPECTED_COLUMNS, parse_csv_upload
from app.services.settings import create_default_user_settings


VALID_PASSWORD = "SyntheticPassphrase-42"


def _synthetic_csv(
    *,
    columns: tuple[str, ...] = EXPECTED_COLUMNS,
    row_count: int = 1,
    overrides: dict[int, dict[str, str]] | None = None,
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()

    for index in range(row_count):
        row = {column: "" for column in columns}
        baseline_values = {
            "RecordID": f"record-{index:03d}",
            "ApplicationNumber": f"application-{index:03d}",
            "GatewayCode": "SYNTHETIC-GATEWAY",
            "ApplicationDate": f"2026-01-{index + 1:02d}",
            "StartTime": "08:00",
            "DateCreated": f"2026-01-{index + 1:02d} 08:00",
            "AircraftType": "A320",
            "TailNumber": f"N{index:05d}",
            "TruckNumber": "TRUCK-TEST",
            "Operator": "Synthetic Operator",
            "Driver": "Synthetic Driver",
            "AmbientTemp": "1",
            "Type1Used": "10",
            "Type1Concentration": "50",
            "FreezingPoint1": "-17.3",
            "Type4Used": "0",
            "Type4ABrix": "",
        }
        row.update(
            {
                column: value
                for column, value in baseline_values.items()
                if column in row
            }
        )
        if overrides and index in overrides:
            row.update(
                {
                    column: value
                    for column, value in overrides[index].items()
                    if column in row
                }
            )
        writer.writerow(row)

    return output.getvalue().encode("utf-8")


def _upload(client, payload: bytes, filename: str = "synthetic-deice.csv"):
    return client.post(
        "/import",
        data={"csv_file": (io.BytesIO(payload), filename)},
        content_type="multipart/form-data",
    )


def test_valid_baseline_csv_imports_successfully(client):
    payload = _synthetic_csv(
        row_count=2,
        overrides={
            0: {
                "GatewayCode": "GATEWAY-A",
                "ApplicationDate": "2026-01-02",
                "DateCreated": "2026-01-02 08:00",
            },
            1: {
                "GatewayCode": "GATEWAY-B",
                "ApplicationDate": "2026-01-05",
                "DateCreated": "2026-01-05 08:00",
            },
        },
    )

    response = _upload(client, payload)

    assert response.status_code == 200
    assert b"Audit Results" in response.data
    assert b"No exceptions found" in response.data
    assert b"synthetic-deice.csv" in response.data
    assert b"GATEWAY-A" in response.data
    assert b"GATEWAY-B" in response.data
    assert b"2026-01-02" in response.data
    assert b"2026-01-05" in response.data


def test_complete_source_dataset_is_available_unchanged_after_parsing():
    columns = (*EXPECTED_COLUMNS, "Original Extra")
    payload = _synthetic_csv(
        columns=columns,
        row_count=12,
        overrides={
            11: {
                "RecordID": " final-record ",
                "Operator": "Mixed CASE value",
                "Original Extra": "=SOURCE-VALUE",
            }
        },
    )

    result = parse_csv_upload(
        FileStorage(
            stream=io.BytesIO(payload),
            filename="complete-source.csv",
        )
    )

    assert result.column_names == columns
    assert len(result.rows) == 12
    assert result.rows[11].source_row_number == 13
    assert result.rows[11].get("RecordID") == " final-record "
    assert result.rows[11].get("Operator") == "Mixed CASE value"
    assert result.rows[11].get("Original Extra") == "=SOURCE-VALUE"


def test_expected_columns_may_arrive_in_a_different_order(client):
    reversed_columns = tuple(reversed(EXPECTED_COLUMNS))

    response = _upload(
        client,
        _synthetic_csv(columns=reversed_columns),
    )

    assert response.status_code == 200
    assert b"Audit Results" in response.data


def test_missing_expected_column_rejects_file(client):
    columns = tuple(column for column in EXPECTED_COLUMNS if column != "Notes")

    response = _upload(client, _synthetic_csv(columns=columns))

    assert response.status_code == 400
    assert b"Missing required columns" in response.data
    assert b"Notes" in response.data


def test_unexpected_additional_column_is_allowed_and_reported(client):
    columns = (*EXPECTED_COLUMNS, "SyntheticExtraColumn")

    response = _upload(client, _synthetic_csv(columns=columns))

    assert response.status_code == 200
    assert b"Unexpected columns" in response.data
    assert b"SyntheticExtraColumn" in response.data


def test_empty_csv_rejects_cleanly(client):
    response = _upload(client, b"")

    assert response.status_code == 400
    assert b"selected CSV file is empty" in response.data


def test_header_only_csv_rejects_cleanly(client):
    header_only = (",".join(EXPECTED_COLUMNS) + "\n").encode("utf-8")

    response = _upload(client, header_only)

    assert response.status_code == 400
    assert b"header but no data rows" in response.data


def test_malformed_csv_rejects_cleanly(client):
    malformed = (
        ",".join(EXPECTED_COLUMNS)
        + "\n"
        + "record-001,application-001,too-few-fields\n"
    ).encode("utf-8")

    response = _upload(client, malformed)

    assert response.status_code == 400
    assert b"different number of fields" in response.data
    assert b"Traceback" not in response.data


def test_duplicate_column_names_reject_cleanly(client):
    duplicate_columns = (*EXPECTED_COLUMNS, "Notes")
    payload = _synthetic_csv(columns=duplicate_columns)

    response = _upload(client, payload)

    assert response.status_code == 400
    assert b"duplicate column names" in response.data
    assert b"Notes" in response.data


def test_undecodable_csv_rejects_cleanly(client):
    response = _upload(client, b"\xff\xfe\x00\x80")

    assert response.status_code == 400
    assert b"could not be decoded" in response.data


def test_non_csv_extension_rejects_cleanly(client):
    response = _upload(client, _synthetic_csv(), filename="synthetic-deice.txt")

    assert response.status_code == 400
    assert b".csv extension" in response.data
    assert b"synthetic-deice.txt" in response.data


def test_uploaded_filename_is_sanitized_for_display(client):
    response = _upload(
        client,
        _synthetic_csv(),
        filename="../../unsafe deice log.csv",
    )

    assert response.status_code == 200
    assert b"unsafe_deice_log.csv" in response.data
    assert b"../" not in response.data


def test_multiple_files_reject_cleanly(client):
    response = client.post(
        "/import",
        data={
            "csv_file": [
                (io.BytesIO(_synthetic_csv()), "first.csv"),
                (io.BytesIO(_synthetic_csv()), "second.csv"),
            ]
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert b"one CSV file at a time" in response.data


def test_oversized_upload_returns_branded_413(app, client):
    app.config["MAX_CONTENT_LENGTH"] = 512
    app.config["MAX_UPLOAD_MB"] = 1

    response = _upload(client, b"x" * 2048, filename="oversized.csv")

    assert response.status_code == 413
    assert b"CryoCheck" in response.data
    assert b"CSV file is too large" in response.data
    assert b"Import Another CSV" in response.data


def test_preview_is_limited_to_first_10_rows(client):
    response = _upload(client, _synthetic_csv(row_count=12))

    assert response.status_code == 200
    assert b"record-009" in response.data
    assert b"record-010" not in response.data
    assert b"record-011" not in response.data
    assert b"First 10 data rows" in response.data


def test_source_csv_row_numbering_starts_at_two(client):
    response = _upload(client, _synthetic_csv())

    assert response.status_code == 200
    assert b'<td class="preview-table__row">\n                    2\n' in response.data


def test_source_csv_row_numbering_accounts_for_blank_lines(client):
    payload = _synthetic_csv().replace(b"\n", b"\n\n", 1)

    response = _upload(client, payload)

    assert response.status_code == 200
    assert b'<td class="preview-table__row">\n                    3\n' in response.data


def test_uploaded_markup_is_escaped_and_formula_text_is_not_evaluated(client):
    payload = _synthetic_csv(
        overrides={
            0: {
                "Operator": '<script>alert("unsafe")</script>',
                "Driver": "=1+1",
            }
        }
    )

    response = _upload(client, payload)

    assert response.status_code == 200
    assert b"&lt;script&gt;alert" in response.data
    assert b'<script>alert("unsafe")</script>' not in response.data
    assert b"=1+1" in response.data


def test_rule_exception_is_rendered_on_results_screen(client):
    response = _upload(
        client,
        _synthetic_csv(
            overrides={0: {"DateCreated": "2026-01-01 07:59"}}
        ),
    )

    assert response.status_code == 200
    assert b"Audit Results" in response.data
    assert b"CC-RULE-001" in response.data
    assert b"Application entry proceeds event." in response.data
    assert b"CSV row <strong>2</strong>" in response.data
    assert b"1 minute" in response.data


def test_rule_003_exception_is_rendered_on_results_screen(client):
    response = _upload(
        client,
        _synthetic_csv(
            overrides={
                0: {
                    "Type1Concentration": "65",
                    "FreezingPoint1": "-20",
                    "AmbientTemp": "-32",
                }
            }
        ),
    )

    assert response.status_code == 200
    assert b"CC-RULE-003" in response.data
    assert b"Incorrect freeze point." in response.data
    assert b"Cryotech Polar Plus LT" in response.data
    assert b"Expected -50.0" in response.data
    assert b"CC-RULE-004" not in response.data


def test_rule_004_exception_is_rendered_on_results_screen(client):
    response = _upload(
        client,
        _synthetic_csv(
            overrides={
                0: {
                    "Type1Concentration": "65",
                    "FreezingPoint1": "-50.0",
                    "AmbientTemp": "-33",
                }
            }
        ),
    )

    assert response.status_code == 200
    assert b"CC-RULE-003" not in response.data
    assert b"CC-RULE-004" in response.data
    assert b"18 degree buffer not met." in response.data
    assert b"17.0" in response.data
    assert b"1.0" in response.data


def test_rule_003_and_rule_004_render_together_in_rule_order(client):
    response = _upload(
        client,
        _synthetic_csv(
            overrides={
                0: {
                    "Type1Concentration": "65",
                    "FreezingPoint1": "-20",
                    "AmbientTemp": "-33",
                }
            }
        ),
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert page.index("CC-RULE-003") < page.index("CC-RULE-004")
    assert page.count("Incorrect freeze point.") == 1
    assert page.count("18 degree buffer not met.") == 1


def test_exact_18_degree_buffer_does_not_render_rule_004(client):
    response = _upload(
        client,
        _synthetic_csv(
            overrides={
                0: {
                    "Type1Concentration": "65",
                    "FreezingPoint1": "-50.0",
                    "AmbientTemp": "-32",
                }
            }
        ),
    )

    assert response.status_code == 200
    assert b"CC-RULE-004" not in response.data
    assert b"No exceptions found" in response.data


@pytest.mark.parametrize("type4_brix", ("34.6", "36.6"))
def test_rule_005_inclusive_boundaries_pass_on_results_screen(
    client,
    type4_brix,
):
    response = _upload(
        client,
        _synthetic_csv(
            overrides={
                0: {
                    "Type4Used": "1",
                    "Type4ABrix": type4_brix,
                }
            }
        ),
    )

    assert response.status_code == 200
    assert b"CC-RULE-005" not in response.data
    assert b"No exceptions found" in response.data


@pytest.mark.parametrize(
    ("type4_brix", "direction", "amount"),
    (
        ("33.9", b"Below range", b"0.7"),
        ("37.1", b"Above range", b"0.5"),
    ),
)
def test_rule_005_exception_is_rendered_on_results_screen(
    client,
    type4_brix,
    direction,
    amount,
):
    response = _upload(
        client,
        _synthetic_csv(
            overrides={
                0: {
                    "Type4Used": "1",
                    "Type4ABrix": type4_brix,
                }
            }
        ),
    )

    assert response.status_code == 200
    assert b"CC-RULE-005" in response.data
    assert b"BRIX out of range." in response.data
    assert b"Cryotech Polar Guard Xtend" in response.data
    assert b"34.6\xe2\x80\x9336.6" in response.data
    assert direction in response.data
    assert amount in response.data


def test_rule_005_no_type4_use_skips_without_warning(client):
    response = _upload(
        client,
        _synthetic_csv(
            overrides={
                0: {
                    "Type4Used": "0",
                    "Type4ABrix": "malformed",
                }
            }
        ),
    )

    assert response.status_code == 200
    assert b"CC-RULE-005" not in response.data
    assert b"Some rule evaluations could not run" not in response.data
    assert b"No exceptions found" in response.data


def test_invalid_timestamp_warning_is_separate_from_exceptions(client):
    response = _upload(
        client,
        _synthetic_csv(overrides={0: {"DateCreated": "invalid"}}),
    )

    assert response.status_code == 200
    assert b"Some rule evaluations could not run" in response.data
    assert b"2 rule" in response.data
    assert b"not included in the exception count" in response.data
    assert b"No exceptions found" in response.data


def test_personal_48_hour_threshold_overrides_anonymous_default(app, client):
    payload = _synthetic_csv(
        overrides={0: {"DateCreated": "2026-01-02 08:00"}}
    )

    anonymous_response = _upload(client, payload)

    assert anonymous_response.status_code == 200
    assert b"CC-RULE-002" in anonymous_response.data
    assert b"Late entry." in anonymous_response.data
    assert b"Default" in anonymous_response.data

    with app.app_context():
        user = User(
            username="AuditUser",
            username_normalized="audituser",
        )
        user.set_password(VALID_PASSWORD)
        settings = create_default_user_settings(user)
        settings.late_entry_threshold_hours = 48
        db.session.add(user)
        db.session.commit()

    login_response = client.post(
        "/login",
        data={
            "username": "AuditUser",
            "password": VALID_PASSWORD,
        },
    )
    personal_response = _upload(client, payload)

    assert login_response.status_code == 302
    assert personal_response.status_code == 200
    assert b"Personal \xe2\x80\x94 AuditUser" in personal_response.data
    assert b"No exceptions found" in personal_response.data
    assert b"Late entry." not in personal_response.data


def test_signed_in_audit_uses_personal_type4_fluid_selection(app, client):
    payload = _synthetic_csv(
        overrides={
            0: {
                "Type4Used": "1",
                "Type4ABrix": "33.9",
            }
        }
    )

    anonymous_response = _upload(client, payload)

    assert anonymous_response.status_code == 200
    assert b"Default" in anonymous_response.data
    assert b"CC-RULE-005" in anonymous_response.data

    with app.app_context():
        user = User(
            username="Type4AuditUser",
            username_normalized="type4audituser",
        )
        user.set_password(VALID_PASSWORD)
        create_default_user_settings(user)
        db.session.add(user)
        db.session.commit()

    login_response = client.post(
        "/login",
        data={
            "username": "Type4AuditUser",
            "password": VALID_PASSWORD,
        },
    )
    personal_response = _upload(client, payload)

    assert login_response.status_code == 302
    assert personal_response.status_code == 200
    assert b"Personal \xe2\x80\x94 Type4AuditUser" in personal_response.data
    assert b"CC-RULE-005" in personal_response.data
    assert b"Cryotech Polar Guard Xtend" in personal_response.data


def test_successful_import_performs_no_database_operations(app, client):
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
            response = _upload(client, _synthetic_csv())
        finally:
            event.remove(engine, "before_cursor_execute", record_statement)

    assert response.status_code == 200
    assert executed_statements == []
