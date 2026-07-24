"""In-memory execution for CryoCheck's implemented audit rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext
from typing import Final

from app.services.csv_import import CSVImportResult, CSVSourceRow
from app.services.precipitation import has_active_precipitation
from app.services.rules import IMPLEMENTED_STATUS, RULES, RuleDefinition
from app.services.settings import SettingsDefinition
from app.services.time_of_day import (
    crosses_midnight,
    elapsed_minutes,
    parse_military_time,
)
from app.services.type1_fluids import get_type1_fluid_profile
from app.services.type4_fluids import get_type4_fluid_profile


EXECUTED_RULES: Final[tuple[RuleDefinition, ...]] = tuple(
    rule for rule in RULES if rule.implementation_status == IMPLEMENTED_STATUS
)
_EXECUTED_RULES_BY_ID: Final = {
    rule.rule_id: rule for rule in EXECUTED_RULES
}
_RULE_001 = _EXECUTED_RULES_BY_ID["CC-RULE-001"]
_RULE_002 = _EXECUTED_RULES_BY_ID["CC-RULE-002"]
_RULE_003 = _EXECUTED_RULES_BY_ID["CC-RULE-003"]
_RULE_004 = _EXECUTED_RULES_BY_ID["CC-RULE-004"]
_RULE_005 = _EXECUTED_RULES_BY_ID["CC-RULE-005"]
_RULE_006 = _EXECUTED_RULES_BY_ID["CC-RULE-006"]
_RULE_007 = _EXECUTED_RULES_BY_ID["CC-RULE-007"]
_RULE_008 = _EXECUTED_RULES_BY_ID["CC-RULE-008"]
_RULE_009 = _EXECUTED_RULES_BY_ID["CC-RULE-009"]
_RULE_010 = _EXECUTED_RULES_BY_ID["CC-RULE-010"]
_RULE_011 = _EXECUTED_RULES_BY_ID["CC-RULE-011"]
_RULE_012 = _EXECUTED_RULES_BY_ID["CC-RULE-012"]
_RULE_013 = _EXECUTED_RULES_BY_ID["CC-RULE-013"]
_RULE_014 = _EXECUTED_RULES_BY_ID["CC-RULE-014"]
_TIMESTAMP_RULES: Final = (_RULE_001, _RULE_002)
_TYPE1_RULES: Final = (_RULE_003, _RULE_004)
_REQUIRED_TYPE1_BUFFER: Final = Decimal("18.0")
_UPS_TAIL_PATTERN: Final = re.compile(r"^N[0-9]{3}UP$", re.IGNORECASE)
_TYPE2_TAIL_CHARACTERS_PATTERN: Final = re.compile(r"^[A-Z0-9-]+$")
_TYPE2_TAIL_ALPHANUMERIC_PATTERN: Final = re.compile(r"[A-Z0-9]")
_TYPE1_NOTE_REFERENCE_PATTERN: Final = re.compile(
    r"\b(?:type\s+(?:i|1)|t\s*1)\b"
)
_APPLICATION_NOTE_WORDING_PATTERN: Final = re.compile(
    r"\b(?:applied|sprayed|completed|performed|done)\b"
)
_TRUCK_NOTE_IDENTIFIER_PATTERN: Final = re.compile(
    r"\btruck\s+(?:(?:no|number)\s+)?(?P<number>[0-9]+)\b"
)
_WHOLE_NUMBER_IDENTIFIER_PATTERN: Final = re.compile(r"^[0-9]+$")

_APPLICATION_DATE_FORMATS: Final[tuple[str, ...]] = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%Y/%m/%d",
    "%m/%d/%y",
)
_DATE_CREATED_FORMATS: Final[tuple[str, ...]] = (
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M:%S.%f",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%Y %I:%M:%S %p",
    "%m/%d/%Y %I:%M:%S.%f %p",
)
@dataclass(frozen=True, slots=True)
class RuleDetail:
    """One immutable label/value pair shown with an audit exception."""

    label: str
    value: str


@dataclass(frozen=True, slots=True)
class AuditException:
    """One immutable rule failure tied to an original CSV source row."""

    rule_id: str
    rule_name: str
    exception_message: str
    source_row_number: int
    record_id: str
    application_number: str
    gateway_code: str
    aircraft_type: str
    tail_number: str
    application_date: str
    start_time: str
    date_created: str
    truck_number: str
    operator: str
    driver: str
    details: tuple[RuleDetail, ...]


@dataclass(frozen=True, slots=True)
class UnableToEvaluate:
    """A non-exception warning for one rule evaluation that could not run."""

    rule_id: str
    rule_name: str
    source_row_number: int
    record_id: str
    invalid_fields: tuple[str, ...]
    message: str


@dataclass(frozen=True, slots=True)
class AuditResult:
    """Immutable aggregate from one complete in-memory CSV audit."""

    filename: str
    rows_audited: int
    rules_executed: int
    active_settings_profile_name: str
    exceptions: tuple[AuditException, ...]
    unable_to_evaluate: tuple[UnableToEvaluate, ...]

    @property
    def exception_count(self) -> int:
        return len(self.exceptions)

    @property
    def unable_to_evaluate_count(self) -> int:
        return len(self.unable_to_evaluate)

    @property
    def unable_to_evaluate_row_count(self) -> int:
        return len(
            {
                warning.source_row_number
                for warning in self.unable_to_evaluate
            }
        )


@dataclass(frozen=True, slots=True)
class AdjustedRateCalculation:
    """Validated Decimal inputs and output for an adjusted fluid rate."""

    usage_text: str
    process_time_text: str
    usage: Decimal
    recorded_minutes: Decimal
    adjusted_minutes: Decimal
    adjusted_rate: Decimal
    configured_maximum: Decimal
    exceeds_maximum: bool


@dataclass(frozen=True, slots=True)
class EventTimeCalculation:
    """Validated inputs and output for one event-time calculation."""

    type1_used: bool
    type4_used: bool
    type1_usage_text: str
    type4_usage_text: str
    type1_usage: Decimal | None
    type4_usage: Decimal | None
    process_time1_text: str | None
    process_time4_text: str | None
    process_time1: Decimal | None
    process_time4: Decimal | None
    include_gap: bool
    gap_minutes: int | None
    gap_crossed_midnight: bool
    overlap_zero_gap: bool
    type1_end_text: str | None
    type4_start_text: str | None
    calculated_minutes: Decimal
    configured_maximum: int
    minutes_over: Decimal


def run_audit(
    imported_csv: CSVImportResult,
    active_settings: SettingsDefinition,
) -> AuditResult:
    """Execute every implemented rule against every imported row."""
    exceptions: list[AuditException] = []
    warnings: list[UnableToEvaluate] = []

    for source_row in imported_csv.rows:
        timestamps, invalid_fields = _parse_local_timestamps(source_row)
        if timestamps is None:
            for rule in _TIMESTAMP_RULES:
                warnings.append(
                    _unable_to_evaluate(
                        source_row,
                        rule,
                        invalid_fields,
                        message=(
                            "Required local timestamp values are blank or "
                            f"invalid: {', '.join(invalid_fields)}."
                        ),
                    )
                )
        else:
            event_timestamp, entry_timestamp = timestamps
            if entry_timestamp < event_timestamp:
                exceptions.append(
                    _rule_001_exception(
                        source_row,
                        event_timestamp - entry_timestamp,
                    )
                )

            threshold = timedelta(
                hours=active_settings.late_entry_threshold_hours
            )
            delay = entry_timestamp - event_timestamp
            if delay >= threshold:
                exceptions.append(
                    _rule_002_exception(
                        source_row,
                        threshold_hours=(
                            active_settings.late_entry_threshold_hours
                        ),
                        delay=delay,
                        beyond_threshold=delay - threshold,
                    )
                )

        type1_exceptions, type1_warnings = _evaluate_type1_rules(
            source_row,
            active_settings,
        )
        exceptions.extend(type1_exceptions)
        warnings.extend(type1_warnings)

        type4_exceptions, type4_warnings = _evaluate_type4_rule(
            source_row,
            active_settings,
        )
        exceptions.extend(type4_exceptions)
        warnings.extend(type4_warnings)

        gap_exceptions, gap_warnings = _evaluate_step_gap_rule(
            source_row,
            active_settings,
        )
        exceptions.extend(gap_exceptions)
        warnings.extend(gap_warnings)

        precipitation_exceptions, precipitation_warnings = (
            _evaluate_precipitation_rule(source_row)
        )
        exceptions.extend(precipitation_exceptions)
        warnings.extend(precipitation_warnings)

        type1_rate_exceptions, type1_rate_warnings = (
            _evaluate_type1_rate_rule(source_row, active_settings)
        )
        exceptions.extend(type1_rate_exceptions)
        warnings.extend(type1_rate_warnings)

        type4_rate_exceptions, type4_rate_warnings = (
            _evaluate_type4_rate_rule(source_row, active_settings)
        )
        exceptions.extend(type4_rate_exceptions)
        warnings.extend(type4_rate_warnings)

        event_time_exceptions, event_time_warnings = (
            _evaluate_event_time_rule(source_row, active_settings)
        )
        exceptions.extend(event_time_exceptions)
        warnings.extend(event_time_warnings)

        concentration_exceptions, concentration_warnings = (
            _evaluate_type4_concentration_rule(source_row, active_settings)
        )
        exceptions.extend(concentration_exceptions)
        warnings.extend(concentration_warnings)

        tail_exceptions, tail_warnings = _evaluate_tail_number_rule(source_row)
        exceptions.extend(tail_exceptions)
        warnings.extend(tail_warnings)

        overlap_exceptions, overlap_warnings = _evaluate_pass_overlap_rule(
            source_row
        )
        exceptions.extend(overlap_exceptions)
        warnings.extend(overlap_warnings)

        explanation_exceptions, explanation_warnings = (
            _evaluate_type4_without_type1_rule(source_row)
        )
        exceptions.extend(explanation_exceptions)
        warnings.extend(explanation_warnings)

    return AuditResult(
        filename=imported_csv.filename,
        rows_audited=imported_csv.row_count,
        rules_executed=len(EXECUTED_RULES),
        active_settings_profile_name=active_settings.name,
        exceptions=tuple(
            sorted(
                exceptions,
                key=lambda exception: (
                    exception.source_row_number,
                    exception.rule_id,
                ),
            )
        ),
        unable_to_evaluate=tuple(
            sorted(
                warnings,
                key=lambda warning: (
                    warning.source_row_number,
                    warning.rule_id,
                ),
            )
        ),
    )


def _parse_local_timestamps(
    source_row: CSVSourceRow,
) -> tuple[tuple[datetime, datetime] | None, tuple[str, ...]]:
    application_date = _parse_with_formats(
        source_row.get("ApplicationDate"),
        _APPLICATION_DATE_FORMATS,
    )
    start_time = parse_military_time(source_row.get("StartTime"))
    date_created = _parse_with_formats(
        source_row.get("DateCreated"),
        _DATE_CREATED_FORMATS,
    )

    invalid_fields = tuple(
        field_name
        for field_name, value in (
            ("ApplicationDate", application_date),
            ("StartTime", start_time),
            ("DateCreated", date_created),
        )
        if value is None
    )
    if invalid_fields:
        return None, invalid_fields

    event_timestamp = datetime.combine(
        application_date.date(),
        start_time,
    )
    return (event_timestamp, date_created), ()


def _parse_with_formats(
    source_value: str,
    formats: tuple[str, ...],
) -> datetime | None:
    value = source_value.strip()
    if not value:
        return None

    for timestamp_format in formats:
        try:
            return datetime.strptime(value, timestamp_format)
        except ValueError:
            continue
    return None


def _unable_to_evaluate(
    source_row: CSVSourceRow,
    rule: RuleDefinition,
    invalid_fields: tuple[str, ...],
    *,
    message: str,
) -> UnableToEvaluate:
    return UnableToEvaluate(
        rule_id=rule.rule_id,
        rule_name=rule.name,
        source_row_number=source_row.source_row_number,
        record_id=source_row.get("RecordID"),
        invalid_fields=invalid_fields,
        message=message,
    )


def _evaluate_type1_rules(
    source_row: CSVSourceRow,
    active_settings: SettingsDefinition,
) -> tuple[list[AuditException], list[UnableToEvaluate]]:
    """Evaluate the two chart-backed rules independently of timestamp rules."""
    exceptions: list[AuditException] = []
    warnings: list[UnableToEvaluate] = []
    type1_used_text = source_row.get("Type1Used")

    if not type1_used_text.strip():
        return exceptions, warnings

    type1_used = _parse_decimal(type1_used_text)
    if type1_used is None:
        return exceptions, [
            _unable_to_evaluate(
                source_row,
                rule,
                ("Type1Used",),
                message=(
                    "Type1Used is malformed, so Type I rule applicability "
                    "could not be determined."
                ),
            )
            for rule in _TYPE1_RULES
        ]
    if type1_used <= 0:
        return exceptions, warnings

    profile = get_type1_fluid_profile(active_settings.type1_fluid)
    if profile is None:
        return exceptions, [
            _unable_to_evaluate(
                source_row,
                rule,
                ("Type I fluid setting",),
                message=(
                    "The selected Type I fluid does not have an available "
                    f"manufacturer chart: {active_settings.type1_fluid}."
                ),
            )
            for rule in _TYPE1_RULES
        ]

    concentration_text = source_row.get("Type1Concentration")
    concentration_decimal = _parse_decimal(concentration_text)
    if (
        concentration_decimal is None
        or concentration_decimal
        != concentration_decimal.to_integral_value()
    ):
        return exceptions, [
            _unable_to_evaluate(
                source_row,
                rule,
                ("Type1Concentration",),
                message=(
                    "Type1Concentration must be a supported whole-number "
                    "percentage."
                ),
            )
            for rule in _TYPE1_RULES
        ]

    available_concentrations = profile.freezing_points.keys()
    minimum_concentration = min(available_concentrations)
    maximum_concentration = max(available_concentrations)
    if (
        concentration_decimal < minimum_concentration
        or concentration_decimal > maximum_concentration
    ):
        return exceptions, [
            _unable_to_evaluate(
                source_row,
                rule,
                ("Type1Concentration",),
                message=(
                    f"Type1Concentration {concentration_text} is outside the "
                    f"available {minimum_concentration}–"
                    f"{maximum_concentration}% manufacturer chart."
                ),
            )
            for rule in _TYPE1_RULES
        ]

    concentration = int(concentration_decimal)
    expected_freeze_point = profile.freeze_point_for(concentration)
    if expected_freeze_point is None:
        return exceptions, [
            _unable_to_evaluate(
                source_row,
                rule,
                ("Type1Concentration",),
                message=(
                    f"Type1Concentration {concentration_text} is not available "
                    f"in the {profile.name} manufacturer chart."
                ),
            )
            for rule in _TYPE1_RULES
        ]

    entered_freeze_point_text = source_row.get("FreezingPoint1")
    entered_freeze_point = _parse_decimal(entered_freeze_point_text)
    if entered_freeze_point is None:
        warnings.append(
            _unable_to_evaluate(
                source_row,
                _RULE_003,
                ("FreezingPoint1",),
                message=(
                    "FreezingPoint1 is blank or malformed, so it could not be "
                    "compared with the manufacturer chart."
                ),
            )
        )
    elif entered_freeze_point != expected_freeze_point:
        exceptions.append(
            _rule_003_exception(
                source_row,
                fluid_name=profile.name,
                concentration=concentration,
                entered_freeze_point_text=entered_freeze_point_text,
                expected_freeze_point=expected_freeze_point,
            )
        )

    ambient_temperature_text = source_row.get("AmbientTemp")
    ambient_temperature = _parse_decimal(ambient_temperature_text)
    if ambient_temperature is None:
        warnings.append(
            _unable_to_evaluate(
                source_row,
                _RULE_004,
                ("AmbientTemp",),
                message=(
                    "AmbientTemp is blank or malformed, so the Type I buffer "
                    "could not be calculated."
                ),
            )
        )
    else:
        actual_buffer = ambient_temperature - expected_freeze_point
        if actual_buffer < _REQUIRED_TYPE1_BUFFER:
            exceptions.append(
                _rule_004_exception(
                    source_row,
                    fluid_name=profile.name,
                    concentration=concentration,
                    ambient_temperature_text=ambient_temperature_text,
                    expected_freeze_point=expected_freeze_point,
                    actual_buffer=actual_buffer,
                )
            )

    return exceptions, warnings


def _parse_decimal(source_value: str) -> Decimal | None:
    value = source_value.strip()
    if not value:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _parse_concentration(source_value: str) -> Decimal | None:
    """Parse a finite Decimal with one optional trailing percent sign."""
    value = source_value.strip()
    if not value:
        return None

    percent_count = value.count("%")
    if percent_count:
        if percent_count != 1 or not value.endswith("%"):
            return None
        value = value[:-1].strip()
        if not value:
            return None

    return _parse_decimal(value)


def _evaluate_type1_rate_rule(
    source_row: CSVSourceRow,
    active_settings: SettingsDefinition,
) -> tuple[list[AuditException], list[UnableToEvaluate]]:
    """Evaluate adjusted Type I rate independently of other Type I rules."""
    calculation, warning = _evaluate_adjusted_rate(
        source_row,
        active_settings,
        rule=_RULE_008,
        usage_field="Type1Used",
        process_time_field="ProcessTime1",
        maximum_setting_name="max_type1_rate_gpm",
        maximum_setting_label="Maximum Type I rate setting",
    )
    if warning is not None:
        return [], [warning]
    if calculation is None or not calculation.exceeds_maximum:
        return [], []
    return [_rule_008_exception(source_row, calculation)], []


def _evaluate_type4_rate_rule(
    source_row: CSVSourceRow,
    active_settings: SettingsDefinition,
) -> tuple[list[AuditException], list[UnableToEvaluate]]:
    """Evaluate adjusted Type IV rate independently of other Type IV rules."""
    calculation, warning = _evaluate_adjusted_rate(
        source_row,
        active_settings,
        rule=_RULE_009,
        usage_field="Type4Used",
        process_time_field="ProcessTime4",
        maximum_setting_name="max_type4_rate_gpm",
        maximum_setting_label="Maximum Type IV rate setting",
    )
    if warning is not None:
        return [], [warning]
    if calculation is None or not calculation.exceeds_maximum:
        return [], []
    return [_rule_009_exception(source_row, calculation)], []


def _evaluate_adjusted_rate(
    source_row: CSVSourceRow,
    active_settings: SettingsDefinition,
    *,
    rule: RuleDefinition,
    usage_field: str,
    process_time_field: str,
    maximum_setting_name: str,
    maximum_setting_label: str,
) -> tuple[AdjustedRateCalculation | None, UnableToEvaluate | None]:
    """Validate and calculate one adjusted fluid rate for reusable rate rules."""
    usage_text = source_row.get(usage_field)
    if not usage_text.strip():
        return None, None

    usage = _parse_decimal(usage_text)
    if usage is None:
        return None, _unable_to_evaluate(
            source_row,
            rule,
            (usage_field,),
            message=(
                f"{usage_field} is malformed or non-finite, so "
                f"{rule.rule_id} applicability could not be determined."
            ),
        )
    if usage <= 0:
        return None, None

    process_time_text = source_row.get(process_time_field)
    recorded_minutes = _parse_decimal(process_time_text)
    if (
        recorded_minutes is None
        or recorded_minutes < 0
        or recorded_minutes != recorded_minutes.to_integral_value()
    ):
        return None, _unable_to_evaluate(
            source_row,
            rule,
            (process_time_field,),
            message=(
                f"{process_time_field} must be a finite, nonnegative, "
                "numerically whole-minute value when positive fluid usage "
                "is recorded."
            ),
        )

    configured_maximum = _valid_positive_decimal_setting(
        active_settings,
        maximum_setting_name,
    )
    if configured_maximum is None:
        return None, _unable_to_evaluate(
            source_row,
            rule,
            (maximum_setting_label,),
            message=(
                f"{maximum_setting_label} must be an available, finite, "
                "positive Decimal value."
            ),
        )

    adjusted_minutes = recorded_minutes + Decimal(1)
    precision = max(
        28,
        len(usage.as_tuple().digits)
        + len(adjusted_minutes.as_tuple().digits)
        + len(configured_maximum.as_tuple().digits)
        + 10,
    )
    exponent_limit = (
        abs(usage.adjusted())
        + abs(adjusted_minutes.adjusted())
        + abs(configured_maximum.adjusted())
        + 10
    )
    with localcontext() as decimal_context:
        decimal_context.prec = precision
        decimal_context.Emax = max(decimal_context.Emax, exponent_limit)
        decimal_context.Emin = min(decimal_context.Emin, -exponent_limit)
        adjusted_rate = usage / adjusted_minutes
        maximum_allowed_usage = configured_maximum * adjusted_minutes
    return (
        AdjustedRateCalculation(
            usage_text=usage_text,
            process_time_text=process_time_text,
            usage=usage,
            recorded_minutes=recorded_minutes,
            adjusted_minutes=adjusted_minutes,
            adjusted_rate=adjusted_rate,
            configured_maximum=configured_maximum,
            exceeds_maximum=usage > maximum_allowed_usage,
        ),
        None,
    )


def _valid_positive_decimal_setting(
    active_settings: SettingsDefinition,
    setting_name: str,
) -> Decimal | None:
    value = getattr(active_settings, setting_name, None)
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or value <= 0
    ):
        return None
    return value


def _evaluate_event_time_rule(
    source_row: CSVSourceRow,
    active_settings: SettingsDefinition,
) -> tuple[list[AuditException], list[UnableToEvaluate]]:
    """Evaluate original whole-minute process times and an optional step gap."""
    usage_values: dict[str, Decimal | None] = {}
    used_steps: dict[str, bool] = {}
    invalid_usage_fields: list[str] = []

    for field_name in ("Type1Used", "Type4Used"):
        source_text = source_row.get(field_name)
        if not source_text.strip():
            usage_values[field_name] = None
            used_steps[field_name] = False
            continue

        parsed_usage = _parse_decimal(source_text)
        if parsed_usage is None:
            invalid_usage_fields.append(field_name)
            continue
        usage_values[field_name] = parsed_usage
        used_steps[field_name] = parsed_usage > 0

    if invalid_usage_fields:
        invalid_fields = tuple(invalid_usage_fields)
        return [], [
            _unable_to_evaluate(
                source_row,
                _RULE_010,
                invalid_fields,
                message=(
                    "Event-time applicability could not be determined because "
                    "these usage values are malformed or non-finite: "
                    f"{', '.join(invalid_fields)}."
                ),
            )
        ]

    type1_used = used_steps["Type1Used"]
    type4_used = used_steps["Type4Used"]
    if not type1_used and not type4_used:
        return [], []

    process_values: dict[str, Decimal] = {}
    process_texts: dict[str, str] = {}
    invalid_process_fields: list[str] = []
    for is_used, field_name in (
        (type1_used, "ProcessTime1"),
        (type4_used, "ProcessTime4"),
    ):
        if not is_used:
            continue
        source_text = source_row.get(field_name)
        process_time = _parse_decimal(source_text)
        if (
            process_time is None
            or process_time < 0
            or process_time != process_time.to_integral_value()
        ):
            invalid_process_fields.append(field_name)
            continue
        process_texts[field_name] = source_text
        process_values[field_name] = process_time

    if invalid_process_fields:
        invalid_fields = tuple(invalid_process_fields)
        return [], [
            _unable_to_evaluate(
                source_row,
                _RULE_010,
                invalid_fields,
                message=(
                    "Every positively used step requires a finite, "
                    "nonnegative, numerically whole-minute process time. "
                    f"Invalid fields: {', '.join(invalid_fields)}."
                ),
            )
        ]

    configured_maximum = getattr(
        active_settings,
        "max_event_time_minutes",
        None,
    )
    if (
        type(configured_maximum) is not int
        or not 1 <= configured_maximum <= 999
    ):
        return [], [
            _unable_to_evaluate(
                source_row,
                _RULE_010,
                ("Maximum event time setting",),
                message=(
                    "Maximum event time must be an available whole number "
                    "from 1 through 999 minutes."
                ),
            )
        ]

    include_gap = getattr(
        active_settings,
        "include_gap_in_event_time",
        None,
    )
    if type(include_gap) is not bool:
        return [], [
            _unable_to_evaluate(
                source_row,
                _RULE_010,
                ("Include Gap setting",),
                message="Include Gap must be an available On or Off value.",
            )
        ]

    gap_minutes: int | None = None
    gap_crossed_midnight = False
    overlap_zero_gap = False
    type1_end_text: str | None = None
    type4_start_text: str | None = None
    if include_gap and type1_used and type4_used:
        type1_end_text = source_row.get("EndTime1")
        type4_start_text = source_row.get("StartTime4")
        type1_end = parse_military_time(type1_end_text)
        type4_start = parse_military_time(type4_start_text)
        invalid_step_fields = tuple(
            field_name
            for field_name, value in (
                ("EndTime1", type1_end),
                ("StartTime4", type4_start),
            )
            if value is None
        )
        if invalid_step_fields:
            return [], [
                _unable_to_evaluate(
                    source_row,
                    _RULE_010,
                    invalid_step_fields,
                    message=(
                        "Include Gap is On, so both step times must be valid "
                        "whole-minute HH:MM values. Invalid fields: "
                        f"{', '.join(invalid_step_fields)}."
                    ),
                )
            ]

        direct_gap = elapsed_minutes(type1_end, type4_start)
        if direct_gap is not None:
            gap_minutes = direct_gap
        else:
            event_start = parse_military_time(source_row.get("StartTime"))
            event_end = parse_military_time(source_row.get("EndTime"))
            invalid_event_fields = tuple(
                field_name
                for field_name, value in (
                    ("StartTime", event_start),
                    ("EndTime", event_end),
                )
                if value is None
            )
            if invalid_event_fields:
                return [], [
                    _unable_to_evaluate(
                        source_row,
                        _RULE_010,
                        invalid_event_fields,
                        message=(
                            "The overall event time is needed to distinguish "
                            "an overnight included gap from an overlap. "
                            "Invalid fields: "
                            f"{', '.join(invalid_event_fields)}."
                        ),
                    )
                ]

            if crosses_midnight(event_start, event_end):
                gap_crossed_midnight = True
                gap_minutes = elapsed_minutes(
                    type1_end,
                    type4_start,
                    crossed_midnight=True,
                )
            else:
                overlap_zero_gap = True
                gap_minutes = 0

    calculation_parts = tuple(process_values.values())
    if gap_minutes is not None:
        calculation_parts = (
            *calculation_parts,
            Decimal(gap_minutes),
        )
    precision = max(
        28,
        sum(len(value.as_tuple().digits) for value in calculation_parts)
        + 10,
    )
    exponent_limit = (
        sum(abs(value.adjusted()) for value in calculation_parts) + 10
    )
    with localcontext() as decimal_context:
        decimal_context.prec = precision
        decimal_context.Emax = max(decimal_context.Emax, exponent_limit)
        decimal_context.Emin = min(decimal_context.Emin, -exponent_limit)
        calculated_minutes = sum(calculation_parts, Decimal(0))
        minutes_over = calculated_minutes - Decimal(configured_maximum)

    if calculated_minutes <= configured_maximum:
        return [], []

    calculation = EventTimeCalculation(
        type1_used=type1_used,
        type4_used=type4_used,
        type1_usage_text=source_row.get("Type1Used"),
        type4_usage_text=source_row.get("Type4Used"),
        type1_usage=usage_values.get("Type1Used"),
        type4_usage=usage_values.get("Type4Used"),
        process_time1_text=process_texts.get("ProcessTime1"),
        process_time4_text=process_texts.get("ProcessTime4"),
        process_time1=process_values.get("ProcessTime1"),
        process_time4=process_values.get("ProcessTime4"),
        include_gap=include_gap,
        gap_minutes=gap_minutes,
        gap_crossed_midnight=gap_crossed_midnight,
        overlap_zero_gap=overlap_zero_gap,
        type1_end_text=type1_end_text,
        type4_start_text=type4_start_text,
        calculated_minutes=calculated_minutes,
        configured_maximum=configured_maximum,
        minutes_over=minutes_over,
    )
    return [_rule_010_exception(source_row, calculation)], []


def _evaluate_type4_rule(
    source_row: CSVSourceRow,
    active_settings: SettingsDefinition,
) -> tuple[list[AuditException], list[UnableToEvaluate]]:
    """Evaluate the Type IV BRIX range rule independently of other rules."""
    exceptions: list[AuditException] = []
    warnings: list[UnableToEvaluate] = []
    type4_used_text = source_row.get("Type4Used")

    if not type4_used_text.strip():
        return exceptions, warnings

    type4_used = _parse_decimal(type4_used_text)
    if type4_used is None:
        warnings.append(
            _unable_to_evaluate(
                source_row,
                _RULE_005,
                ("Type4Used",),
                message=(
                    "Type4Used is malformed, so Type IV rule applicability "
                    "could not be determined."
                ),
            )
        )
        return exceptions, warnings
    if type4_used <= 0:
        return exceptions, warnings

    profile = get_type4_fluid_profile(active_settings.type4_fluid)
    if profile is None:
        warnings.append(
            _unable_to_evaluate(
                source_row,
                _RULE_005,
                ("Type IV fluid setting",),
                message=(
                    "The selected Type IV fluid does not have an available "
                    f"BRIX profile: {active_settings.type4_fluid}."
                ),
            )
        )
        return exceptions, warnings

    brix_range = _valid_brix_range(profile)
    if brix_range is None:
        warnings.append(
            _unable_to_evaluate(
                source_row,
                _RULE_005,
                ("Type IV fluid setting",),
                message=(
                    "The selected Type IV fluid profile does not supply a "
                    f"valid BRIX range: {active_settings.type4_fluid}."
                ),
            )
        )
        return exceptions, warnings

    minimum_brix, maximum_brix = brix_range
    entered_brix_text = source_row.get("Type4ABrix")
    entered_brix = _parse_decimal(entered_brix_text)
    if entered_brix is None:
        warnings.append(
            _unable_to_evaluate(
                source_row,
                _RULE_005,
                ("Type4ABrix",),
                message=(
                    "Type4ABrix is blank, malformed, or non-finite, so it "
                    "could not be compared with the acceptable range."
                ),
            )
        )
    elif entered_brix < minimum_brix:
        exceptions.append(
            _rule_005_exception(
                source_row,
                fluid_name=profile.name,
                entered_brix_text=entered_brix_text,
                minimum_brix=minimum_brix,
                maximum_brix=maximum_brix,
                direction="Below",
                amount_outside=minimum_brix - entered_brix,
            )
        )
    elif entered_brix > maximum_brix:
        exceptions.append(
            _rule_005_exception(
                source_row,
                fluid_name=profile.name,
                entered_brix_text=entered_brix_text,
                minimum_brix=minimum_brix,
                maximum_brix=maximum_brix,
                direction="Above",
                amount_outside=entered_brix - maximum_brix,
            )
        )

    return exceptions, warnings


def _valid_brix_range(profile: object) -> tuple[Decimal, Decimal] | None:
    try:
        minimum_brix = profile.minimum_brix
        maximum_brix = profile.maximum_brix
    except AttributeError:
        return None

    if (
        not isinstance(minimum_brix, Decimal)
        or not isinstance(maximum_brix, Decimal)
        or not minimum_brix.is_finite()
        or not maximum_brix.is_finite()
        or minimum_brix > maximum_brix
    ):
        return None
    return minimum_brix, maximum_brix


def _evaluate_type4_concentration_rule(
    source_row: CSVSourceRow,
    active_settings: SettingsDefinition,
) -> tuple[list[AuditException], list[UnableToEvaluate]]:
    """Compare entered Type IV concentration with the active fluid profile."""
    type4_used_text = source_row.get("Type4Used")
    if not type4_used_text.strip():
        return [], []

    type4_used = _parse_decimal(type4_used_text)
    if type4_used is None:
        return [], [
            _unable_to_evaluate(
                source_row,
                _RULE_011,
                ("Type4Used",),
                message=(
                    "Type4Used is malformed or non-finite, so CC-RULE-011 "
                    "applicability could not be determined."
                ),
            )
        ]
    if type4_used <= 0:
        return [], []

    selected_fluid = getattr(active_settings, "type4_fluid", None)
    profile = (
        get_type4_fluid_profile(selected_fluid)
        if isinstance(selected_fluid, str)
        else None
    )
    if profile is None:
        return [], [
            _unable_to_evaluate(
                source_row,
                _RULE_011,
                ("Type IV fluid setting",),
                message=(
                    "The selected Type IV fluid does not have an available "
                    "concentration profile."
                ),
            )
        ]

    required_concentration = _valid_required_concentration(profile)
    if required_concentration is None:
        return [], [
            _unable_to_evaluate(
                source_row,
                _RULE_011,
                ("Type IV fluid setting",),
                message=(
                    "The selected Type IV fluid profile does not supply a "
                    "valid required concentration."
                ),
            )
        ]

    entered_text = source_row.get("Type4AConcentration")
    entered_concentration = _parse_concentration(entered_text)
    if entered_concentration is None:
        return [], [
            _unable_to_evaluate(
                source_row,
                _RULE_011,
                ("Type4AConcentration",),
                message=(
                    "Type4AConcentration must be a finite numeric value with "
                    "at most one optional trailing percent sign."
                ),
            )
        ]

    if entered_concentration == required_concentration:
        return [], []

    return [
        _rule_011_exception(
            source_row,
            fluid_name=profile.name,
            entered_concentration_text=entered_text,
            required_concentration=required_concentration,
        )
    ], []


def _valid_required_concentration(profile: object) -> Decimal | None:
    try:
        required_concentration = profile.required_concentration
    except AttributeError:
        return None

    if (
        not isinstance(required_concentration, Decimal)
        or not required_concentration.is_finite()
        or not Decimal(0) <= required_concentration <= Decimal(100)
    ):
        return None
    return required_concentration


def _evaluate_tail_number_rule(
    source_row: CSVSourceRow,
) -> tuple[list[AuditException], list[UnableToEvaluate]]:
    """Validate a trimmed tail deterministically for AircraftType 0, 1, or 2."""
    aircraft_type_text = source_row.get("AircraftType")
    aircraft_type = _parse_decimal(aircraft_type_text)
    if (
        aircraft_type is None
        or aircraft_type != aircraft_type.to_integral_value()
        or aircraft_type not in (Decimal(0), Decimal(1), Decimal(2))
    ):
        return [], [
            _unable_to_evaluate(
                source_row,
                _RULE_012,
                ("AircraftType",),
                message=(
                    "AircraftType must be a finite, numerically whole value "
                    "of 0, 1, or 2 for tail-number validation."
                ),
            )
        ]

    aircraft_type_number = int(aircraft_type)
    tail_text = source_row.get("TailNumber")
    normalized_tail = tail_text.strip().upper()
    notes_text = source_row.get("Notes")
    failure_reasons: list[str] = []

    if aircraft_type_number == 0:
        if normalized_tail:
            failure_reasons.append(
                "TailNumber must be blank for AircraftType 0"
            )
        if not notes_text.strip():
            failure_reasons.append("Notes are required for AircraftType 0")
    elif aircraft_type_number == 1:
        if _UPS_TAIL_PATTERN.fullmatch(normalized_tail) is None:
            failure_reasons.append("Does not match UPS NxxxUP format")
    else:
        if not normalized_tail:
            failure_reasons.append(
                "TailNumber must not be blank for AircraftType 2"
            )
        elif _UPS_TAIL_PATTERN.fullmatch(normalized_tail) is not None:
            failure_reasons.append(
                "AircraftType 2 must not use UPS format"
            )
        elif (
            _TYPE2_TAIL_CHARACTERS_PATTERN.fullmatch(normalized_tail) is None
        ):
            failure_reasons.append("Contains unsupported characters")
        elif (
            _TYPE2_TAIL_ALPHANUMERIC_PATTERN.search(normalized_tail) is None
        ):
            failure_reasons.append(
                "Does not contain a letter or number"
            )

    if not failure_reasons:
        return [], []

    return [
        _rule_012_exception(
            source_row,
            aircraft_type_number=aircraft_type_number,
            failure_reasons=tuple(failure_reasons),
        )
    ], []


def _evaluate_pass_overlap_rule(
    source_row: CSVSourceRow,
) -> tuple[list[AuditException], list[UnableToEvaluate]]:
    """Detect a same-day Type IV start before the Type I pass ends."""
    parsed_usage: dict[str, Decimal] = {}
    invalid_usage_fields: list[str] = []
    has_nonpositive_or_blank_usage = False

    for field_name in ("Type1Used", "Type4Used"):
        source_text = source_row.get(field_name)
        if not source_text.strip():
            has_nonpositive_or_blank_usage = True
            continue

        usage = _parse_decimal(source_text)
        if usage is None:
            invalid_usage_fields.append(field_name)
        elif usage <= 0:
            has_nonpositive_or_blank_usage = True
        else:
            parsed_usage[field_name] = usage

    if invalid_usage_fields:
        invalid_fields = tuple(invalid_usage_fields)
        return [], [
            _unable_to_evaluate(
                source_row,
                _RULE_013,
                invalid_fields,
                message=(
                    "Pass-overlap applicability could not be determined "
                    "because these usage values are malformed or non-finite: "
                    f"{', '.join(invalid_fields)}."
                ),
            )
        ]
    if has_nonpositive_or_blank_usage or len(parsed_usage) != 2:
        return [], []

    type1_end_text = source_row.get("EndTime1")
    type4_start_text = source_row.get("StartTime4")
    type1_end = parse_military_time(type1_end_text)
    type4_start = parse_military_time(type4_start_text)
    invalid_step_fields = tuple(
        field_name
        for field_name, value in (
            ("EndTime1", type1_end),
            ("StartTime4", type4_start),
        )
        if value is None
    )
    if invalid_step_fields:
        return [], [
            _unable_to_evaluate(
                source_row,
                _RULE_013,
                invalid_step_fields,
                message=(
                    "Pass overlap requires valid whole-minute HH:MM values "
                    "for EndTime1 and StartTime4. Invalid fields: "
                    f"{', '.join(invalid_step_fields)}."
                ),
            )
        ]

    if elapsed_minutes(type1_end, type4_start) is not None:
        return [], []

    overall_start_text = source_row.get("StartTime")
    overall_end_text = source_row.get("EndTime")
    overall_start = parse_military_time(overall_start_text)
    overall_end = parse_military_time(overall_end_text)
    invalid_overall_fields = tuple(
        field_name
        for field_name, value in (
            ("StartTime", overall_start),
            ("EndTime", overall_end),
        )
        if value is None
    )
    if invalid_overall_fields:
        return [], [
            _unable_to_evaluate(
                source_row,
                _RULE_013,
                invalid_overall_fields,
                message=(
                    "StartTime4 is earlier than EndTime1, so valid overall "
                    "StartTime and EndTime values are required to determine "
                    "whether the event crossed midnight. Invalid fields: "
                    f"{', '.join(invalid_overall_fields)}."
                ),
            )
        ]

    if crosses_midnight(overall_start, overall_end):
        return [], []

    overlap_minutes = elapsed_minutes(type4_start, type1_end)
    if overlap_minutes is None:
        raise RuntimeError("Validated same-day overlap must have a duration.")

    return [
        _rule_013_exception(
            source_row,
            overlap_minutes=overlap_minutes,
        )
    ], []


def _evaluate_type4_without_type1_rule(
    source_row: CSVSourceRow,
) -> tuple[list[AuditException], list[UnableToEvaluate]]:
    """Require a deterministic other-truck explanation for Type IV-only use."""
    aircraft_type_text = source_row.get("AircraftType")
    aircraft_type = _parse_decimal(aircraft_type_text)
    aircraft_type_state = "invalid"
    if (
        aircraft_type is not None
        and aircraft_type == aircraft_type.to_integral_value()
        and aircraft_type in (Decimal(0), Decimal(1), Decimal(2))
    ):
        aircraft_type_state = (
            "exempt" if aircraft_type == 0 else "eligible"
        )

    usage_states: dict[str, str] = {}
    for field_name in ("Type1Used", "Type4Used"):
        source_text = source_row.get(field_name)
        if not source_text.strip():
            usage_states[field_name] = "inactive"
            continue
        parsed_usage = _parse_decimal(source_text)
        if parsed_usage is None:
            usage_states[field_name] = "invalid"
        elif parsed_usage > 0:
            usage_states[field_name] = "positive"
        else:
            usage_states[field_name] = "inactive"

    if (
        aircraft_type_state == "exempt"
        or usage_states["Type4Used"] == "inactive"
        or usage_states["Type1Used"] == "positive"
    ):
        return [], []

    invalid_applicability_fields = tuple(
        field_name
        for field_name, is_invalid in (
            ("AircraftType", aircraft_type_state == "invalid"),
            ("Type1Used", usage_states["Type1Used"] == "invalid"),
            ("Type4Used", usage_states["Type4Used"] == "invalid"),
        )
        if is_invalid
    )
    if invalid_applicability_fields:
        return [], [
            _unable_to_evaluate(
                source_row,
                _RULE_014,
                invalid_applicability_fields,
                message=(
                    "Type IV-only explanation applicability could not be "
                    "determined because these values are invalid, malformed, "
                    "or non-finite: "
                    f"{', '.join(invalid_applicability_fields)}."
                ),
            )
        ]

    current_truck_text = source_row.get("TruckNumber")
    normalized_current_truck = current_truck_text.strip()
    if (
        _WHOLE_NUMBER_IDENTIFIER_PATTERN.fullmatch(
            normalized_current_truck
        )
        is None
    ):
        return [], [
            _unable_to_evaluate(
                source_row,
                _RULE_014,
                ("TruckNumber",),
                message=(
                    "Current TruckNumber must contain only whole-number "
                    "digits so documented truck identifiers can be compared."
                ),
            )
        ]

    current_truck_number = _canonical_whole_number(
        normalized_current_truck
    )
    notes_text = source_row.get("Notes")
    normalized_notes = _normalize_note_text(notes_text)
    has_type1_reference = (
        _TYPE1_NOTE_REFERENCE_PATTERN.search(normalized_notes) is not None
    )
    has_application_wording = (
        _APPLICATION_NOTE_WORDING_PATTERN.search(normalized_notes) is not None
    )
    documented_truck_texts = tuple(
        match.group("number")
        for match in _TRUCK_NOTE_IDENTIFIER_PATTERN.finditer(
            normalized_notes
        )
    )
    documented_truck_numbers = tuple(
        _canonical_whole_number(identifier)
        for identifier in documented_truck_texts
    )

    failure_reasons: list[str] = []
    if not notes_text.strip():
        failure_reasons.append("Notes are blank")
    if not has_type1_reference:
        failure_reasons.append("Missing Type I reference")
    if not has_application_wording:
        failure_reasons.append("Missing application wording")
    if not documented_truck_texts:
        failure_reasons.append("Missing documented truck number")
    elif all(
        truck_number == current_truck_number
        for truck_number in documented_truck_numbers
    ):
        failure_reasons.append(
            "Documented truck number matches current TruckNumber"
        )

    if not failure_reasons:
        return [], []

    return [
        _rule_014_exception(
            source_row,
            failure_reasons=tuple(failure_reasons),
            documented_truck_numbers=documented_truck_texts,
        )
    ], []


def _normalize_note_text(source_text: str) -> str:
    """Normalize case, punctuation, and whitespace for exact note matching."""
    punctuation_as_spaces = re.sub(
        r"[^a-z0-9]+",
        " ",
        source_text.casefold(),
    )
    return " ".join(punctuation_as_spaces.split())


def _canonical_whole_number(source_text: str) -> str:
    """Remove insignificant leading zeros without integer conversion."""
    without_leading_zeros = source_text.lstrip("0")
    return without_leading_zeros or "0"


def _evaluate_step_gap_rule(
    source_row: CSVSourceRow,
    active_settings: SettingsDefinition,
) -> tuple[list[AuditException], list[UnableToEvaluate]]:
    """Evaluate the whole-minute gap between positive Type I and Type IV use."""
    exceptions: list[AuditException] = []
    warnings: list[UnableToEvaluate] = []
    malformed_usage_fields: list[str] = []

    for field_name in ("Type1Used", "Type4Used"):
        source_text = source_row.get(field_name)
        if not source_text.strip():
            return exceptions, warnings

        parsed_value = _parse_decimal(source_text)
        if parsed_value is None:
            malformed_usage_fields.append(field_name)
        elif parsed_value <= 0:
            return exceptions, warnings

    if malformed_usage_fields:
        invalid_fields = tuple(malformed_usage_fields)
        warnings.append(
            _unable_to_evaluate(
                source_row,
                _RULE_006,
                invalid_fields,
                message=(
                    "Step-gap applicability could not be determined because "
                    "these usage values are malformed: "
                    f"{', '.join(invalid_fields)}."
                ),
            )
        )
        return exceptions, warnings

    allowed_gap = _valid_allowed_gap_minutes(active_settings)
    if allowed_gap is None:
        warnings.append(
            _unable_to_evaluate(
                source_row,
                _RULE_006,
                ("Allowed Gap setting",),
                message=(
                    "Allowed Gap must be an available whole number from 0 "
                    "through 99 minutes."
                ),
            )
        )
        return exceptions, warnings

    type1_end_text = source_row.get("EndTime1")
    type4_start_text = source_row.get("StartTime4")
    type1_end = parse_military_time(type1_end_text)
    type4_start = parse_military_time(type4_start_text)
    invalid_step_fields = tuple(
        field_name
        for field_name, value in (
            ("EndTime1", type1_end),
            ("StartTime4", type4_start),
        )
        if value is None
    )
    if invalid_step_fields:
        warnings.append(
            _unable_to_evaluate(
                source_row,
                _RULE_006,
                invalid_step_fields,
                message=(
                    "Required whole-minute HH:MM values are blank or invalid: "
                    f"{', '.join(invalid_step_fields)}."
                ),
            )
        )
        return exceptions, warnings

    crossed_midnight = False
    if elapsed_minutes(type1_end, type4_start) is None:
        event_start = parse_military_time(source_row.get("StartTime"))
        event_end = parse_military_time(source_row.get("EndTime"))
        invalid_event_fields = tuple(
            field_name
            for field_name, value in (
                ("StartTime", event_start),
                ("EndTime", event_end),
            )
            if value is None
        )
        if invalid_event_fields:
            warnings.append(
                _unable_to_evaluate(
                    source_row,
                    _RULE_006,
                    invalid_event_fields,
                    message=(
                        "The overall event time is needed to distinguish an "
                        "overnight step gap from an overlap, but these values "
                        "are blank or invalid: "
                        f"{', '.join(invalid_event_fields)}."
                    ),
                )
            )
            return exceptions, warnings

        crossed_midnight = crosses_midnight(event_start, event_end)
        if not crossed_midnight:
            return exceptions, warnings

    actual_gap = elapsed_minutes(
        type1_end,
        type4_start,
        crossed_midnight=crossed_midnight,
    )
    if actual_gap is not None and actual_gap > allowed_gap:
        exceptions.append(
            _rule_006_exception(
                source_row,
                type1_end_text=type1_end_text,
                type4_start_text=type4_start_text,
                actual_gap=actual_gap,
                allowed_gap=allowed_gap,
            )
        )

    return exceptions, warnings


def _valid_allowed_gap_minutes(
    active_settings: SettingsDefinition,
) -> int | None:
    allowed_gap = getattr(active_settings, "allowed_gap_minutes", None)
    if type(allowed_gap) is not int or not 0 <= allowed_gap <= 99:
        return None
    return allowed_gap


def _evaluate_precipitation_rule(
    source_row: CSVSourceRow,
) -> tuple[list[AuditException], list[UnableToEvaluate]]:
    """Evaluate active precipitation independently of settings and profiles."""
    precipitation_text = source_row.get("Precipitation")
    if not has_active_precipitation(precipitation_text):
        return [], []

    type4_used_text = source_row.get("Type4Used")
    if not type4_used_text.strip():
        return [_rule_007_exception(source_row)], []

    type4_used = _parse_decimal(type4_used_text)
    if type4_used is None or type4_used < 0:
        return [], [
            _unable_to_evaluate(
                source_row,
                _RULE_007,
                ("Type4Used",),
                message=(
                    "Type4Used is malformed, non-finite, or negative, so "
                    "recorded Type IV use during active precipitation could "
                    "not be determined."
                ),
            )
        ]
    if type4_used == 0:
        return [_rule_007_exception(source_row)], []

    return [], []


def _rule_001_exception(
    source_row: CSVSourceRow,
    created_before_event: timedelta,
) -> AuditException:
    return _build_exception(
        source_row,
        _RULE_001,
        details=(
            RuleDetail(
                "Application date/time",
                _application_timestamp_source_text(source_row),
            ),
            RuleDetail("Entry date/time", source_row.get("DateCreated")),
            RuleDetail(
                "How far before the application event the entry was created",
                _format_duration(created_before_event),
            ),
        ),
    )


def _rule_002_exception(
    source_row: CSVSourceRow,
    *,
    threshold_hours: int,
    delay: timedelta,
    beyond_threshold: timedelta,
) -> AuditException:
    return _build_exception(
        source_row,
        _RULE_002,
        details=(
            RuleDetail(
                "Application date/time",
                _application_timestamp_source_text(source_row),
            ),
            RuleDetail("Entry date/time", source_row.get("DateCreated")),
            RuleDetail("Configured threshold", f"{threshold_hours} hours"),
            RuleDetail("Actual delay", _format_duration(delay)),
            RuleDetail(
                "Amount beyond the threshold",
                _format_duration(beyond_threshold),
            ),
        ),
    )


def _rule_003_exception(
    source_row: CSVSourceRow,
    *,
    fluid_name: str,
    concentration: int,
    entered_freeze_point_text: str,
    expected_freeze_point: Decimal,
) -> AuditException:
    expected_text = _format_temperature(expected_freeze_point)
    entered_temperature_text = f"{entered_freeze_point_text}°F"
    return _build_exception(
        source_row,
        _RULE_003,
        details=(
            RuleDetail("Selected Type I fluid", fluid_name),
            RuleDetail("Recorded concentration", f"{concentration}%"),
            RuleDetail(
                "Entered freeze point",
                entered_temperature_text,
            ),
            RuleDetail(
                "Expected manufacturer-chart freeze point",
                expected_text,
            ),
            RuleDetail(
                "Comparison",
                (
                    f"Expected {expected_text} at {concentration}% "
                    f"concentration. Entered {entered_temperature_text}."
                ),
            ),
        ),
    )


def _rule_004_exception(
    source_row: CSVSourceRow,
    *,
    fluid_name: str,
    concentration: int,
    ambient_temperature_text: str,
    expected_freeze_point: Decimal,
    actual_buffer: Decimal,
) -> AuditException:
    amount_short = _REQUIRED_TYPE1_BUFFER - actual_buffer
    return _build_exception(
        source_row,
        _RULE_004,
        details=(
            RuleDetail("Selected Type I fluid", fluid_name),
            RuleDetail("Recorded concentration", f"{concentration}%"),
            RuleDetail(
                "Outside air temperature",
                f"{ambient_temperature_text}°F",
            ),
            RuleDetail(
                "Authoritative manufacturer-chart freeze point",
                _format_temperature(expected_freeze_point),
            ),
            RuleDetail(
                "Actual calculated buffer",
                _format_temperature(actual_buffer),
            ),
            RuleDetail(
                "Required buffer",
                _format_temperature(_REQUIRED_TYPE1_BUFFER),
            ),
            RuleDetail(
                "Amount short",
                _format_temperature(amount_short),
            ),
        ),
    )


def _rule_005_exception(
    source_row: CSVSourceRow,
    *,
    fluid_name: str,
    entered_brix_text: str,
    minimum_brix: Decimal,
    maximum_brix: Decimal,
    direction: str,
    amount_outside: Decimal,
) -> AuditException:
    acceptable_range = (
        f"{_format_decimal(minimum_brix)}–"
        f"{_format_decimal(maximum_brix)}"
    )
    direction_text = f"{direction} range"
    amount_text = _format_decimal(amount_outside)
    return _build_exception(
        source_row,
        _RULE_005,
        details=(
            RuleDetail("Selected Type IV fluid", fluid_name),
            RuleDetail("Entered BRIX", entered_brix_text),
            RuleDetail("Acceptable inclusive range", acceptable_range),
            RuleDetail("Range comparison", direction_text),
            RuleDetail(
                f"Amount {direction.lower()} nearest boundary",
                amount_text,
            ),
            RuleDetail(
                "Comparison",
                (
                    f"Entered BRIX: {entered_brix_text}. Acceptable range for "
                    f"{fluid_name}: {acceptable_range}. {direction_text} by "
                    f"{amount_text}."
                ),
            ),
        ),
    )


def _rule_006_exception(
    source_row: CSVSourceRow,
    *,
    type1_end_text: str,
    type4_start_text: str,
    actual_gap: int,
    allowed_gap: int,
) -> AuditException:
    amount_over = actual_gap - allowed_gap
    actual_gap_text = _format_minutes(actual_gap)
    allowed_gap_text = _format_minutes(allowed_gap)
    amount_over_text = _format_minutes(amount_over)
    return _build_exception(
        source_row,
        _RULE_006,
        details=(
            RuleDetail("Type I end time", type1_end_text),
            RuleDetail("Type IV start time", type4_start_text),
            RuleDetail("Actual calculated gap", actual_gap_text),
            RuleDetail("Configured Allowed Gap", allowed_gap_text),
            RuleDetail("Amount over setting", amount_over_text),
            RuleDetail(
                "Comparison",
                (
                    f"Type I ended at {type1_end_text}. Type IV began at "
                    f"{type4_start_text}. Actual gap: {actual_gap_text}. "
                    f"Allowed gap: {allowed_gap_text}. Exceeded by "
                    f"{amount_over_text}."
                ),
            ),
        ),
    )


def _rule_007_exception(source_row: CSVSourceRow) -> AuditException:
    type4_used_text = source_row.get("Type4Used")
    type4_display = type4_used_text if type4_used_text.strip() else "Blank"
    return _build_exception(
        source_row,
        _RULE_007,
        details=(
            RuleDetail(
                "Recorded precipitation",
                source_row.get("Precipitation"),
            ),
            RuleDetail("Type IV amount recorded", type4_display),
            RuleDetail(
                "Finding",
                (
                    "No Type IV fluid was recorded during active "
                    "precipitation."
                ),
            ),
        ),
    )


def _rule_008_exception(
    source_row: CSVSourceRow,
    calculation: AdjustedRateCalculation,
) -> AuditException:
    usage_unit = "gallon" if calculation.usage == 1 else "gallons"
    recorded_time = _format_decimal_minutes(
        calculation.process_time_text,
        calculation.recorded_minutes,
    )
    adjusted_time = _format_decimal_minutes(
        _format_compact_decimal(calculation.adjusted_minutes),
        calculation.adjusted_minutes,
    )
    rate_text = _format_compact_decimal(calculation.adjusted_rate)
    maximum_text = _format_compact_decimal(
        calculation.configured_maximum
    )
    return _build_exception(
        source_row,
        _RULE_008,
        details=(
            RuleDetail(
                "Type I gallons used",
                f"{calculation.usage_text} {usage_unit}",
            ),
            RuleDetail("Recorded ProcessTime1", recorded_time),
            RuleDetail("Adjusted calculation time", adjusted_time),
            RuleDetail(
                "Adjusted Type I rate",
                f"{rate_text} gallons per minute",
            ),
            RuleDetail(
                "Configured maximum Type I rate",
                f"{maximum_text} gallons per minute",
            ),
            RuleDetail(
                "Comparison",
                (
                    f"Adjusted rate {rate_text} gallons per minute exceeds "
                    f"the configured maximum of {maximum_text} gallons per "
                    "minute."
                ),
            ),
        ),
    )


def _rule_009_exception(
    source_row: CSVSourceRow,
    calculation: AdjustedRateCalculation,
) -> AuditException:
    usage_unit = "gallon" if calculation.usage == 1 else "gallons"
    recorded_time = _format_decimal_minutes(
        calculation.process_time_text,
        calculation.recorded_minutes,
    )
    adjusted_time = _format_decimal_minutes(
        _format_compact_decimal(calculation.adjusted_minutes),
        calculation.adjusted_minutes,
    )
    rate_text = _format_compact_decimal(calculation.adjusted_rate)
    maximum_text = _format_compact_decimal(
        calculation.configured_maximum
    )
    return _build_exception(
        source_row,
        _RULE_009,
        details=(
            RuleDetail(
                "Type IV gallons used",
                f"{calculation.usage_text} {usage_unit}",
            ),
            RuleDetail("Recorded ProcessTime4", recorded_time),
            RuleDetail("Adjusted calculation time", adjusted_time),
            RuleDetail(
                "Adjusted Type IV rate",
                f"{rate_text} gallons per minute",
            ),
            RuleDetail(
                "Configured maximum Type IV rate",
                f"{maximum_text} gallons per minute",
            ),
            RuleDetail(
                "Comparison",
                (
                    f"Adjusted rate {rate_text} gallons per minute exceeds "
                    f"the configured maximum of {maximum_text} gallons per "
                    "minute."
                ),
            ),
        ),
    )


def _rule_010_exception(
    source_row: CSVSourceRow,
    calculation: EventTimeCalculation,
) -> AuditException:
    details: list[RuleDetail] = [
        RuleDetail(
            "Type I usage status",
            _event_usage_status(
                calculation.type1_used,
                calculation.type1_usage_text,
                calculation.type1_usage,
            ),
        ),
        RuleDetail(
            "Type IV usage status",
            _event_usage_status(
                calculation.type4_used,
                calculation.type4_usage_text,
                calculation.type4_usage,
            ),
        ),
    ]

    if (
        calculation.type1_used
        and calculation.process_time1_text is not None
        and calculation.process_time1 is not None
    ):
        details.append(
            RuleDetail(
                "ProcessTime1",
                _format_decimal_minutes(
                    calculation.process_time1_text,
                    calculation.process_time1,
                ),
            )
        )
    if (
        calculation.type4_used
        and calculation.process_time4_text is not None
        and calculation.process_time4 is not None
    ):
        details.append(
            RuleDetail(
                "ProcessTime4",
                _format_decimal_minutes(
                    calculation.process_time4_text,
                    calculation.process_time4,
                ),
            )
        )

    details.append(
        RuleDetail(
            "Include Gap setting",
            "On" if calculation.include_gap else "Off",
        )
    )
    if (
        calculation.gap_minutes is not None
        and calculation.type1_end_text is not None
        and calculation.type4_start_text is not None
    ):
        gap_context = " overnight" if calculation.gap_crossed_midnight else ""
        details.append(
            RuleDetail(
                "Included gap",
                (
                    f"{_format_minutes(calculation.gap_minutes)}{gap_context} "
                    f"(EndTime1 {calculation.type1_end_text} to StartTime4 "
                    f"{calculation.type4_start_text})"
                ),
            )
        )
    if calculation.overlap_zero_gap:
        details.append(
            RuleDetail(
                "Overlap handling",
                (
                    f"StartTime4 {calculation.type4_start_text} is earlier than "
                    f"EndTime1 {calculation.type1_end_text}; CC-RULE-010 used "
                    "a 0-minute gap."
                ),
            )
        )

    calculated_text = _format_compact_decimal(
        calculation.calculated_minutes
    )
    over_text = _format_compact_decimal(calculation.minutes_over)
    calculated_display = _format_decimal_minutes(
        calculated_text,
        calculation.calculated_minutes,
    )
    maximum_display = _format_minutes(calculation.configured_maximum)
    over_display = _format_decimal_minutes(
        over_text,
        calculation.minutes_over,
    )
    details.extend(
        (
            RuleDetail(
                "Calculated event time",
                calculated_display,
            ),
            RuleDetail(
                "Configured maximum event time",
                maximum_display,
            ),
            RuleDetail(
                "Minutes over the maximum",
                over_display,
            ),
            RuleDetail(
                "Comparison",
                (
                    f"Calculated event time {calculated_display} exceeds the "
                    f"configured maximum of {maximum_display} by "
                    f"{over_display}."
                ),
            ),
        )
    )
    return _build_exception(
        source_row,
        _RULE_010,
        details=tuple(details),
    )


def _rule_011_exception(
    source_row: CSVSourceRow,
    *,
    fluid_name: str,
    entered_concentration_text: str,
    required_concentration: Decimal,
) -> AuditException:
    required_display = f"{_format_compact_decimal(required_concentration)}%"
    entered_comparison = entered_concentration_text.strip()
    return _build_exception(
        source_row,
        _RULE_011,
        details=(
            RuleDetail("Selected Type IV fluid", fluid_name),
            RuleDetail(
                "Entered Type IV concentration",
                entered_concentration_text,
            ),
            RuleDetail(
                "Required Type IV concentration",
                required_display,
            ),
            RuleDetail(
                "Comparison",
                (
                    f"Entered concentration {entered_comparison} does "
                    f"not match the required {required_display}."
                ),
            ),
        ),
    )


def _rule_012_exception(
    source_row: CSVSourceRow,
    *,
    aircraft_type_number: int,
    failure_reasons: tuple[str, ...],
) -> AuditException:
    required_format = {
        0: (
            "AircraftType 0 requires a blank TailNumber and nonblank Notes."
        ),
        1: (
            "UPS format ^N[0-9]{3}UP$ after trimming, compared "
            "case-insensitively."
        ),
        2: (
            "A nonblank, non-UPS tail containing only letters, numbers, and "
            "hyphens, with at least one letter or number."
        ),
    }[aircraft_type_number]
    details: list[RuleDetail] = [
        RuleDetail("Original AircraftType", source_row.get("AircraftType")),
        RuleDetail("Original TailNumber", source_row.get("TailNumber")),
    ]
    if aircraft_type_number == 0:
        details.append(RuleDetail("Original Notes", source_row.get("Notes")))
    details.extend(
        (
            RuleDetail("Required format", required_format),
            RuleDetail("Failure reason", "; ".join(failure_reasons)),
        )
    )
    return _build_exception(
        source_row,
        _RULE_012,
        details=tuple(details),
    )


def _rule_013_exception(
    source_row: CSVSourceRow,
    *,
    overlap_minutes: int,
) -> AuditException:
    overlap_display = _format_minutes(overlap_minutes)
    type1_end_text = source_row.get("EndTime1")
    type4_start_text = source_row.get("StartTime4")
    return _build_exception(
        source_row,
        _RULE_013,
        details=(
            RuleDetail(
                "Overall StartTime",
                source_row.get("StartTime"),
            ),
            RuleDetail(
                "Overall EndTime",
                source_row.get("EndTime"),
            ),
            RuleDetail("Type I EndTime1", type1_end_text),
            RuleDetail("Type IV StartTime4", type4_start_text),
            RuleDetail("Calculated overlap", overlap_display),
            RuleDetail(
                "Explanation",
                (
                    f"Type IV began at {type4_start_text}, "
                    f"{overlap_display} before Type I ended at "
                    f"{type1_end_text}, and the overall event did not cross "
                    "midnight."
                ),
            ),
        ),
    )


def _rule_014_exception(
    source_row: CSVSourceRow,
    *,
    failure_reasons: tuple[str, ...],
    documented_truck_numbers: tuple[str, ...],
) -> AuditException:
    details: list[RuleDetail] = [
        RuleDetail("AircraftType", source_row.get("AircraftType")),
        RuleDetail("Type1Used", source_row.get("Type1Used")),
        RuleDetail("Type4Used", source_row.get("Type4Used")),
        RuleDetail("Current TruckNumber", source_row.get("TruckNumber")),
        RuleDetail("Original Notes", source_row.get("Notes")),
        RuleDetail(
            "Missing or failed requirement",
            "; ".join(failure_reasons),
        ),
    ]
    if documented_truck_numbers:
        details.append(
            RuleDetail(
                "Documented truck number",
                ", ".join(documented_truck_numbers),
            )
        )
    return _build_exception(
        source_row,
        _RULE_014,
        details=tuple(details),
    )


def _event_usage_status(
    is_used: bool,
    source_text: str,
    parsed_usage: Decimal | None,
) -> str:
    if is_used and parsed_usage is not None:
        unit = "gallon" if parsed_usage == 1 else "gallons"
        return f"Included — {source_text} {unit} recorded"
    if not source_text.strip():
        return "Not included — usage is blank"
    return f"Not included — recorded amount {source_text} is not positive"


def _build_exception(
    source_row: CSVSourceRow,
    rule: RuleDefinition,
    *,
    details: tuple[RuleDetail, ...],
) -> AuditException:
    return AuditException(
        rule_id=rule.rule_id,
        rule_name=rule.name,
        exception_message=rule.exception_message,
        source_row_number=source_row.source_row_number,
        record_id=source_row.get("RecordID"),
        application_number=source_row.get("ApplicationNumber"),
        gateway_code=source_row.get("GatewayCode"),
        aircraft_type=source_row.get("AircraftType"),
        tail_number=source_row.get("TailNumber"),
        application_date=source_row.get("ApplicationDate"),
        start_time=source_row.get("StartTime"),
        date_created=source_row.get("DateCreated"),
        truck_number=source_row.get("TruckNumber"),
        operator=source_row.get("Operator"),
        driver=source_row.get("Driver"),
        details=details,
    )


def _application_timestamp_source_text(source_row: CSVSourceRow) -> str:
    return (
        f"{source_row.get('ApplicationDate')} "
        f"{source_row.get('StartTime')}"
    )


def _format_duration(duration: timedelta) -> str:
    total_seconds = int(duration.total_seconds())
    days, remaining = divmod(total_seconds, 86_400)
    hours, remaining = divmod(remaining, 3_600)
    minutes, seconds = divmod(remaining, 60)

    parts: list[str] = []
    for value, label in (
        (days, "day"),
        (hours, "hour"),
        (minutes, "minute"),
        (seconds, "second"),
    ):
        if value:
            parts.append(f"{value} {label}{'' if value == 1 else 's'}")

    return ", ".join(parts) if parts else "0 minutes"


def _format_minutes(minutes: int) -> str:
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


def _format_decimal_minutes(source_text: str, minutes: Decimal) -> str:
    unit = "minute" if minutes == 1 else "minutes"
    return f"{source_text} {unit}"


def _format_compact_decimal(value: Decimal) -> str:
    display_value = format(value, "f")
    if "." in display_value:
        display_value = display_value.rstrip("0").rstrip(".")
    return display_value or "0"


def _format_temperature(value: Decimal) -> str:
    return f"{_format_decimal(value)}°F"


def _format_decimal(value: Decimal) -> str:
    return format(value, "f")


__all__ = [
    "AuditException",
    "AuditResult",
    "EXECUTED_RULES",
    "RuleDetail",
    "UnableToEvaluate",
    "run_audit",
]
