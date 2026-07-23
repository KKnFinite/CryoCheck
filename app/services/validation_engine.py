"""In-memory execution for CryoCheck's implemented audit rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from app.services.csv_import import CSVImportResult, CSVSourceRow
from app.services.rules import IMPLEMENTED_STATUS, RULES, RuleDefinition
from app.services.settings import SettingsDefinition


EXECUTED_RULES: Final[tuple[RuleDefinition, ...]] = tuple(
    rule for rule in RULES if rule.implementation_status == IMPLEMENTED_STATUS
)
_RULE_001, _RULE_002 = EXECUTED_RULES

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
_MILITARY_TIME_PATTERN: Final = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


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
            for rule in EXECUTED_RULES:
                warnings.append(
                    _unable_to_evaluate(source_row, rule, invalid_fields)
                )
            continue

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
    start_time = _parse_military_time(source_row.get("StartTime"))
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
        start_time.time(),
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


def _parse_military_time(source_value: str) -> datetime | None:
    value = source_value.strip()
    if not _MILITARY_TIME_PATTERN.fullmatch(value):
        return None
    return datetime.strptime(value, "%H:%M")


def _unable_to_evaluate(
    source_row: CSVSourceRow,
    rule: RuleDefinition,
    invalid_fields: tuple[str, ...],
) -> UnableToEvaluate:
    field_list = ", ".join(invalid_fields)
    return UnableToEvaluate(
        rule_id=rule.rule_id,
        rule_name=rule.name,
        source_row_number=source_row.source_row_number,
        record_id=source_row.get("RecordID"),
        invalid_fields=invalid_fields,
        message=(
            "Required local timestamp values are blank or invalid: "
            f"{field_list}."
        ),
    )


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


__all__ = [
    "AuditException",
    "AuditResult",
    "EXECUTED_RULES",
    "RuleDetail",
    "UnableToEvaluate",
    "run_audit",
]
