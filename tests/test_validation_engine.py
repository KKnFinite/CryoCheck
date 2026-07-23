"""Focused boundary coverage for the executable CryoCheck rules."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from app.services import validation_engine
from app.services.csv_import import CSVImportResult, CSVSourceRow
from app.services.settings import DEFAULT_SETTINGS
from app.services.type4_fluids import TypeIVFluidProfile
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
    type1_used: str = "",
    type1_concentration: str = "",
    freezing_point1: str = "",
    ambient_temp: str = "",
    type4_used: str = "",
    type4_brix: str = "",
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
        "Type1Used": type1_used,
        "Type1Concentration": type1_concentration,
        "FreezingPoint1": freezing_point1,
        "AmbientTemp": ambient_temp,
        "Type4Used": type4_used,
        "Type4ABrix": type4_brix,
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


def test_audit_reports_five_rules_executed():
    result = _audit_one()

    assert result.rules_executed == 5


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
    ) == ("CC-RULE-003", "CC-RULE-004")
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
    assert tuple(
        warning.rule_id for warning in result.unable_to_evaluate
    ) == ("CC-RULE-005",)
    assert result.unable_to_evaluate[0].invalid_fields == ("Type4Used",)


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
    ) == ("CC-RULE-005",)
    assert result.unable_to_evaluate[0].invalid_fields == (
        "Type IV fluid setting",
    )


def test_rule_005_invalid_profile_range_is_unable_to_evaluate(monkeypatch):
    invalid_profile = TypeIVFluidProfile(
        name="Invalid Type IV fluid",
        minimum_brix=Decimal("36.6"),
        maximum_brix=Decimal("34.6"),
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


def test_audit_result_and_exception_structures_are_immutable():
    result = _audit_one(date_created="2026-01-15 07:59")

    with pytest.raises(FrozenInstanceError):
        result.filename = "changed.csv"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.exceptions[0].rule_id = "changed"  # type: ignore[misc]
