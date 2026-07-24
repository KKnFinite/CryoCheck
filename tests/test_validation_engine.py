"""Focused boundary coverage for the executable CryoCheck rules."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services import validation_engine
from app.services.csv_import import CSVImportResult, CSVSourceRow
from app.services.settings import DEFAULT_SETTINGS
from app.services.type4_fluids import TypeIVFluidProfile
from app.services.validation_engine import run_audit


def _source_row(
    *,
    source_row_number: int = 2,
    aircraft_type: str = "2",
    tail_number: str = "N12345",
    notes: str = "Type I applied by truck 2",
    truck_number: str = "1",
    application_date: str = "2026-01-15",
    start_time: str = "08:00",
    end_time: str = "08:30",
    date_created: str = "2026-01-15 08:00",
    date_created_utc: str = "",
    last_modified_utc: str = "",
    record_id: str = "record-001",
    precipitation: str = "",
    type1_used: str = "",
    type1_concentration: str = "",
    freezing_point1: str = "",
    end_time1: str = "08:10",
    ambient_temp: str = "",
    process_time1: str = "1",
    type4_used: str = "",
    type4_brix: str = "",
    type4_concentration: str = "100",
    start_time4: str = "08:15",
    process_time4: str = "1",
) -> CSVSourceRow:
    values = {
        "RecordID": record_id,
        "ApplicationNumber": "application-001",
        "GatewayCode": "GATEWAY-A",
        "AircraftType": aircraft_type,
        "TailNumber": tail_number,
        "Notes": notes,
        "ApplicationDate": application_date,
        "StartTime": start_time,
        "EndTime": end_time,
        "DateCreated": date_created,
        "TruckNumber": truck_number,
        "Operator": "Test Operator",
        "Driver": "Test Driver",
        "DateCreatedUTC": date_created_utc,
        "LastModifiedUTC": last_modified_utc,
        "Precipitation": precipitation,
        "Type1Used": type1_used,
        "Type1Concentration": type1_concentration,
        "FreezingPoint1": freezing_point1,
        "EndTime1": end_time1,
        "AmbientTemp": ambient_temp,
        "ProcessTime1": process_time1,
        "Type4Used": type4_used,
        "Type4ABrix": type4_brix,
        "Type4AConcentration": type4_concentration,
        "StartTime4": start_time4,
        "ProcessTime4": process_time4,
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


def _audit_gap(
    *,
    settings=DEFAULT_SETTINGS,
    **row_values,
):
    values = {
        "type1_used": "10",
        "type1_concentration": "50",
        "freezing_point1": "-17.3",
        "ambient_temp": "1",
        "type4_used": "10",
        "type4_brix": "35",
        "end_time1": "08:10",
        "start_time4": "08:15",
    }
    values.update(row_values)
    return run_audit(
        _import_result(_source_row(**values)),
        settings,
    )


def _audit_type1_rate(
    *,
    settings=DEFAULT_SETTINGS,
    **row_values,
):
    values = {
        "type1_used": "120",
        "type1_concentration": "50",
        "freezing_point1": "-17.3",
        "ambient_temp": "1",
        "process_time1": "1",
    }
    values.update(row_values)
    return run_audit(
        _import_result(_source_row(**values)),
        settings,
    )


def _audit_type4_rate(
    *,
    settings=DEFAULT_SETTINGS,
    **row_values,
):
    values = {
        "type4_used": "60",
        "type4_brix": "35",
        "process_time4": "1",
    }
    values.update(row_values)
    return run_audit(
        _import_result(_source_row(**values)),
        settings,
    )


def _audit_type4_concentration(
    *,
    settings=DEFAULT_SETTINGS,
    **row_values,
):
    values = {
        "type4_used": "1",
        "type4_brix": "35",
        "type4_concentration": "100",
        "process_time4": "1",
    }
    values.update(row_values)
    return run_audit(
        _import_result(_source_row(**values)),
        settings,
    )


def _audit_tail_number(**row_values):
    return run_audit(
        _import_result(_source_row(**row_values)),
        DEFAULT_SETTINGS,
    )


def _audit_overlap(**row_values):
    values = {
        "type1_used": "1",
        "type1_concentration": "50",
        "freezing_point1": "-17.3",
        "ambient_temp": "1",
        "process_time1": "1",
        "type4_used": "1",
        "type4_brix": "35",
        "type4_concentration": "100",
        "process_time4": "1",
        "end_time1": "08:10",
        "start_time4": "08:15",
    }
    values.update(row_values)
    return run_audit(
        _import_result(_source_row(**values)),
        DEFAULT_SETTINGS,
    )


def _audit_type4_explanation(**row_values):
    values = {
        "aircraft_type": "2",
        "tail_number": "N12345",
        "notes": "Type I applied by truck 2",
        "truck_number": "1",
        "type1_used": "",
        "type4_used": "1",
        "type4_brix": "35",
        "type4_concentration": "100",
        "process_time4": "1",
    }
    values.update(row_values)
    return run_audit(
        _import_result(_source_row(**values)),
        DEFAULT_SETTINGS,
    )


def _audit_event_time(
    *,
    settings=DEFAULT_SETTINGS,
    **row_values,
):
    values = {
        "type1_used": "1",
        "type1_concentration": "50",
        "freezing_point1": "-17.3",
        "ambient_temp": "1",
        "process_time1": "30",
        "type4_used": "",
        "type4_brix": "35",
        "process_time4": "",
    }
    values.update(row_values)
    return run_audit(
        _import_result(_source_row(**values)),
        settings,
    )


def _settings_without(field_name: str) -> SimpleNamespace:
    return SimpleNamespace(
        **{
            field.name: getattr(DEFAULT_SETTINGS, field.name)
            for field in fields(DEFAULT_SETTINGS)
            if field.name != field_name
        }
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


def test_audit_reports_fourteen_rules_executed():
    result = _audit_one()

    assert result.rules_executed == 14


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


def test_rule_003_correct_decimal_freeze_point_passes():
    result = _audit_one(
        type1_used="1",
        type1_concentration="60",
        freezing_point1="-39.2",
        ambient_temp="-21",
    )

    assert result.exception_count == 0
    assert result.unable_to_evaluate_count == 0


def test_rule_003_incorrect_freeze_point_fails_with_required_details():
    result = _audit_one(
        type1_used="1",
        type1_concentration="60",
        freezing_point1="-37.0",
        ambient_temp="-21",
    )

    assert result.exception_count == 1
    exception = result.exceptions[0]
    assert exception.rule_id == "CC-RULE-003"
    assert exception.rule_name == "Incorrect Freeze Point"
    assert exception.exception_message == "Incorrect freeze point."
    assert tuple(
        (detail.label, detail.value) for detail in exception.details
    ) == (
        ("Selected Type I fluid", "Cryotech Polar Plus LT"),
        ("Recorded concentration", "60%"),
        ("Entered freeze point", "-37.0°F"),
        ("Expected manufacturer-chart freeze point", "-39.2°F"),
        (
            "Comparison",
            "Expected -39.2°F at 60% concentration. Entered -37.0°F.",
        ),
    )


def test_rule_003_does_not_round_an_incorrect_value_into_a_match():
    result = _audit_one(
        type1_used="1",
        type1_concentration="60",
        freezing_point1="-39.19",
        ambient_temp="-21",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-003",)


def test_rule_003_numeric_freeze_point_forms_are_equivalent():
    result = _audit_one(
        type1_used="1",
        type1_concentration="65",
        freezing_point1="-50",
        ambient_temp="-32",
    )

    assert result.exception_count == 0
    assert result.unable_to_evaluate_count == 0


@pytest.mark.parametrize("concentration", ("60", "60.0"))
def test_rule_003_whole_concentration_forms_select_same_row(concentration):
    result = _audit_one(
        type1_used="1",
        type1_concentration=concentration,
        freezing_point1="-39.2",
        ambient_temp="-21",
    )

    assert result.exception_count == 0
    assert result.unable_to_evaluate_count == 0


@pytest.mark.parametrize("concentration", ("60.5", "71", "-1"))
def test_unsupported_concentration_is_unable_to_evaluate(concentration):
    result = _audit_one(
        type1_used="1",
        type1_concentration=concentration,
        freezing_point1="-39.2",
        ambient_temp="-21",
    )

    assert result.exception_count == 0
    assert tuple(
        warning.rule_id for warning in result.unable_to_evaluate
    ) == ("CC-RULE-003", "CC-RULE-004")
    assert all(
        warning.invalid_fields == ("Type1Concentration",)
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize("type1_used", ("", "0", "0.0", "-1"))
def test_blank_or_nonpositive_type1_used_skips_type1_rules(type1_used):
    result = _audit_one(
        type1_used=type1_used,
        type1_concentration="unsupported",
        freezing_point1="malformed",
        ambient_temp="malformed",
    )

    assert result.exception_count == 0
    assert result.unable_to_evaluate_count == 0


def test_malformed_type1_used_is_unable_to_evaluate():
    result = _audit_one(type1_used="malformed")

    assert result.exception_count == 0
    assert tuple(
        warning.rule_id for warning in result.unable_to_evaluate
    ) == (
        "CC-RULE-003",
        "CC-RULE-004",
        "CC-RULE-008",
        "CC-RULE-010",
        "CC-RULE-013",
    )
    assert all(
        warning.invalid_fields == ("Type1Used",)
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize("freezing_point", ("", "malformed", "NaN"))
def test_rule_003_missing_or_malformed_freeze_point_is_warning(
    freezing_point,
):
    result = _audit_one(
        type1_used="1",
        type1_concentration="60",
        freezing_point1=freezing_point,
        ambient_temp="-21",
    )

    assert result.exception_count == 0
    assert tuple(
        warning.rule_id for warning in result.unable_to_evaluate
    ) == ("CC-RULE-003",)
    assert result.unable_to_evaluate[0].invalid_fields == ("FreezingPoint1",)


def test_unknown_selected_type1_fluid_is_unable_to_evaluate():
    settings = replace(DEFAULT_SETTINGS, type1_fluid="Unknown Type I fluid")

    result = run_audit(
        _import_result(
            _source_row(
                type1_used="1",
                type1_concentration="60",
                freezing_point1="-39.2",
                ambient_temp="-21",
            )
        ),
        settings,
    )

    assert result.exception_count == 0
    assert tuple(
        warning.rule_id for warning in result.unable_to_evaluate
    ) == ("CC-RULE-003", "CC-RULE-004")


def test_rule_004_exact_18_degree_buffer_passes():
    result = _audit_one(
        type1_used="1",
        type1_concentration="65",
        freezing_point1="-50.0",
        ambient_temp="-32",
    )

    assert result.exception_count == 0
    assert result.unable_to_evaluate_count == 0


def test_rule_004_17_degree_buffer_fails_with_required_details():
    result = _audit_one(
        type1_used="1",
        type1_concentration="65",
        freezing_point1="-50.0",
        ambient_temp="-33",
    )

    assert result.exception_count == 1
    exception = result.exceptions[0]
    assert exception.rule_id == "CC-RULE-004"
    assert exception.rule_name == "18 Degree Buffer Not Met"
    assert exception.exception_message == "18 degree buffer not met."
    assert tuple(
        (detail.label, detail.value) for detail in exception.details
    ) == (
        ("Selected Type I fluid", "Cryotech Polar Plus LT"),
        ("Recorded concentration", "65%"),
        ("Outside air temperature", "-33°F"),
        ("Authoritative manufacturer-chart freeze point", "-50.0°F"),
        ("Actual calculated buffer", "17.0°F"),
        ("Required buffer", "18.0°F"),
        ("Amount short", "1.0°F"),
    )


def test_rule_004_decimal_buffer_below_18_fails():
    result = _audit_one(
        type1_used="1",
        type1_concentration="65",
        freezing_point1="-50.0",
        ambient_temp="-32.1",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-004",)
    assert result.exceptions[0].details[4].value == "17.9°F"
    assert result.exceptions[0].details[-1].value == "0.1°F"


@pytest.mark.parametrize("ambient_temp", ("", "malformed", "Infinity"))
def test_rule_004_missing_or_malformed_ambient_temperature_is_warning(
    ambient_temp,
):
    result = _audit_one(
        type1_used="1",
        type1_concentration="65",
        freezing_point1="-50.0",
        ambient_temp=ambient_temp,
    )

    assert result.exception_count == 0
    assert tuple(
        warning.rule_id for warning in result.unable_to_evaluate
    ) == ("CC-RULE-004",)
    assert result.unable_to_evaluate[0].invalid_fields == ("AmbientTemp",)


def test_wrong_entered_freeze_point_with_valid_chart_buffer_only_fails_003():
    result = _audit_one(
        type1_used="1",
        type1_concentration="65",
        freezing_point1="-20",
        ambient_temp="-32",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-003",)


def test_correct_entered_freeze_point_with_failed_chart_buffer_only_fails_004():
    result = _audit_one(
        type1_used="1",
        type1_concentration="65",
        freezing_point1="-50.0",
        ambient_temp="-33",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-004",)


def test_wrong_entered_freeze_point_and_failed_chart_buffer_fail_both_rules():
    result = _audit_one(
        type1_used="1",
        type1_concentration="65",
        freezing_point1="-10",
        ambient_temp="-33",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-003", "CC-RULE-004")


def test_rule_004_uses_chart_value_not_incorrect_entered_value():
    result = _audit_one(
        type1_used="1",
        type1_concentration="65",
        freezing_point1="-100",
        ambient_temp="-33",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-003", "CC-RULE-004")
    assert result.exceptions[1].details[3].value == "-50.0°F"


@pytest.mark.parametrize(
    "type4_brix",
    ("34.6", "36.6", "34.60", "36.600", "35", "35.0"),
)
def test_rule_005_inclusive_range_and_numeric_equivalence_pass(type4_brix):
    result = _audit_one(
        type4_used="1",
        type4_brix=type4_brix,
    )

    assert result.exception_count == 0
    assert result.unable_to_evaluate_count == 0


@pytest.mark.parametrize("type4_used", ("", "0", "0.0", "-1"))
def test_rule_005_nonpositive_or_blank_type4_used_skips(type4_used):
    result = _audit_one(
        type4_used=type4_used,
        type4_brix="malformed",
    )

    assert result.exception_count == 0
    assert result.unable_to_evaluate_count == 0


@pytest.mark.parametrize(
    ("entered_brix", "amount_below"),
    (("34.59", "0.01"), ("33.9", "0.7")),
)
def test_rule_005_below_range_fails_with_exact_amount(
    entered_brix,
    amount_below,
):
    result = _audit_one(
        type4_used="1",
        type4_brix=entered_brix,
    )

    assert result.exception_count == 1
    exception = result.exceptions[0]
    assert exception.rule_id == "CC-RULE-005"
    assert exception.rule_name == "BRIX Out of Range"
    assert exception.exception_message == "BRIX out of range."
    assert tuple(
        (detail.label, detail.value) for detail in exception.details
    ) == (
        ("Selected Type IV fluid", "Cryotech Polar Guard Xtend"),
        ("Entered BRIX", entered_brix),
        ("Acceptable inclusive range", "34.6–36.6"),
        ("Range comparison", "Below range"),
        ("Amount below nearest boundary", amount_below),
        (
            "Comparison",
            (
                f"Entered BRIX: {entered_brix}. Acceptable range for "
                "Cryotech Polar Guard Xtend: 34.6–36.6. "
                f"Below range by {amount_below}."
            ),
        ),
    )


@pytest.mark.parametrize(
    ("entered_brix", "amount_above"),
    (("36.61", "0.01"), ("37.1", "0.5")),
)
def test_rule_005_above_range_fails_with_exact_amount(
    entered_brix,
    amount_above,
):
    result = _audit_one(
        type4_used="1",
        type4_brix=entered_brix,
    )

    assert result.exception_count == 1
    exception = result.exceptions[0]
    assert exception.rule_id == "CC-RULE-005"
    assert tuple(
        (detail.label, detail.value) for detail in exception.details
    ) == (
        ("Selected Type IV fluid", "Cryotech Polar Guard Xtend"),
        ("Entered BRIX", entered_brix),
        ("Acceptable inclusive range", "34.6–36.6"),
        ("Range comparison", "Above range"),
        ("Amount above nearest boundary", amount_above),
        (
            "Comparison",
            (
                f"Entered BRIX: {entered_brix}. Acceptable range for "
                "Cryotech Polar Guard Xtend: 34.6–36.6. "
                f"Above range by {amount_above}."
            ),
        ),
    )


@pytest.mark.parametrize("type4_brix", ("", "malformed", "NaN", "Infinity"))
def test_rule_005_invalid_brix_is_unable_to_evaluate(type4_brix):
    result = _audit_one(
        type4_used="1",
        type4_brix=type4_brix,
    )

    assert result.exception_count == 0
    assert tuple(
        warning.rule_id for warning in result.unable_to_evaluate
    ) == ("CC-RULE-005",)
    assert result.unable_to_evaluate[0].invalid_fields == ("Type4ABrix",)


def test_rule_005_malformed_type4_used_is_unable_to_evaluate():
    result = _audit_one(
        type4_used="malformed",
        type4_brix="35",
    )

    assert result.exception_count == 0
    rule_warning = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-005"
    )
    assert len(rule_warning) == 1
    assert rule_warning[0].invalid_fields == ("Type4Used",)


def test_rule_005_unknown_selected_type4_fluid_is_unable_to_evaluate():
    settings = replace(
        DEFAULT_SETTINGS,
        type4_fluid="Unknown Type IV fluid",
    )

    result = run_audit(
        _import_result(
            _source_row(
                type4_used="1",
                type4_brix="35",
            )
        ),
        settings,
    )

    assert result.exception_count == 0
    assert tuple(
        warning.rule_id for warning in result.unable_to_evaluate
    ) == ("CC-RULE-005", "CC-RULE-011")
    assert result.unable_to_evaluate[0].invalid_fields == (
        "Type IV fluid setting",
    )
    assert result.unable_to_evaluate[1].invalid_fields == (
        "Type IV fluid setting",
    )


def test_rule_005_invalid_profile_range_is_unable_to_evaluate(monkeypatch):
    invalid_profile = TypeIVFluidProfile(
        name="Invalid Type IV fluid",
        minimum_brix=Decimal("36.6"),
        maximum_brix=Decimal("34.6"),
        required_concentration=Decimal("100"),
    )
    monkeypatch.setattr(
        validation_engine,
        "get_type4_fluid_profile",
        lambda _name: invalid_profile,
    )

    result = _audit_one(
        type4_used="1",
        type4_brix="35",
    )

    assert result.exception_count == 0
    assert tuple(
        warning.rule_id for warning in result.unable_to_evaluate
    ) == ("CC-RULE-005",)
    assert "valid BRIX range" in result.unable_to_evaluate[0].message


@pytest.mark.parametrize("type4_used", ("", "0", "0.0", "-1"))
def test_rule_011_blank_or_nonpositive_usage_skips(type4_used):
    result = _audit_type4_concentration(
        type4_used=type4_used,
        type4_concentration="malformed",
    )

    assert all(
        exception.rule_id != "CC-RULE-011"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-011"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize("type4_used", ("malformed", "NaN", "Infinity"))
def test_rule_011_malformed_or_nonfinite_usage_warns(type4_used):
    result = _audit_type4_concentration(type4_used=type4_used)
    rule_warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-011"
    )

    assert len(rule_warnings) == 1
    assert rule_warnings[0].invalid_fields == ("Type4Used",)
    assert all(
        exception.rule_id != "CC-RULE-011"
        for exception in result.exceptions
    )


@pytest.mark.parametrize(
    "type4_concentration",
    ("100", "100.0", "100.00", "100%", "100.0%", " 100 % "),
)
def test_rule_011_exact_required_concentration_formats_pass(
    type4_concentration,
):
    result = _audit_type4_concentration(
        type4_concentration=type4_concentration
    )

    assert all(
        exception.rule_id != "CC-RULE-011"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-011"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    "type4_concentration",
    ("99.9", "99.999", "50", "1", "1.0", "0", "100.001", "101"),
)
def test_rule_011_exact_concentration_mismatch_fails(type4_concentration):
    result = _audit_type4_concentration(
        type4_concentration=type4_concentration
    )
    rule_exceptions = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-011"
    )

    assert len(rule_exceptions) == 1
    assert rule_exceptions[0].exception_message == (
        "Incorrect Type IV concentration."
    )
    assert all(
        warning.rule_id != "CC-RULE-011"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    "type4_concentration",
    ("", "malformed", "NaN", "Infinity", "100%%", "100 percent"),
)
def test_rule_011_invalid_concentration_warns(type4_concentration):
    result = _audit_type4_concentration(
        type4_concentration=type4_concentration
    )
    rule_warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-011"
    )

    assert len(rule_warnings) == 1
    assert rule_warnings[0].invalid_fields == ("Type4AConcentration",)
    assert all(
        exception.rule_id != "CC-RULE-011"
        for exception in result.exceptions
    )


def test_rule_011_unknown_selected_fluid_warns():
    result = _audit_type4_concentration(
        settings=replace(
            DEFAULT_SETTINGS,
            type4_fluid="Unknown Type IV fluid",
        )
    )
    rule_warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-011"
    )

    assert len(rule_warnings) == 1
    assert rule_warnings[0].invalid_fields == ("Type IV fluid setting",)


@pytest.mark.parametrize(
    "invalid_requirement",
    (None, "100", Decimal("NaN"), Decimal("-0.1"), Decimal("100.1")),
)
def test_rule_011_invalid_runtime_profile_requirement_warns(
    monkeypatch,
    invalid_requirement,
):
    invalid_profile = SimpleNamespace(
        name="Invalid Type IV fluid",
        minimum_brix=Decimal("34.6"),
        maximum_brix=Decimal("36.6"),
        required_concentration=invalid_requirement,
    )
    monkeypatch.setattr(
        validation_engine,
        "get_type4_fluid_profile",
        lambda _name: invalid_profile,
    )

    result = _audit_type4_concentration()
    rule_warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-011"
    )

    assert len(rule_warnings) == 1
    assert rule_warnings[0].invalid_fields == ("Type IV fluid setting",)


def test_rule_011_exception_details_preserve_original_concentration():
    result = _audit_type4_concentration(
        type4_concentration=" 99.5 % "
    )
    exception = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-011"
    )[0]

    assert exception.rule_name == "Incorrect Type IV Concentration"
    assert exception.exception_message == "Incorrect Type IV concentration."
    assert tuple(
        (detail.label, detail.value)
        for detail in exception.details
    ) == (
        ("Selected Type IV fluid", "Cryotech Polar Guard Xtend"),
        ("Entered Type IV concentration", " 99.5 % "),
        ("Required Type IV concentration", "100%"),
        (
            "Comparison",
            (
                "Entered concentration 99.5 % does not match the required "
                "100%."
            ),
        ),
    )


def test_rule_011_uses_active_type4_fluid_profile(monkeypatch):
    personal_profile = TypeIVFluidProfile(
        name="Personal Type IV fluid",
        minimum_brix=Decimal("34"),
        maximum_brix=Decimal("36"),
        required_concentration=Decimal("75"),
    )
    monkeypatch.setattr(
        validation_engine,
        "get_type4_fluid_profile",
        lambda name: personal_profile
        if name == personal_profile.name
        else None,
    )
    settings = replace(
        DEFAULT_SETTINGS,
        name="Personal — ConcentrationUser",
        is_default=False,
        type4_fluid=personal_profile.name,
    )

    passing = _audit_type4_concentration(
        settings=settings,
        type4_brix="35",
        type4_concentration="75%",
    )
    failing = _audit_type4_concentration(
        settings=settings,
        type4_brix="35",
        type4_concentration="100",
    )
    exception = tuple(
        exception
        for exception in failing.exceptions
        if exception.rule_id == "CC-RULE-011"
    )[0]

    assert all(
        exception.rule_id != "CC-RULE-011"
        for exception in passing.exceptions
    )
    assert exception.details[0].value == personal_profile.name
    assert exception.details[2].value == "75%"


@pytest.mark.parametrize(
    ("type4_brix", "type4_concentration", "type4_used", "process_time4",
     "expected_rule_ids"),
    (
        ("33.9", "100", "10", "1", ("CC-RULE-005",)),
        ("35", "99.9", "10", "1", ("CC-RULE-011",)),
        ("35", "100", "61", "1", ("CC-RULE-009",)),
        (
            "33.9",
            "99.9",
            "61",
            "1",
            ("CC-RULE-005", "CC-RULE-009", "CC-RULE-011"),
        ),
    ),
)
def test_type4_brix_rate_and_concentration_rules_are_independent(
    type4_brix,
    type4_concentration,
    type4_used,
    process_time4,
    expected_rule_ids,
):
    result = _audit_type4_concentration(
        type4_brix=type4_brix,
        type4_concentration=type4_concentration,
        type4_used=type4_used,
        process_time4=process_time4,
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == expected_rule_ids


def test_malformed_brix_does_not_block_rule_011():
    result = _audit_type4_concentration(
        type4_brix="malformed",
        type4_concentration="99.9",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-011",)
    assert tuple(
        warning.rule_id for warning in result.unable_to_evaluate
    ) == ("CC-RULE-005",)


def test_malformed_process_time_does_not_block_rule_011():
    result = _audit_type4_concentration(
        type4_concentration="99.9",
        process_time4="malformed",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-011",)
    assert tuple(
        warning.rule_id for warning in result.unable_to_evaluate
    ) == ("CC-RULE-009", "CC-RULE-010")


def test_malformed_concentration_does_not_block_rules_005_or_009():
    result = _audit_type4_concentration(
        type4_brix="33.9",
        type4_concentration="malformed",
        type4_used="61",
        process_time4="1",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-005", "CC-RULE-009")
    assert tuple(
        warning.rule_id for warning in result.unable_to_evaluate
    ) == ("CC-RULE-011",)


@pytest.mark.parametrize(
    ("aircraft_type", "tail_number", "notes"),
    (
        ("0.0", "", "Equipment treatment"),
        ("1.0", "N121UP", ""),
        ("2.00", "AB-123", ""),
    ),
)
def test_rule_012_accepts_equivalent_whole_aircraft_types(
    aircraft_type,
    tail_number,
    notes,
):
    result = _audit_tail_number(
        aircraft_type=aircraft_type,
        tail_number=tail_number,
        notes=notes,
    )

    assert all(
        exception.rule_id != "CC-RULE-012"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-012"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    "aircraft_type",
    ("", "malformed", "NaN", "Infinity", "1.5", "-1", "3"),
)
def test_rule_012_invalid_aircraft_type_warns(aircraft_type):
    result = _audit_tail_number(aircraft_type=aircraft_type)
    rule_warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-012"
    )

    assert len(rule_warnings) == 1
    assert rule_warnings[0].invalid_fields == ("AircraftType",)
    assert all(
        exception.rule_id != "CC-RULE-012"
        for exception in result.exceptions
    )


@pytest.mark.parametrize(
    ("tail_number", "notes"),
    (("", "Equipment treatment"), ("   ", "  Ground equipment  ")),
)
def test_rule_012_aircraft_type_0_valid_non_aircraft_spray_passes(
    tail_number,
    notes,
):
    result = _audit_tail_number(
        aircraft_type="0",
        tail_number=tail_number,
        notes=notes,
    )

    assert all(
        finding.rule_id != "CC-RULE-012"
        for finding in result.exceptions
    )


@pytest.mark.parametrize(
    ("tail_number", "notes", "expected_reasons"),
    (
        ("", "", ("Notes are required for AircraftType 0",)),
        (
            "N121UP",
            "Equipment treatment",
            ("TailNumber must be blank for AircraftType 0",),
        ),
        (
            " N121UP ",
            "   ",
            (
                "TailNumber must be blank for AircraftType 0",
                "Notes are required for AircraftType 0",
            ),
        ),
    ),
)
def test_rule_012_aircraft_type_0_failures_are_specific(
    tail_number,
    notes,
    expected_reasons,
):
    result = _audit_tail_number(
        aircraft_type="0",
        tail_number=tail_number,
        notes=notes,
    )
    exception = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-012"
    )[0]

    assert exception.details[-1].label == "Failure reason"
    assert exception.details[-1].value == "; ".join(expected_reasons)


def test_rule_012_aircraft_type_0_ignores_fluid_usage():
    result = _audit_tail_number(
        aircraft_type="0",
        tail_number="",
        notes="Equipment treatment",
        type1_used="malformed",
        type4_used="Infinity",
    )

    assert all(
        exception.rule_id != "CC-RULE-012"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-012"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    "tail_number",
    ("N121UP", "n121up", "  N121UP  "),
)
def test_rule_012_aircraft_type_1_valid_ups_tails_pass(tail_number):
    result = _audit_tail_number(
        aircraft_type="1",
        tail_number=tail_number,
    )

    assert all(
        exception.rule_id != "CC-RULE-012"
        for exception in result.exceptions
    )


@pytest.mark.parametrize(
    "tail_number",
    ("", "N12UP", "N121XX", "N0123UP", "AB-123", "N12AUP"),
)
def test_rule_012_aircraft_type_1_invalid_tails_fail(tail_number):
    result = _audit_tail_number(
        aircraft_type="1",
        tail_number=tail_number,
    )
    exception = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-012"
    )[0]

    assert exception.details[-1].value == (
        "Does not match UPS NxxxUP format"
    )


@pytest.mark.parametrize(
    "tail_number",
    ("AB-123", "12345", "-A123-", "A--123", "abc-123"),
)
def test_rule_012_aircraft_type_2_valid_non_ups_tails_pass(tail_number):
    result = _audit_tail_number(
        aircraft_type="2",
        tail_number=tail_number,
    )

    assert all(
        exception.rule_id != "CC-RULE-012"
        for exception in result.exceptions
    )


@pytest.mark.parametrize(
    ("tail_number", "expected_reason"),
    (
        ("", "TailNumber must not be blank for AircraftType 2"),
        ("N121UP", "AircraftType 2 must not use UPS format"),
        ("n121up", "AircraftType 2 must not use UPS format"),
        ("---", "Does not contain a letter or number"),
        ("AB 123", "Contains unsupported characters"),
        ("AB_123", "Contains unsupported characters"),
        ("AB/123", "Contains unsupported characters"),
    ),
)
def test_rule_012_aircraft_type_2_invalid_tails_fail(
    tail_number,
    expected_reason,
):
    result = _audit_tail_number(
        aircraft_type="2",
        tail_number=tail_number,
    )
    exception = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-012"
    )[0]

    assert exception.details[-1].value == expected_reason


def test_rule_012_type_0_details_preserve_original_csv_values():
    result = _audit_tail_number(
        aircraft_type=" 0.0 ",
        tail_number=" N121UP ",
        notes="   ",
    )
    exception = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-012"
    )[0]

    assert exception.rule_name == "Incorrect Tail Number"
    assert exception.exception_message == "Incorrect tail number."
    assert tuple(
        (detail.label, detail.value)
        for detail in exception.details
    ) == (
        ("Original AircraftType", " 0.0 "),
        ("Original TailNumber", " N121UP "),
        ("Original Notes", "   "),
        (
            "Required format",
            (
                "AircraftType 0 requires a blank TailNumber and nonblank "
                "Notes."
            ),
        ),
        (
            "Failure reason",
            (
                "TailNumber must be blank for AircraftType 0; "
                "Notes are required for AircraftType 0"
            ),
        ),
    )


def test_rule_012_type_1_details_show_required_format():
    result = _audit_tail_number(
        aircraft_type="1",
        tail_number="AB-123",
    )
    exception = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-012"
    )[0]

    assert exception.details[2].value == (
        "UPS format ^N[0-9]{3}UP$ after trimming, compared "
        "case-insensitively."
    )


def test_rule_012_orders_by_csv_row_then_rule_id():
    result = run_audit(
        _import_result(
            _source_row(
                source_row_number=3,
                aircraft_type="1",
                tail_number="invalid",
            ),
            _source_row(
                source_row_number=2,
                aircraft_type="2",
                tail_number="N121UP",
            ),
        ),
        DEFAULT_SETTINGS,
    )

    assert tuple(
        (exception.source_row_number, exception.rule_id)
        for exception in result.exceptions
    ) == ((2, "CC-RULE-012"), (3, "CC-RULE-012"))


def test_rule_012_failure_does_not_trigger_nonapplicable_rule_014():
    result = _audit_tail_number(
        aircraft_type="2",
        tail_number="N121UP",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-012",)
    assert all(
        warning.rule_id != "CC-RULE-014"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    (
        ("type1_used", ""),
        ("type1_used", "0"),
        ("type1_used", "-1"),
        ("type4_used", ""),
        ("type4_used", "0"),
        ("type4_used", "-1"),
    ),
)
def test_rule_013_blank_or_nonpositive_usage_skips(field_name, field_value):
    result = _audit_overlap(
        **{
            field_name: field_value,
            "end_time1": "08:20",
            "start_time4": "08:15",
        }
    )

    assert all(
        exception.rule_id != "CC-RULE-013"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-013"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_field"),
    (
        ("type1_used", "malformed", "Type1Used"),
        ("type1_used", "NaN", "Type1Used"),
        ("type4_used", "malformed", "Type4Used"),
        ("type4_used", "Infinity", "Type4Used"),
    ),
)
def test_rule_013_malformed_or_nonfinite_usage_warns(
    field_name,
    field_value,
    expected_field,
):
    result = _audit_overlap(**{field_name: field_value})
    warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-013"
    )

    assert len(warnings) == 1
    assert warnings[0].invalid_fields == (expected_field,)
    assert "malformed or non-finite" in warnings[0].message


@pytest.mark.parametrize("start_time4", ("08:10", "08:11"))
def test_rule_013_equality_and_same_day_positive_gap_pass_without_overall_times(
    start_time4,
):
    result = _audit_overlap(
        start_time="malformed",
        end_time="",
        end_time1="08:10",
        start_time4=start_time4,
    )

    assert all(
        exception.rule_id != "CC-RULE-013"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-013"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    ("end_time1", "start_time4", "expected_overlap"),
    (
        ("08:16", "08:15", "1 minute"),
        ("20:20", "20:15", "5 minutes"),
    ),
)
def test_rule_013_same_day_overlap_fails_with_exact_details(
    end_time1,
    start_time4,
    expected_overlap,
):
    result = _audit_overlap(
        start_time="20:00",
        end_time="20:30",
        end_time1=end_time1,
        start_time4=start_time4,
    )
    exception = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-013"
    )[0]

    assert exception.rule_name == "Pass Overlap"
    assert exception.exception_message == "Pass overlap."
    assert tuple(
        (detail.label, detail.value)
        for detail in exception.details
    ) == (
        ("Overall StartTime", "20:00"),
        ("Overall EndTime", "20:30"),
        ("Type I EndTime1", end_time1),
        ("Type IV StartTime4", start_time4),
        ("Calculated overlap", expected_overlap),
        (
            "Explanation",
            (
                f"Type IV began at {start_time4}, {expected_overlap} before "
                f"Type I ended at {end_time1}, and the overall event did not "
                "cross midnight."
            ),
        ),
    )


def test_rule_013_overnight_sequence_passes():
    result = _audit_overlap(
        start_time="23:45",
        end_time="00:10",
        date_created="2026-01-15 23:45",
        end_time1="23:59",
        start_time4="00:01",
    )

    assert all(
        exception.rule_id != "CC-RULE-013"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-013"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_field"),
    (
        ("end_time1", "", "EndTime1"),
        ("end_time1", "malformed", "EndTime1"),
        ("start_time4", "", "StartTime4"),
        ("start_time4", "malformed", "StartTime4"),
    ),
)
def test_rule_013_missing_or_malformed_step_time_warns(
    field_name,
    field_value,
    expected_field,
):
    result = _audit_overlap(**{field_name: field_value})
    warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-013"
    )

    assert len(warnings) == 1
    assert warnings[0].invalid_fields == (expected_field,)
    assert all(
        exception.rule_id != "CC-RULE-013"
        for exception in result.exceptions
    )


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_field"),
    (
        ("start_time", "", "StartTime"),
        ("start_time", "malformed", "StartTime"),
        ("end_time", "", "EndTime"),
        ("end_time", "malformed", "EndTime"),
    ),
)
def test_rule_013_ambiguous_midnight_status_warns(
    field_name,
    field_value,
    expected_field,
):
    result = _audit_overlap(
        end_time1="23:59",
        start_time4="00:01",
        **{field_name: field_value},
    )
    warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-013"
    )

    assert len(warnings) == 1
    assert warnings[0].invalid_fields == (expected_field,)
    assert "determine whether the event crossed midnight" in (
        warnings[0].message
    )


def test_rule_006_treats_overlap_as_no_excessive_gap_while_rule_013_fails():
    result = _audit_overlap(
        start_time="08:00",
        end_time="08:30",
        end_time1="08:20",
        start_time4="08:15",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-013",)


def test_rule_013_orders_by_csv_row_then_rule_id():
    common_values = {
        "type1_used": "1",
        "type1_concentration": "50",
        "freezing_point1": "-17.3",
        "ambient_temp": "1",
        "process_time1": "1",
        "type4_used": "1",
        "type4_brix": "35",
        "type4_concentration": "100",
        "process_time4": "1",
        "end_time1": "08:20",
        "start_time4": "08:15",
    }
    result = run_audit(
        _import_result(
            _source_row(
                source_row_number=3,
                **common_values,
            ),
            _source_row(
                source_row_number=2,
                tail_number="N121UP",
                **common_values,
            ),
        ),
        DEFAULT_SETTINGS,
    )

    assert tuple(
        (exception.source_row_number, exception.rule_id)
        for exception in result.exceptions
    ) == (
        (2, "CC-RULE-012"),
        (2, "CC-RULE-013"),
        (3, "CC-RULE-013"),
    )


def test_rule_014_aircraft_type_0_is_always_exempt():
    result = _audit_type4_explanation(
        aircraft_type="0",
        tail_number="",
        notes="",
        truck_number="malformed",
        type1_used="malformed",
        type4_used="Infinity",
    )

    assert all(
        exception.rule_id != "CC-RULE-014"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-014"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    ("aircraft_type", "tail_number"),
    (("1", "N121UP"), ("1.0", "N121UP"), ("2", "N12345"), ("2.00", "AB-123")),
)
def test_rule_014_aircraft_types_1_and_2_apply_and_valid_notes_pass(
    aircraft_type,
    tail_number,
):
    result = _audit_type4_explanation(
        aircraft_type=aircraft_type,
        tail_number=tail_number,
    )

    assert all(
        exception.rule_id != "CC-RULE-014"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-014"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize("type1_used", ("", "0", "-1"))
def test_rule_014_blank_zero_and_negative_type1_usage_are_applicable(
    type1_used,
):
    result = _audit_type4_explanation(
        type1_used=type1_used,
        notes="",
    )

    assert tuple(
        exception.rule_id
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-014"
    ) == ("CC-RULE-014",)


@pytest.mark.parametrize(
    "aircraft_type",
    ("", "malformed", "NaN", "Infinity", "1.5", "-1", "3"),
)
def test_rule_014_invalid_aircraft_type_warns_when_usage_would_apply(
    aircraft_type,
):
    result = _audit_type4_explanation(aircraft_type=aircraft_type)
    warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-014"
    )

    assert len(warnings) == 1
    assert warnings[0].invalid_fields == ("AircraftType",)


@pytest.mark.parametrize("type4_used", ("", "0", "-1"))
def test_rule_014_nonpositive_or_blank_type4_usage_skips(type4_used):
    result = _audit_type4_explanation(
        type1_used="malformed",
        type4_used=type4_used,
        notes="",
        truck_number="malformed",
    )

    assert all(
        finding.rule_id != "CC-RULE-014"
        for finding in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-014"
        for warning in result.unable_to_evaluate
    )


def test_rule_014_positive_type1_usage_skips_even_with_invalid_type4_usage():
    result = _audit_type4_explanation(
        type1_used="1",
        type4_used="malformed",
        notes="",
        truck_number="malformed",
    )

    assert all(
        finding.rule_id != "CC-RULE-014"
        for finding in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-014"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    ("type1_used", "type4_used", "expected_fields"),
    (
        ("malformed", "1", ("Type1Used",)),
        ("NaN", "1", ("Type1Used",)),
        ("", "malformed", ("Type4Used",)),
        ("", "Infinity", ("Type4Used",)),
        ("malformed", "Infinity", ("Type1Used", "Type4Used")),
    ),
)
def test_rule_014_invalid_usage_warns_when_applicability_is_ambiguous(
    type1_used,
    type4_used,
    expected_fields,
):
    result = _audit_type4_explanation(
        type1_used=type1_used,
        type4_used=type4_used,
    )
    warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-014"
    )

    assert len(warnings) == 1
    assert warnings[0].invalid_fields == expected_fields


@pytest.mark.parametrize(
    "notes",
    (
        "Type I applied by truck 2",
        "Type 1 applied by truck 2",
        "T1 applied by truck 2",
        "TYPE-I APPLIED BY TRUCK 2",
    ),
)
def test_rule_014_accepts_each_type1_reference(notes):
    result = _audit_type4_explanation(notes=notes)

    assert all(
        exception.rule_id != "CC-RULE-014"
        for exception in result.exceptions
    )


@pytest.mark.parametrize(
    "application_word",
    ("applied", "sprayed", "completed", "performed", "done"),
)
def test_rule_014_accepts_each_application_word(application_word):
    result = _audit_type4_explanation(
        notes=f"Type I {application_word} by truck 2"
    )

    assert all(
        exception.rule_id != "CC-RULE-014"
        for exception in result.exceptions
    )


@pytest.mark.parametrize(
    "truck_phrase",
    ("truck 2", "truck #2", "truck no. 2", "truck number 2"),
)
def test_rule_014_accepts_each_truck_number_format(truck_phrase):
    result = _audit_type4_explanation(
        notes=f"Type I applied by {truck_phrase}"
    )

    assert all(
        exception.rule_id != "CC-RULE-014"
        for exception in result.exceptions
    )


@pytest.mark.parametrize(
    ("notes", "expected_reasons"),
    (
        (
            "",
            (
                "Notes are blank",
                "Missing Type I reference",
                "Missing application wording",
                "Missing documented truck number",
            ),
        ),
        (
            "Type IV only",
            (
                "Missing Type I reference",
                "Missing application wording",
                "Missing documented truck number",
            ),
        ),
        (
            "Another truck applied Type I",
            ("Missing documented truck number",),
        ),
        (
            "Type I completed",
            ("Missing documented truck number",),
        ),
        (
            "Type I applied; flight 123",
            ("Missing documented truck number",),
        ),
        (
            "Truck 2 applied the fluid",
            ("Missing Type I reference",),
        ),
        (
            "Type I from truck 2",
            ("Missing application wording",),
        ),
    ),
)
def test_rule_014_missing_note_components_fail(notes, expected_reasons):
    result = _audit_type4_explanation(notes=notes)
    exception = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-014"
    )[0]

    assert exception.details[5].value == "; ".join(expected_reasons)


def test_rule_014_same_truck_fails_and_different_truck_passes():
    failing = _audit_type4_explanation(
        truck_number="12",
        notes="Type I applied by truck 12",
    )
    passing = _audit_type4_explanation(
        truck_number="12",
        notes="Type I applied by truck 13",
    )
    exception = tuple(
        exception
        for exception in failing.exceptions
        if exception.rule_id == "CC-RULE-014"
    )[0]

    assert exception.details[5].value == (
        "Documented truck number matches current TruckNumber"
    )
    assert exception.details[6].value == "12"
    assert all(
        finding.rule_id != "CC-RULE-014"
        for finding in passing.exceptions
    )


@pytest.mark.parametrize(
    ("current_truck", "documented_truck", "should_fail"),
    (
        ("0012", "12", True),
        ("12", "0012", True),
        ("0012", "00013", False),
    ),
)
def test_rule_014_compares_truck_numbers_numerically(
    current_truck,
    documented_truck,
    should_fail,
):
    result = _audit_type4_explanation(
        truck_number=current_truck,
        notes=f"Type I applied by truck {documented_truck}",
    )
    exceptions = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-014"
    )

    assert bool(exceptions) is should_fail


def test_rule_014_supports_truck_identifiers_of_any_length():
    very_long_identifier = "9" * 5000
    result = _audit_type4_explanation(
        truck_number="1",
        notes=f"Type I completed by truck {very_long_identifier}",
    )

    assert all(
        exception.rule_id != "CC-RULE-014"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-014"
        for warning in result.unable_to_evaluate
    )


def test_rule_014_multiple_documented_trucks_pass_when_one_differs():
    passing = _audit_type4_explanation(
        truck_number="12",
        notes=(
            "Type I applied by truck 0012 and completed by truck number 13"
        ),
    )
    failing = _audit_type4_explanation(
        truck_number="12",
        notes="Type I applied by truck 0012 and truck #00012",
    )

    assert all(
        exception.rule_id != "CC-RULE-014"
        for exception in passing.exceptions
    )
    exception = tuple(
        exception
        for exception in failing.exceptions
        if exception.rule_id == "CC-RULE-014"
    )[0]
    assert exception.details[-1].value == "0012, 00012"


@pytest.mark.parametrize(
    "truck_number",
    ("", "TRUCK-1", "12.0", "-1"),
)
def test_rule_014_invalid_current_truck_number_warns(truck_number):
    result = _audit_type4_explanation(truck_number=truck_number)
    warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-014"
    )

    assert len(warnings) == 1
    assert warnings[0].invalid_fields == ("TruckNumber",)
    assert all(
        exception.rule_id != "CC-RULE-014"
        for exception in result.exceptions
    )


def test_rule_014_exception_details_preserve_original_values():
    result = _audit_type4_explanation(
        aircraft_type=" 2.00 ",
        type1_used=" -1 ",
        type4_used=" 1.0 ",
        truck_number="0012",
        notes="  TYPE-I applied by truck #00012!  ",
    )
    exception = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-014"
    )[0]

    assert exception.rule_name == (
        "Type IV Without Type I Explanation Required"
    )
    assert exception.exception_message == (
        "Type IV applied without documented Type I truck."
    )
    assert tuple(
        (detail.label, detail.value)
        for detail in exception.details
    ) == (
        ("AircraftType", " 2.00 "),
        ("Type1Used", " -1 "),
        ("Type4Used", " 1.0 "),
        ("Current TruckNumber", "0012"),
        ("Original Notes", "  TYPE-I applied by truck #00012!  "),
        (
            "Missing or failed requirement",
            "Documented truck number matches current TruckNumber",
        ),
        ("Documented truck number", "00012"),
    )


def test_rule_014_orders_by_csv_row_then_rule_id():
    common_values = {
        "type1_used": "",
        "type4_used": "1",
        "type4_brix": "35",
        "type4_concentration": "100",
        "process_time4": "1",
        "truck_number": "1",
        "notes": "",
    }
    result = run_audit(
        _import_result(
            _source_row(
                source_row_number=3,
                **common_values,
            ),
            _source_row(
                source_row_number=2,
                tail_number="N121UP",
                **common_values,
            ),
        ),
        DEFAULT_SETTINGS,
    )

    assert tuple(
        (exception.source_row_number, exception.rule_id)
        for exception in result.exceptions
    ) == (
        (2, "CC-RULE-012"),
        (2, "CC-RULE-014"),
        (3, "CC-RULE-014"),
    )


def test_type1_and_type4_exceptions_are_ordered_by_rule_id_on_same_row():
    result = _audit_one(
        type1_used="1",
        type1_concentration="65",
        freezing_point1="-20",
        ambient_temp="-32",
        type4_used="1",
        type4_brix="33.9",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-003", "CC-RULE-005")


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    (
        ("type1_used", ""),
        ("type1_used", "0"),
        ("type1_used", "-1"),
        ("type4_used", ""),
        ("type4_used", "0"),
        ("type4_used", "-1"),
    ),
)
def test_rule_006_blank_or_nonpositive_usage_skips(field_name, field_value):
    result = _audit_gap(**{field_name: field_value, "start_time4": "08:30"})

    assert all(
        exception.rule_id != "CC-RULE-006"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-006"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize("field_name", ("type1_used", "type4_used"))
def test_rule_006_malformed_usage_is_unable_to_evaluate(field_name):
    result = _audit_gap(**{field_name: "malformed"})

    rule_warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-006"
    )

    assert result.exception_count == 0
    assert len(rule_warnings) == 1
    assert rule_warnings[0].invalid_fields == (
        "Type1Used" if field_name == "type1_used" else "Type4Used",
    )


def test_rule_006_nonpositive_usage_skips_when_other_usage_is_malformed():
    result = _audit_gap(type1_used="malformed", type4_used="0")

    assert all(
        warning.rule_id != "CC-RULE-006"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    ("type1_end", "type4_start"),
    (
        ("08:10", "08:10"),
        ("08:10", "08:11"),
        ("23:44", "23:49"),
    ),
)
def test_rule_006_gaps_at_or_below_default_pass(type1_end, type4_start):
    result = _audit_gap(
        end_time1=type1_end,
        start_time4=type4_start,
    )

    assert result.exception_count == 0
    assert result.unable_to_evaluate_count == 0


def test_rule_006_six_minute_gap_fails_with_required_details():
    result = _audit_gap(
        end_time1="23:44",
        start_time4="23:50",
    )

    assert result.exception_count == 1
    exception = result.exceptions[0]
    assert exception.rule_id == "CC-RULE-006"
    assert exception.rule_name == "Excessive Gap Between Steps"
    assert exception.exception_message == "Excessive gap between steps."
    assert tuple(
        (detail.label, detail.value) for detail in exception.details
    ) == (
        ("Type I end time", "23:44"),
        ("Type IV start time", "23:50"),
        ("Actual calculated gap", "6 minutes"),
        ("Configured Allowed Gap", "5 minutes"),
        ("Amount over setting", "1 minute"),
        (
            "Comparison",
            (
                "Type I ended at 23:44. Type IV began at 23:50. "
                "Actual gap: 6 minutes. Allowed gap: 5 minutes. "
                "Exceeded by 1 minute."
            ),
        ),
    )


def test_rule_006_ten_minute_gap_reports_five_minutes_over():
    result = _audit_gap(
        end_time1="08:10",
        start_time4="08:20",
    )

    exception = result.exceptions[0]
    assert exception.rule_id == "CC-RULE-006"
    assert exception.details[2].value == "10 minutes"
    assert exception.details[4].value == "5 minutes"


def test_rule_006_setting_zero_allows_only_zero_minute_gap():
    settings = replace(DEFAULT_SETTINGS, allowed_gap_minutes=0)

    passing = _audit_gap(
        settings=settings,
        end_time1="08:10",
        start_time4="08:10",
    )
    failing = _audit_gap(
        settings=settings,
        end_time1="08:10",
        start_time4="08:11",
    )

    assert passing.exception_count == 0
    assert failing.exceptions[0].rule_id == "CC-RULE-006"
    assert failing.exceptions[0].details[3].value == "0 minutes"
    assert failing.exceptions[0].details[4].value == "1 minute"


def test_rule_006_setting_99_passes_99_and_fails_100_minutes():
    settings = replace(DEFAULT_SETTINGS, allowed_gap_minutes=99)

    passing = _audit_gap(
        settings=settings,
        end_time1="08:00",
        start_time4="09:39",
    )
    failing = _audit_gap(
        settings=settings,
        end_time1="08:00",
        start_time4="09:40",
    )

    assert passing.exception_count == 0
    assert failing.exceptions[0].rule_id == "CC-RULE-006"
    assert failing.exceptions[0].details[2].value == "100 minutes"
    assert failing.exceptions[0].details[4].value == "1 minute"


@pytest.mark.parametrize(
    ("type4_start", "expected_gap", "should_fail"),
    (
        ("00:03", "5 minutes", False),
        ("00:04", "6 minutes", True),
        ("00:00", "1 minute", False),
    ),
)
def test_rule_006_overnight_gap_uses_overall_event(
    type4_start,
    expected_gap,
    should_fail,
):
    result = _audit_gap(
        start_time="23:45",
        end_time="00:10",
        date_created="2026-01-15 23:45",
        end_time1="23:58" if type4_start != "00:00" else "23:59",
        start_time4=type4_start,
    )

    rule_exceptions = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-006"
    )
    assert bool(rule_exceptions) is should_fail
    if should_fail:
        assert rule_exceptions[0].details[2].value == expected_gap


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_invalid_field"),
    (
        ("start_time", "malformed", "StartTime"),
        ("end_time", "malformed", "EndTime"),
    ),
)
def test_rule_006_invalid_overall_time_warns_only_when_midnight_is_needed(
    field_name,
    field_value,
    expected_invalid_field,
):
    overnight_result = _audit_gap(
        end_time1="23:58",
        start_time4="00:03",
        **{field_name: field_value},
    )
    forward_result = _audit_gap(
        end_time1="08:10",
        start_time4="08:15",
        **{field_name: field_value},
    )

    overnight_warnings = tuple(
        warning
        for warning in overnight_result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-006"
    )
    forward_warnings = tuple(
        warning
        for warning in forward_result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-006"
    )
    assert len(overnight_warnings) == 1
    assert overnight_warnings[0].invalid_fields == (expected_invalid_field,)
    assert forward_warnings == ()


def test_rule_006_same_day_overlap_is_not_a_24_hour_gap():
    result = _audit_gap(
        start_time="08:00",
        end_time="09:00",
        end_time1="08:40",
        start_time4="08:30",
    )

    assert all(
        exception.rule_id != "CC-RULE-006"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-006"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_invalid_field"),
    (
        ("end_time1", "", "EndTime1"),
        ("end_time1", "8:10 AM", "EndTime1"),
        ("start_time4", "", "StartTime4"),
        ("start_time4", "08:10:00", "StartTime4"),
    ),
)
def test_rule_006_missing_or_malformed_step_time_is_warning(
    field_name,
    field_value,
    expected_invalid_field,
):
    result = _audit_gap(**{field_name: field_value})

    rule_warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-006"
    )
    assert result.exception_count == 0
    assert len(rule_warnings) == 1
    assert rule_warnings[0].invalid_fields == (expected_invalid_field,)


@pytest.mark.parametrize("allowed_gap", (None, 5.0, True, -1, 100))
def test_rule_006_invalid_allowed_gap_setting_is_warning(allowed_gap):
    settings = replace(
        DEFAULT_SETTINGS,
        allowed_gap_minutes=allowed_gap,
    )

    result = _audit_gap(settings=settings)

    rule_warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-006"
    )
    assert result.exception_count == 0
    assert len(rule_warnings) == 1
    assert rule_warnings[0].invalid_fields == ("Allowed Gap setting",)


def test_rule_005_and_rule_006_exceptions_are_ordered_on_same_row():
    result = _audit_gap(
        type4_brix="33.9",
        end_time1="08:10",
        start_time4="08:16",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-005", "CC-RULE-006")


@pytest.mark.parametrize(
    ("precipitation", "type4_used"),
    (
        ("", ""),
        ("   ", "0"),
        ("None", "0"),
        ("NONE", ""),
        ("none", "0"),
        (" NoNe ", "0.00"),
    ),
)
def test_rule_007_no_active_precipitation_passes(
    precipitation,
    type4_used,
):
    result = _audit_one(
        precipitation=precipitation,
        type4_used=type4_used,
    )

    assert all(
        exception.rule_id != "CC-RULE-007"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-007"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    ("precipitation", "type4_used"),
    (
        ("Snow", ""),
        ("Snow", "   "),
        ("Snow", "0"),
        ("Snow", "0.0"),
        ("Freezing Rain", "0.00"),
        ("Rain", ""),
        ("Unfamiliar Condition", "0"),
    ),
)
def test_rule_007_active_precipitation_without_type4_fails(
    precipitation,
    type4_used,
):
    result = _audit_one(
        precipitation=precipitation,
        type4_used=type4_used,
    )

    assert result.exception_count == 1
    assert result.exceptions[0].rule_id == "CC-RULE-007"
    assert result.exceptions[0].exception_message == (
        "No Type IV during active precipitation."
    )
    assert result.unable_to_evaluate_count == 0


@pytest.mark.parametrize(
    ("precipitation", "type4_used"),
    (
        ("Snow", "1"),
        ("Snow", "0.1"),
        ("Freezing Rain", "25"),
    ),
)
def test_rule_007_positive_type4_passes(precipitation, type4_used):
    result = _audit_one(
        precipitation=precipitation,
        type4_used=type4_used,
        type4_brix="35",
    )

    assert result.exception_count == 0
    assert result.unable_to_evaluate_count == 0


def test_rule_007_exception_preserves_original_values_and_details():
    result = _audit_one(
        precipitation=" MiXeD Precipitation ",
        type4_used="0.00",
    )

    exception = result.exceptions[0]
    assert exception.rule_id == "CC-RULE-007"
    assert exception.rule_name == "No Type IV During Active Precipitation"
    assert tuple(
        (detail.label, detail.value) for detail in exception.details
    ) == (
        ("Recorded precipitation", " MiXeD Precipitation "),
        ("Type IV amount recorded", "0.00"),
        (
            "Finding",
            "No Type IV fluid was recorded during active precipitation.",
        ),
    )


def test_rule_007_blank_type4_displays_blank_without_mutating_source():
    source_row = _source_row(
        precipitation="Snow",
        type4_used="   ",
    )
    result = run_audit(_import_result(source_row), DEFAULT_SETTINGS)

    assert source_row.get("Type4Used") == "   "
    assert result.exceptions[0].details[1].value == "Blank"


@pytest.mark.parametrize(
    "type4_used",
    ("malformed", "NaN", "Infinity", "-1"),
)
def test_rule_007_invalid_type4_during_active_precipitation_is_warning(
    type4_used,
):
    result = _audit_one(
        precipitation="Snow",
        type4_used=type4_used,
    )

    rule_warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-007"
    )
    assert result.exception_count == 0
    assert len(rule_warnings) == 1
    assert rule_warnings[0].invalid_fields == ("Type4Used",)
    assert "malformed, non-finite, or negative" in rule_warnings[0].message


def test_rule_007_inactive_precipitation_skips_malformed_type4():
    result = _audit_one(
        precipitation="None",
        type4_used="malformed",
    )

    assert all(
        exception.rule_id != "CC-RULE-007"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-007"
        for warning in result.unable_to_evaluate
    )


def test_rule_007_exception_orders_after_earlier_rule_on_same_row():
    result = _audit_one(
        date_created="2026-01-15 07:59",
        precipitation="Snow",
        type4_used="0",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-001", "CC-RULE-007")


@pytest.mark.parametrize("type1_used", ("", "0", "0.0", "-1"))
def test_rule_008_nonpositive_or_blank_type1_usage_skips(type1_used):
    result = _audit_type1_rate(type1_used=type1_used)

    assert all(
        exception.rule_id != "CC-RULE-008"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-008"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize("type1_used", ("malformed", "NaN", "Infinity"))
def test_rule_008_invalid_type1_usage_creates_warning(type1_used):
    result = _audit_type1_rate(type1_used=type1_used)
    rule_warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-008"
    )

    assert len(rule_warnings) == 1
    assert rule_warnings[0].invalid_fields == ("Type1Used",)
    assert "malformed or non-finite" in rule_warnings[0].message
    assert all(
        exception.rule_id != "CC-RULE-008"
        for exception in result.exceptions
    )


@pytest.mark.parametrize(
    ("type1_used", "process_time1", "should_fail", "displayed_rate"),
    (
        ("120", "1", False, None),
        ("121", "1", True, "60.5 gallons per minute"),
        ("60", "0", False, None),
        ("61", "0", True, "61 gallons per minute"),
        ("180", "2", False, None),
        (
            "60.000000000000000000000000001",
            "0",
            True,
            "60.000000000000000000000000001 gallons per minute",
        ),
    ),
)
def test_rule_008_default_maximum_boundaries(
    type1_used,
    process_time1,
    should_fail,
    displayed_rate,
):
    result = _audit_type1_rate(
        type1_used=type1_used,
        process_time1=process_time1,
    )
    rule_exceptions = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-008"
    )

    assert bool(rule_exceptions) is should_fail
    if displayed_rate is not None:
        assert rule_exceptions[0].details[3].value == displayed_rate


@pytest.mark.parametrize("process_time1", ("0", "1", "1.0", "5.00"))
def test_rule_008_accepts_numerically_whole_process_times(process_time1):
    result = _audit_type1_rate(
        type1_used="1",
        process_time1=process_time1,
    )

    assert all(
        warning.rule_id != "CC-RULE-008"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    "process_time1",
    ("", "malformed", "NaN", "Infinity", "-1", "1.5"),
)
def test_rule_008_invalid_process_time_creates_warning(process_time1):
    result = _audit_type1_rate(process_time1=process_time1)
    rule_warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-008"
    )

    assert len(rule_warnings) == 1
    assert rule_warnings[0].invalid_fields == ("ProcessTime1",)
    assert "finite, nonnegative" in rule_warnings[0].message
    assert all(
        exception.rule_id != "CC-RULE-008"
        for exception in result.exceptions
    )


def test_rule_008_personal_maximum_equality_passes():
    settings = replace(
        DEFAULT_SETTINGS,
        name="Personal — RateUser",
        is_default=False,
        max_type1_rate_gpm=Decimal("50"),
    )

    result = _audit_type1_rate(
        settings=settings,
        type1_used="100",
        process_time1="1",
    )

    assert all(
        exception.rule_id != "CC-RULE-008"
        for exception in result.exceptions
    )


def test_rule_008_personal_maximum_above_boundary_fails():
    settings = replace(
        DEFAULT_SETTINGS,
        name="Personal — RateUser",
        is_default=False,
        max_type1_rate_gpm=Decimal("50"),
    )

    result = _audit_type1_rate(
        settings=settings,
        type1_used="101",
        process_time1="1",
    )

    assert result.exceptions[-1].rule_id == "CC-RULE-008"
    assert result.exceptions[-1].details[3].value == (
        "50.5 gallons per minute"
    )
    assert result.exceptions[-1].details[4].value == (
        "50 gallons per minute"
    )


@pytest.mark.parametrize(
    "invalid_maximum",
    (
        None,
        "60",
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("0"),
        Decimal("-1"),
    ),
)
def test_rule_008_invalid_runtime_maximum_is_warning(invalid_maximum):
    settings = replace(
        DEFAULT_SETTINGS,
        max_type1_rate_gpm=invalid_maximum,
    )

    result = _audit_type1_rate(settings=settings)
    rule_warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-008"
    )

    assert len(rule_warnings) == 1
    assert rule_warnings[0].invalid_fields == (
        "Maximum Type I rate setting",
    )
    assert all(
        exception.rule_id != "CC-RULE-008"
        for exception in result.exceptions
    )


def test_rule_008_missing_runtime_maximum_is_warning():
    result = _audit_type1_rate(
        settings=_settings_without("max_type1_rate_gpm")
    )

    assert tuple(
        warning.rule_id
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-008"
    ) == ("CC-RULE-008",)


def test_rule_008_exception_preserves_source_text_and_details():
    result = _audit_type1_rate(
        type1_used="121.00",
        process_time1="1.0",
    )
    exception = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-008"
    )[0]

    assert exception.rule_name == "Excessive Type I"
    assert exception.exception_message == "Excessive Type I."
    assert tuple(
        (detail.label, detail.value)
        for detail in exception.details
    ) == (
        ("Type I gallons used", "121.00 gallons"),
        ("Recorded ProcessTime1", "1.0 minute"),
        ("Adjusted calculation time", "2 minutes"),
        ("Adjusted Type I rate", "60.5 gallons per minute"),
        (
            "Configured maximum Type I rate",
            "60 gallons per minute",
        ),
        (
            "Comparison",
            (
                "Adjusted rate 60.5 gallons per minute exceeds the "
                "configured maximum of 60 gallons per minute."
            ),
        ),
    )


def test_rule_008_singular_and_plural_minute_wording():
    singular = _audit_type1_rate(
        settings=replace(
            DEFAULT_SETTINGS,
            max_type1_rate_gpm=Decimal("0.5"),
        ),
        type1_used="1",
        process_time1="0",
    )
    plural = _audit_type1_rate(
        type1_used="121",
        process_time1="1",
    )

    singular_details = singular.exceptions[-1].details
    plural_details = plural.exceptions[-1].details
    assert singular_details[0].value == "1 gallon"
    assert singular_details[1].value == "0 minutes"
    assert singular_details[2].value == "1 minute"
    assert plural_details[1].value == "1 minute"
    assert plural_details[2].value == "2 minutes"


def test_rule_008_exception_orders_after_earlier_rule_on_same_row():
    result = _audit_type1_rate(
        date_created="2026-01-15 07:59",
        type1_used="121",
        process_time1="1",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-001", "CC-RULE-008")


@pytest.mark.parametrize("type4_used", ("", "0", "0.0", "-1"))
def test_rule_009_nonpositive_or_blank_usage_skips(type4_used):
    result = _audit_type4_rate(
        type4_used=type4_used,
        type4_brix="malformed",
        process_time4="malformed",
    )

    assert all(
        exception.rule_id != "CC-RULE-009"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-009"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize("type4_used", ("malformed", "NaN", "Infinity"))
def test_rule_009_invalid_type4_usage_creates_warning(type4_used):
    result = _audit_type4_rate(type4_used=type4_used)
    rule_warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-009"
    )

    assert len(rule_warnings) == 1
    assert rule_warnings[0].invalid_fields == ("Type4Used",)
    assert "malformed or non-finite" in rule_warnings[0].message
    assert all(
        exception.rule_id != "CC-RULE-009"
        for exception in result.exceptions
    )


@pytest.mark.parametrize(
    ("type4_used", "process_time4", "should_fail", "displayed_rate"),
    (
        ("60", "1", False, None),
        ("61", "1", True, "30.5 gallons per minute"),
        ("30", "0", False, None),
        ("31", "0", True, "31 gallons per minute"),
        ("90", "2", False, None),
        (
            "30.000000000000000000000000001",
            "0",
            True,
            "30.000000000000000000000000001 gallons per minute",
        ),
    ),
)
def test_rule_009_default_maximum_boundaries(
    type4_used,
    process_time4,
    should_fail,
    displayed_rate,
):
    result = _audit_type4_rate(
        type4_used=type4_used,
        process_time4=process_time4,
    )
    rule_exceptions = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-009"
    )

    assert bool(rule_exceptions) is should_fail
    if displayed_rate is not None:
        assert rule_exceptions[0].details[3].value == displayed_rate


@pytest.mark.parametrize("process_time4", ("0", "1", "1.0", "5.00"))
def test_rule_009_accepts_numerically_whole_process_times(process_time4):
    result = _audit_type4_rate(
        type4_used="1",
        process_time4=process_time4,
    )

    assert all(
        warning.rule_id != "CC-RULE-009"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    "process_time4",
    ("", "malformed", "NaN", "Infinity", "-1", "1.5"),
)
def test_rule_009_invalid_process_time_creates_warning(process_time4):
    result = _audit_type4_rate(process_time4=process_time4)
    rule_warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-009"
    )

    assert len(rule_warnings) == 1
    assert rule_warnings[0].invalid_fields == ("ProcessTime4",)
    assert "finite, nonnegative" in rule_warnings[0].message
    assert all(
        exception.rule_id != "CC-RULE-009"
        for exception in result.exceptions
    )


def test_rule_009_personal_maximum_equality_passes():
    settings = replace(
        DEFAULT_SETTINGS,
        name="Personal — RateUser",
        is_default=False,
        max_type4_rate_gpm=Decimal("20"),
    )

    result = _audit_type4_rate(
        settings=settings,
        type4_used="40",
        process_time4="1",
    )

    assert all(
        exception.rule_id != "CC-RULE-009"
        for exception in result.exceptions
    )


def test_rule_009_personal_maximum_above_boundary_fails():
    settings = replace(
        DEFAULT_SETTINGS,
        name="Personal — RateUser",
        is_default=False,
        max_type4_rate_gpm=Decimal("20"),
    )

    result = _audit_type4_rate(
        settings=settings,
        type4_used="41",
        process_time4="1",
    )
    exception = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-009"
    )[0]

    assert exception.details[3].value == "20.5 gallons per minute"
    assert exception.details[4].value == "20 gallons per minute"


def test_rule_009_is_independent_from_type1_maximum():
    settings = replace(
        DEFAULT_SETTINGS,
        max_type1_rate_gpm=Decimal("0.000001"),
    )

    result = _audit_type4_rate(
        settings=settings,
        type4_used="60",
        process_time4="1",
    )

    assert all(
        exception.rule_id != "CC-RULE-009"
        for exception in result.exceptions
    )


def test_rule_008_is_independent_from_type4_maximum():
    settings = replace(
        DEFAULT_SETTINGS,
        max_type4_rate_gpm=Decimal("0.000001"),
    )

    result = _audit_type1_rate(
        settings=settings,
        type1_used="120",
        process_time1="1",
    )

    assert all(
        exception.rule_id != "CC-RULE-008"
        for exception in result.exceptions
    )


@pytest.mark.parametrize(
    "invalid_maximum",
    (
        None,
        "30",
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("0"),
        Decimal("-1"),
    ),
)
def test_rule_009_invalid_runtime_maximum_is_warning(invalid_maximum):
    settings = replace(
        DEFAULT_SETTINGS,
        max_type4_rate_gpm=invalid_maximum,
    )

    result = _audit_type4_rate(settings=settings)
    rule_warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-009"
    )

    assert len(rule_warnings) == 1
    assert rule_warnings[0].invalid_fields == (
        "Maximum Type IV rate setting",
    )
    assert all(
        exception.rule_id != "CC-RULE-009"
        for exception in result.exceptions
    )


def test_rule_009_missing_runtime_maximum_is_warning():
    result = _audit_type4_rate(
        settings=_settings_without("max_type4_rate_gpm")
    )

    assert tuple(
        warning.rule_id
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-009"
    ) == ("CC-RULE-009",)


def test_rule_009_exception_preserves_source_text_and_details():
    result = _audit_type4_rate(
        type4_used="61.00",
        process_time4="1.0",
    )
    exception = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-009"
    )[0]

    assert exception.rule_name == "Excessive Type IV"
    assert exception.exception_message == "Excessive Type IV."
    assert tuple(
        (detail.label, detail.value)
        for detail in exception.details
    ) == (
        ("Type IV gallons used", "61.00 gallons"),
        ("Recorded ProcessTime4", "1.0 minute"),
        ("Adjusted calculation time", "2 minutes"),
        ("Adjusted Type IV rate", "30.5 gallons per minute"),
        (
            "Configured maximum Type IV rate",
            "30 gallons per minute",
        ),
        (
            "Comparison",
            (
                "Adjusted rate 30.5 gallons per minute exceeds the "
                "configured maximum of 30 gallons per minute."
            ),
        ),
    )


def test_rule_009_singular_and_plural_minute_wording():
    singular = _audit_type4_rate(
        settings=replace(
            DEFAULT_SETTINGS,
            max_type4_rate_gpm=Decimal("0.5"),
        ),
        type4_used="1",
        process_time4="0",
    )
    plural = _audit_type4_rate(
        type4_used="61",
        process_time4="1",
    )

    singular_details = singular.exceptions[-1].details
    plural_details = plural.exceptions[-1].details
    assert singular_details[0].value == "1 gallon"
    assert singular_details[1].value == "0 minutes"
    assert singular_details[2].value == "1 minute"
    assert plural_details[1].value == "1 minute"
    assert plural_details[2].value == "2 minutes"


def test_rule_005_and_rule_009_interactions_are_independent():
    valid_brix_excessive_rate = _audit_type4_rate(
        type4_used="61",
        type4_brix="35",
        process_time4="1",
    )
    invalid_brix_acceptable_rate = _audit_type4_rate(
        type4_used="60",
        type4_brix="33.9",
        process_time4="1",
    )
    invalid_brix_excessive_rate = _audit_type4_rate(
        type4_used="61",
        type4_brix="33.9",
        process_time4="1",
    )

    assert tuple(
        exception.rule_id
        for exception in valid_brix_excessive_rate.exceptions
    ) == ("CC-RULE-009",)
    assert tuple(
        exception.rule_id
        for exception in invalid_brix_acceptable_rate.exceptions
    ) == ("CC-RULE-005",)
    assert tuple(
        exception.rule_id
        for exception in invalid_brix_excessive_rate.exceptions
    ) == ("CC-RULE-005", "CC-RULE-009")


def test_rule_005_warning_does_not_block_rule_009():
    result = _audit_type4_rate(
        type4_used="61",
        type4_brix="malformed",
        process_time4="1",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-009",)
    assert tuple(
        warning.rule_id for warning in result.unable_to_evaluate
    ) == ("CC-RULE-005",)


def test_rule_009_warning_does_not_block_rule_005():
    result = _audit_type4_rate(
        type4_used="60",
        type4_brix="33.9",
        process_time4="malformed",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-005",)
    assert tuple(
        warning.rule_id for warning in result.unable_to_evaluate
    ) == ("CC-RULE-009", "CC-RULE-010")


def test_rule_009_orders_by_csv_row_then_rule_id():
    result = run_audit(
        _import_result(
            _source_row(
                source_row_number=3,
                type4_used="61",
                type4_brix="35",
                process_time4="1",
            ),
            _source_row(
                source_row_number=2,
                type4_used="61",
                type4_brix="33.9",
                process_time4="1",
            ),
        ),
        DEFAULT_SETTINGS,
    )

    assert tuple(
        (exception.source_row_number, exception.rule_id)
        for exception in result.exceptions
    ) == (
        (2, "CC-RULE-005"),
        (2, "CC-RULE-009"),
        (3, "CC-RULE-009"),
    )


def test_rule_010_neither_fluid_used_skips_without_warning():
    result = _audit_event_time(
        type1_used="0",
        type4_used="-1",
        process_time1="malformed",
        process_time4="malformed",
    )

    assert all(
        exception.rule_id != "CC-RULE-010"
        for exception in result.exceptions
    )
    assert all(
        warning.rule_id != "CC-RULE-010"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    ("field_name", "field_value", "other_field", "expected_field"),
    (
        ("type1_used", "malformed", "type4_used", "Type1Used"),
        ("type4_used", "malformed", "type1_used", "Type4Used"),
        ("type1_used", "NaN", "type4_used", "Type1Used"),
        ("type4_used", "Infinity", "type1_used", "Type4Used"),
    ),
)
def test_rule_010_malformed_or_nonfinite_usage_warns(
    field_name,
    field_value,
    other_field,
    expected_field,
):
    result = _audit_event_time(
        **{
            field_name: field_value,
            other_field: "",
        }
    )
    warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-010"
    )

    assert len(warnings) == 1
    assert warnings[0].invalid_fields == (expected_field,)
    assert all(
        exception.rule_id != "CC-RULE-010"
        for exception in result.exceptions
    )


@pytest.mark.parametrize(
    ("process_time1", "should_fail"),
    (("30", False), ("31", True)),
)
def test_rule_010_type1_only_boundaries(process_time1, should_fail):
    result = _audit_event_time(
        process_time1=process_time1,
        process_time4="malformed",
    )
    rule_exceptions = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-010"
    )

    assert bool(rule_exceptions) is should_fail
    assert all(
        warning.rule_id != "CC-RULE-010"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    ("process_time4", "should_fail"),
    (("30", False), ("31", True)),
)
def test_rule_010_type4_only_boundaries(process_time4, should_fail):
    result = _audit_event_time(
        type1_used="",
        process_time1="malformed",
        type4_used="1",
        type4_brix="35",
        process_time4=process_time4,
    )
    rule_exceptions = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-010"
    )

    assert bool(rule_exceptions) is should_fail
    assert all(
        warning.rule_id != "CC-RULE-010"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    ("used_field", "process_field", "process_value", "expected_field"),
    (
        ("type1_used", "process_time1", "", "ProcessTime1"),
        ("type1_used", "process_time1", "malformed", "ProcessTime1"),
        ("type1_used", "process_time1", "NaN", "ProcessTime1"),
        ("type1_used", "process_time1", "Infinity", "ProcessTime1"),
        ("type1_used", "process_time1", "-1", "ProcessTime1"),
        ("type1_used", "process_time1", "1.5", "ProcessTime1"),
        ("type4_used", "process_time4", "", "ProcessTime4"),
        ("type4_used", "process_time4", "malformed", "ProcessTime4"),
        ("type4_used", "process_time4", "NaN", "ProcessTime4"),
        ("type4_used", "process_time4", "Infinity", "ProcessTime4"),
        ("type4_used", "process_time4", "-1", "ProcessTime4"),
        ("type4_used", "process_time4", "1.5", "ProcessTime4"),
    ),
)
def test_rule_010_invalid_applicable_process_time_warns(
    used_field,
    process_field,
    process_value,
    expected_field,
):
    row_values = {
        "type1_used": "",
        "type4_used": "",
        "process_time1": "",
        "process_time4": "",
        used_field: "1",
        process_field: process_value,
    }
    result = _audit_event_time(**row_values)
    warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-010"
    )

    assert len(warnings) == 1
    assert warnings[0].invalid_fields == (expected_field,)
    assert all(
        exception.rule_id != "CC-RULE-010"
        for exception in result.exceptions
    )


@pytest.mark.parametrize("process_time", ("0", "1", "1.0", "5.00"))
def test_rule_010_accepts_equivalent_whole_process_times(process_time):
    result = _audit_event_time(process_time1=process_time)

    assert all(
        warning.rule_id != "CC-RULE-010"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    ("process_time1", "process_time4", "should_fail"),
    (("15", "15", False), ("15", "16", True)),
)
def test_rule_010_combined_include_gap_off_boundaries(
    process_time1,
    process_time4,
    should_fail,
):
    result = _audit_event_time(
        type4_used="1",
        process_time1=process_time1,
        process_time4=process_time4,
        end_time1="08:10",
        start_time4="08:25",
    )
    rule_exceptions = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-010"
    )

    assert bool(rule_exceptions) is should_fail


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    (
        ("end_time1", "malformed"),
        ("start_time4", "malformed"),
        ("start_time", "malformed"),
        ("end_time", "malformed"),
    ),
)
def test_rule_010_include_gap_off_ignores_clock_fields(
    field_name,
    field_value,
):
    result = _audit_event_time(
        type4_used="1",
        process_time1="15",
        process_time4="16",
        **{field_name: field_value},
    )

    assert tuple(
        exception.rule_id
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-010"
    ) == ("CC-RULE-010",)
    assert all(
        warning.rule_id != "CC-RULE-010"
        for warning in result.unable_to_evaluate
    )


@pytest.mark.parametrize(
    ("type4_start", "should_fail", "expected_gap"),
    (("08:15", False, None), ("08:16", True, "6 minutes")),
)
def test_rule_010_include_gap_on_same_day_boundaries(
    type4_start,
    should_fail,
    expected_gap,
):
    settings = replace(DEFAULT_SETTINGS, include_gap_in_event_time=True)
    result = _audit_event_time(
        settings=settings,
        type4_used="1",
        process_time1="10",
        process_time4="15",
        end_time1="08:10",
        start_time4=type4_start,
    )
    rule_exceptions = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-010"
    )

    assert bool(rule_exceptions) is should_fail
    if expected_gap is not None:
        assert expected_gap in rule_exceptions[0].details[5].value


@pytest.mark.parametrize(
    ("type4_start", "should_fail", "expected_gap"),
    (("00:03", False, None), ("00:04", True, "6 minutes overnight")),
)
def test_rule_010_include_gap_on_overnight_boundaries(
    type4_start,
    should_fail,
    expected_gap,
):
    settings = replace(DEFAULT_SETTINGS, include_gap_in_event_time=True)
    result = _audit_event_time(
        settings=settings,
        start_time="23:45",
        end_time="00:15",
        date_created="2026-01-15 23:45",
        type4_used="1",
        process_time1="10",
        process_time4="15",
        end_time1="23:58",
        start_time4=type4_start,
    )
    rule_exceptions = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-010"
    )

    assert bool(rule_exceptions) is should_fail
    if expected_gap is not None:
        assert expected_gap in rule_exceptions[0].details[5].value


def test_rule_010_same_day_overlap_uses_zero_gap_and_continues():
    settings = replace(DEFAULT_SETTINGS, include_gap_in_event_time=True)
    result = _audit_event_time(
        settings=settings,
        start_time="08:00",
        end_time="09:00",
        type4_used="1",
        process_time1="20",
        process_time4="11",
        end_time1="08:20",
        start_time4="08:10",
    )
    exception = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-010"
    )[0]

    assert exception.details[5].value.startswith("0 minutes")
    assert exception.details[6].label == "Overlap handling"
    assert "used a 0-minute gap" in exception.details[6].value
    assert tuple(
        finding.rule_id for finding in result.exceptions
    ) == ("CC-RULE-010", "CC-RULE-013")


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_field"),
    (
        ("end_time1", "", "EndTime1"),
        ("end_time1", "malformed", "EndTime1"),
        ("start_time4", "", "StartTime4"),
        ("start_time4", "malformed", "StartTime4"),
    ),
)
def test_rule_010_include_gap_on_invalid_step_time_warns(
    field_name,
    field_value,
    expected_field,
):
    settings = replace(DEFAULT_SETTINGS, include_gap_in_event_time=True)
    result = _audit_event_time(
        settings=settings,
        type4_used="1",
        process_time1="10",
        process_time4="15",
        **{field_name: field_value},
    )
    warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-010"
    )

    assert len(warnings) == 1
    assert warnings[0].invalid_fields == (expected_field,)


@pytest.mark.parametrize(
    ("field_name", "expected_field"),
    (("start_time", "StartTime"), ("end_time", "EndTime")),
)
def test_rule_010_ambiguous_earlier_step_with_invalid_overall_time_warns(
    field_name,
    expected_field,
):
    settings = replace(DEFAULT_SETTINGS, include_gap_in_event_time=True)
    result = _audit_event_time(
        settings=settings,
        type4_used="1",
        process_time1="10",
        process_time4="15",
        end_time1="23:58",
        start_time4="00:03",
        **{field_name: "malformed"},
    )
    warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-010"
    )

    assert len(warnings) == 1
    assert warnings[0].invalid_fields == (expected_field,)


def test_rule_010_one_step_never_requires_gap_times_when_gap_is_on():
    settings = replace(DEFAULT_SETTINGS, include_gap_in_event_time=True)
    type1_only = _audit_event_time(
        settings=settings,
        process_time1="31",
        end_time1="malformed",
        start_time4="malformed",
    )
    type4_only = _audit_event_time(
        settings=settings,
        type1_used="",
        type4_used="1",
        process_time4="31",
        end_time1="malformed",
        start_time4="malformed",
    )

    assert tuple(
        exception.rule_id
        for exception in type1_only.exceptions
        if exception.rule_id == "CC-RULE-010"
    ) == ("CC-RULE-010",)
    assert tuple(
        exception.rule_id
        for exception in type4_only.exceptions
        if exception.rule_id == "CC-RULE-010"
    ) == ("CC-RULE-010",)
    assert all(
        warning.rule_id != "CC-RULE-010"
        for result in (type1_only, type4_only)
        for warning in result.unable_to_evaluate
    )


def test_rule_010_personal_maximum_equality_passes_and_above_fails():
    settings = replace(
        DEFAULT_SETTINGS,
        name="Personal — EventUser",
        is_default=False,
        max_event_time_minutes=20,
    )

    passing = _audit_event_time(
        settings=settings,
        process_time1="20",
    )
    failing = _audit_event_time(
        settings=settings,
        process_time1="21",
    )

    assert all(
        exception.rule_id != "CC-RULE-010"
        for exception in passing.exceptions
    )
    assert tuple(
        exception.rule_id
        for exception in failing.exceptions
        if exception.rule_id == "CC-RULE-010"
    ) == ("CC-RULE-010",)


@pytest.mark.parametrize(
    "invalid_maximum",
    (None, "30", True, 0, -1, 1000, 30.0),
)
def test_rule_010_invalid_runtime_maximum_warns(invalid_maximum):
    settings = replace(
        DEFAULT_SETTINGS,
        max_event_time_minutes=invalid_maximum,
    )
    result = _audit_event_time(settings=settings)
    warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-010"
    )

    assert len(warnings) == 1
    assert warnings[0].invalid_fields == (
        "Maximum event time setting",
    )


def test_rule_010_missing_runtime_maximum_warns():
    result = _audit_event_time(
        settings=_settings_without("max_event_time_minutes")
    )

    assert tuple(
        warning.rule_id
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-010"
    ) == ("CC-RULE-010",)


@pytest.mark.parametrize("invalid_include_gap", (None, 0, 1, "on"))
def test_rule_010_invalid_runtime_include_gap_warns(invalid_include_gap):
    settings = replace(
        DEFAULT_SETTINGS,
        include_gap_in_event_time=invalid_include_gap,
    )
    result = _audit_event_time(settings=settings)
    warnings = tuple(
        warning
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-010"
    )

    assert len(warnings) == 1
    assert warnings[0].invalid_fields == ("Include Gap setting",)


def test_rule_010_missing_runtime_include_gap_warns():
    result = _audit_event_time(
        settings=_settings_without("include_gap_in_event_time")
    )

    assert tuple(
        warning.rule_id
        for warning in result.unable_to_evaluate
        if warning.rule_id == "CC-RULE-010"
    ) == ("CC-RULE-010",)


def test_rule_006_and_rule_010_can_both_fail_on_one_row():
    settings = replace(DEFAULT_SETTINGS, include_gap_in_event_time=True)
    result = _audit_event_time(
        settings=settings,
        type4_used="1",
        process_time1="10",
        process_time4="15",
        end_time1="08:10",
        start_time4="08:16",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-006", "CC-RULE-010")


def test_rule_010_type4_only_valid_explanation_adds_no_rule_014_finding():
    result = _audit_event_time(
        type1_used="",
        type4_used="1",
        process_time4="31",
    )

    assert tuple(
        exception.rule_id for exception in result.exceptions
    ) == ("CC-RULE-010",)
    assert all(
        warning.rule_id != "CC-RULE-014"
        for warning in result.unable_to_evaluate
    )


def test_rule_010_type1_only_exception_details_are_exact():
    result = _audit_event_time(process_time1="31.0")
    exception = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-010"
    )[0]

    assert exception.rule_name == "Excessive Event Time"
    assert exception.exception_message == "Excessive event time."
    assert tuple(
        (detail.label, detail.value)
        for detail in exception.details
    ) == (
        ("Type I usage status", "Included — 1 gallon recorded"),
        ("Type IV usage status", "Not included — usage is blank"),
        ("ProcessTime1", "31.0 minutes"),
        ("Include Gap setting", "Off"),
        ("Calculated event time", "31 minutes"),
        ("Configured maximum event time", "30 minutes"),
        ("Minutes over the maximum", "1 minute"),
        (
            "Comparison",
            (
                "Calculated event time 31 minutes exceeds the configured "
                "maximum of 30 minutes by 1 minute."
            ),
        ),
    )
    assert all(
        detail.label != "ProcessTime4" for detail in exception.details
    )


def test_rule_010_combined_gap_details_preserve_source_times():
    settings = replace(DEFAULT_SETTINGS, include_gap_in_event_time=True)
    result = _audit_event_time(
        settings=settings,
        type4_used="1",
        process_time1="10",
        process_time4="15",
        end_time1="08:10",
        start_time4="08:16",
    )
    exception = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-010"
    )[0]

    assert tuple(
        (detail.label, detail.value)
        for detail in exception.details
    ) == (
        ("Type I usage status", "Included — 1 gallon recorded"),
        ("Type IV usage status", "Included — 1 gallon recorded"),
        ("ProcessTime1", "10 minutes"),
        ("ProcessTime4", "15 minutes"),
        ("Include Gap setting", "On"),
        (
            "Included gap",
            "6 minutes (EndTime1 08:10 to StartTime4 08:16)",
        ),
        ("Calculated event time", "31 minutes"),
        ("Configured maximum event time", "30 minutes"),
        ("Minutes over the maximum", "1 minute"),
        (
            "Comparison",
            (
                "Calculated event time 31 minutes exceeds the configured "
                "maximum of 30 minutes by 1 minute."
            ),
        ),
    )


def test_rule_010_singular_and_plural_wording():
    result = _audit_event_time(
        settings=replace(DEFAULT_SETTINGS, max_event_time_minutes=1),
        process_time1="2",
    )
    exception = tuple(
        exception
        for exception in result.exceptions
        if exception.rule_id == "CC-RULE-010"
    )[0]

    assert exception.details[-4].value == "2 minutes"
    assert exception.details[-3].value == "1 minute"
    assert exception.details[-2].value == "1 minute"
    assert exception.details[-1].value.endswith("by 1 minute.")


def test_rule_010_orders_by_csv_row_then_rule_id():
    result = run_audit(
        _import_result(
            _source_row(
                source_row_number=3,
                type1_used="1",
                type1_concentration="50",
                freezing_point1="-17.3",
                ambient_temp="1",
                process_time1="31",
            ),
            _source_row(
                source_row_number=2,
                type1_used="1",
                type1_concentration="50",
                freezing_point1="-17.3",
                ambient_temp="1",
                process_time1="31",
            ),
        ),
        DEFAULT_SETTINGS,
    )

    assert tuple(
        (exception.source_row_number, exception.rule_id)
        for exception in result.exceptions
    ) == ((2, "CC-RULE-010"), (3, "CC-RULE-010"))


def test_audit_result_and_exception_structures_are_immutable():
    result = _audit_one(date_created="2026-01-15 07:59")

    with pytest.raises(FrozenInstanceError):
        result.filename = "changed.csv"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.exceptions[0].rule_id = "changed"  # type: ignore[misc]
