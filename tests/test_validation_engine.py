"""Focused boundary coverage for the first executable CryoCheck rules."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from app.services.csv_import import CSVImportResult, CSVSourceRow
from app.services.settings import DEFAULT_SETTINGS
from app.services.validation_engine import run_audit


def _source_row(
    *,
    source_row_number: int = 2,
    application_date: str = "2026-01-15",
    start_time: str = "08:00",
    date_created: str = "2026-01-15 08:00",
    date_created_utc: str = "",
    last_modified_utc: str = "",
    record_id: str = "record-001",
) -> CSVSourceRow:
    values = {
        "RecordID": record_id,
        "ApplicationNumber": "application-001",
        "GatewayCode": "GATEWAY-A",
        "AircraftType": "A320",
        "TailNumber": "N12345",
        "ApplicationDate": application_date,
        "StartTime": start_time,
        "DateCreated": date_created,
        "TruckNumber": "TRUCK-1",
        "Operator": "Test Operator",
        "Driver": "Test Driver",
        "DateCreatedUTC": date_created_utc,
        "LastModifiedUTC": last_modified_utc,
    }
    return CSVSourceRow(
        source_row_number=source_row_number,
        fields=tuple(values.items()),
    )


def _import_result(*rows: CSVSourceRow) -> CSVImportResult:
    column_names = tuple(name for name, _value in rows[0].fields)
    return CSVImportResult(
        filename="synthetic-audit.csv",
        row_count=len(rows),
        column_count=len(column_names),
        column_names=column_names,
        rows=tuple(rows),
        expected_columns_found=(),
        missing_columns=(),
        unexpected_columns=(),
        gateway_codes=("GATEWAY-A",),
        earliest_application_date="2026-01-15",
        latest_application_date="2026-01-15",
        preview_records=(),
    )


def _audit_one(**row_values):
    return run_audit(
        _import_result(_source_row(**row_values)),
        DEFAULT_SETTINGS,
    )


def test_rule_001_entry_one_minute_before_event_fails():
    result = _audit_one(date_created="2026-01-15 07:59")

    assert result.exception_count == 1
    exception = result.exceptions[0]
    assert exception.rule_id == "CC-RULE-001"
    assert exception.rule_name == "Application Entry Proceeds Event"
    assert exception.exception_message == "Application entry proceeds event."
    assert exception.source_row_number == 2
    assert exception.application_date == "2026-01-15"
    assert exception.start_time == "08:00"
    assert exception.date_created == "2026-01-15 07:59"
    assert exception.details[-1].value == "1 minute"


def test_rule_001_entry_equal_to_event_passes():
    result = _audit_one(date_created="2026-01-15 08:00")

    assert result.exception_count == 0


def test_rule_001_entry_after_event_passes():
    result = _audit_one(date_created="2026-01-15 08:01")

    assert result.exception_count == 0


def test_utc_fields_do_not_influence_rule_001_or_rule_002():
    result = _audit_one(
        date_created="2026-01-15 08:00",
        date_created_utc="2026-01-10 01:00",
        last_modified_utc="2030-12-31 23:59",
    )

    assert result.exception_count == 0
    assert result.unable_to_evaluate_count == 0


def test_rule_002_23_hours_59_minutes_passes_at_24_hours():
    result = _audit_one(date_created="2026-01-16 07:59")

    assert result.exception_count == 0


def test_rule_002_exactly_24_hours_fails_at_24_hours():
    result = _audit_one(date_created="2026-01-16 08:00")

    assert result.exception_count == 1
    exception = result.exceptions[0]
    assert exception.rule_id == "CC-RULE-002"
    assert exception.exception_message == "Late entry."
    assert tuple((detail.label, detail.value) for detail in exception.details) == (
        ("Application date/time", "2026-01-15 08:00"),
        ("Entry date/time", "2026-01-16 08:00"),
        ("Configured threshold", "24 hours"),
        ("Actual delay", "1 day"),
        ("Amount beyond the threshold", "0 minutes"),
    )


def test_rule_002_more_than_24_hours_fails():
    result = _audit_one(date_created="2026-01-16 09:01")

    assert result.exception_count == 1
    assert result.exceptions[0].rule_id == "CC-RULE-002"
    assert result.exceptions[0].details[-1].value == "1 hour, 1 minute"


def test_rule_002_47_hours_59_minutes_passes_at_48_hours():
    settings = replace(DEFAULT_SETTINGS, late_entry_threshold_hours=48)

    result = run_audit(
        _import_result(_source_row(date_created="2026-01-17 07:59")),
        settings,
    )

    assert result.exception_count == 0


def test_rule_002_exactly_48_hours_fails_at_48_hours():
    settings = replace(DEFAULT_SETTINGS, late_entry_threshold_hours=48)

    result = run_audit(
        _import_result(_source_row(date_created="2026-01-17 08:00")),
        settings,
    )

    assert result.exception_count == 1
    assert result.exceptions[0].rule_id == "CC-RULE-002"
    assert result.exceptions[0].details[2].value == "48 hours"
    assert result.exceptions[0].details[3].value == "2 days"


def test_exceptions_are_ordered_by_source_row_then_rule_id():
    result = run_audit(
        _import_result(
            _source_row(
                source_row_number=9,
                date_created="2026-01-16 08:00",
                record_id="record-009",
            ),
            _source_row(
                source_row_number=3,
                date_created="2026-01-15 07:59",
                record_id="record-003",
            ),
        ),
        DEFAULT_SETTINGS,
    )

    assert tuple(
        (exception.source_row_number, exception.rule_id)
        for exception in result.exceptions
    ) == (
        (3, "CC-RULE-001"),
        (9, "CC-RULE-002"),
    )


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    (
        ("application_date", ""),
        ("application_date", "not-a-date"),
        ("start_time", ""),
        ("start_time", "8:00 AM"),
        ("date_created", ""),
        ("date_created", "2026-01-15T08:00:00Z"),
    ),
)
def test_invalid_required_timestamps_are_non_exception_warnings(
    field_name,
    field_value,
):
    result = _audit_one(**{field_name: field_value})

    assert result.exception_count == 0
    assert result.unable_to_evaluate_count == 2
    assert result.unable_to_evaluate_row_count == 1
    assert tuple(
        warning.rule_id for warning in result.unable_to_evaluate
    ) == ("CC-RULE-001", "CC-RULE-002")
    assert all(
        warning.source_row_number == 2
        for warning in result.unable_to_evaluate
    )


def test_audit_result_and_exception_structures_are_immutable():
    result = _audit_one(date_created="2026-01-15 07:59")

    with pytest.raises(FrozenInstanceError):
        result.filename = "changed.csv"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.exceptions[0].rule_id = "changed"  # type: ignore[misc]
