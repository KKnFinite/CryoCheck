"""In-memory execution for CryoCheck's implemented audit rules."""

from __future__ import annotations

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
_TIMESTAMP_RULES: Final = (_RULE_001, _RULE_002)
_TYPE1_RULES: Final = (_RULE_003, _RULE_004)
_REQUIRED_TYPE1_BUFFER: Final = Decimal("18.0")

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
