"""Deterministic, presentation-only mappings for Results cards."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.validation_engine import AuditException


INVALID_VALUE = "invalid"
REFERENCE_VALUE = "reference"


@dataclass(frozen=True, slots=True)
class ResultDetail:
    """One visible Results-card value and its presentation role."""

    label: str
    value: str
    value_kind: str = REFERENCE_VALUE


@dataclass(frozen=True, slots=True)
class ExceptionPresentation:
    """Visible exception-card content derived without changing audit data."""

    details: tuple[ResultDetail, ...]
    invalid_identity_fields: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class _DetailSpec:
    source_label: str
    display_label: str
    value_kind: str = REFERENCE_VALUE


_STANDARD_SPECS: dict[str, tuple[_DetailSpec, ...]] = {
    "CC-RULE-001": (
        _DetailSpec("Application date/time", "Application Date/Time"),
        _DetailSpec(
            "How far before the application event the entry was created",
            "Entered Early By",
        ),
    ),
    "CC-RULE-004": (
        _DetailSpec(
            "Recorded concentration",
            "Recorded Concentration",
            INVALID_VALUE,
        ),
        _DetailSpec(
            "Outside air temperature",
            "OAT",
            INVALID_VALUE,
        ),
        _DetailSpec(
            "Authoritative manufacturer-chart freeze point",
            "Correct Freeze Point",
        ),
        _DetailSpec("Actual calculated buffer", "Calculated Buffer"),
    ),
    "CC-RULE-005": (
        _DetailSpec("Entered BRIX", "Entered BRIX", INVALID_VALUE),
        _DetailSpec("Selected Type IV fluid", "Type IV Fluid"),
        _DetailSpec("Acceptable inclusive range", "Acceptable Range"),
    ),
    "CC-RULE-006": (
        _DetailSpec("Type I end time", "Type I End Time", INVALID_VALUE),
        _DetailSpec(
            "Type IV start time",
            "Type IV Start Time",
            INVALID_VALUE,
        ),
        _DetailSpec("Actual calculated gap", "Calculated Gap"),
        _DetailSpec("Configured Allowed Gap", "Allowed Gap"),
    ),
    "CC-RULE-008": (
        _DetailSpec(
            "Adjusted Type I rate",
            "Adjusted Type I Rate",
            INVALID_VALUE,
        ),
        _DetailSpec("Type I gallons used", "Type I Used"),
        _DetailSpec(
            "Recorded ProcessTime1",
            "Process Time 1",
        ),
        _DetailSpec(
            "Configured maximum Type I rate",
            "Maximum Type I Rate",
        ),
    ),
    "CC-RULE-009": (
        _DetailSpec(
            "Adjusted Type IV rate",
            "Adjusted Type IV Rate",
            INVALID_VALUE,
        ),
        _DetailSpec("Type IV gallons used", "Type IV Used"),
        _DetailSpec(
            "Recorded ProcessTime4",
            "Process Time 4",
        ),
        _DetailSpec(
            "Configured maximum Type IV rate",
            "Maximum Type IV Rate",
        ),
    ),
    "CC-RULE-010": (
        _DetailSpec("ProcessTime1", "Process Time 1", INVALID_VALUE),
        _DetailSpec("ProcessTime4", "Process Time 4", INVALID_VALUE),
        _DetailSpec("Include Gap setting", "Include Gap"),
        _DetailSpec("Included gap", "Included Gap"),
        _DetailSpec("Overlap handling", "Overlap Handling"),
        _DetailSpec("Calculated event time", "Calculated Event Time"),
        _DetailSpec(
            "Configured maximum event time",
            "Maximum Event Time",
        ),
    ),
    "CC-RULE-011": (
        _DetailSpec(
            "Entered Type IV concentration",
            "Entered Concentration",
            INVALID_VALUE,
        ),
        _DetailSpec(
            "Required Type IV concentration",
            "Required Concentration",
        ),
    ),
}


def _details_by_label(exception: AuditException) -> dict[str, str]:
    return {detail.label: detail.value for detail in exception.details}


def _visible_value(value: str, *, invalid: bool = False) -> str:
    if value.strip():
        return value
    return "Blank" if invalid else "Not reported"


def _mapped_details(
    exception: AuditException,
    specs: tuple[_DetailSpec, ...],
) -> tuple[ResultDetail, ...]:
    source = _details_by_label(exception)
    return tuple(
        ResultDetail(
            spec.display_label,
            _visible_value(
                source[spec.source_label],
                invalid=spec.value_kind == INVALID_VALUE,
            ),
            spec.value_kind,
        )
        for spec in specs
        if spec.source_label in source
    )


def _late_entry_presentation(
    exception: AuditException,
) -> ExceptionPresentation:
    details = _details_by_label(exception)
    threshold = details["Configured threshold"]
    overage = details["Amount beyond the threshold"]
    threshold_parts = threshold.split(maxsplit=1)
    threshold_adjective = threshold
    if len(threshold_parts) == 2:
        quantity, unit = threshold_parts
        threshold_adjective = f"{quantity}-{unit.removesuffix('s')}"
    return ExceptionPresentation(
        details=(
            ResultDetail(
                "Application Date/Time",
                details["Application date/time"],
            ),
            ResultDetail(
                "Threshold Overage",
                f"{overage} past the {threshold_adjective} threshold.",
            ),
        ),
        invalid_identity_fields=frozenset({"entry_date"}),
    )


def _rule_003_presentation(
    exception: AuditException,
) -> ExceptionPresentation:
    details = _details_by_label(exception)
    if "Supported chart range" in details:
        return ExceptionPresentation(
            details=(
                ResultDetail(
                    "Entered Concentration",
                    _visible_value(
                        details["Entered concentration"],
                        invalid=True,
                    ),
                    INVALID_VALUE,
                ),
                ResultDetail(
                    "Supported Chart Range",
                    details["Supported chart range"],
                ),
            ),
        )
    return ExceptionPresentation(
        details=(
            ResultDetail(
                "Entered Freeze Point",
                _visible_value(details["Entered freeze point"], invalid=True),
                INVALID_VALUE,
            ),
            ResultDetail(
                "Recorded Concentration",
                details["Recorded concentration"],
            ),
            ResultDetail(
                "Correct Freeze Point",
                details["Expected manufacturer-chart freeze point"],
            ),
        ),
    )


def _rule_007_presentation(
    exception: AuditException,
) -> ExceptionPresentation:
    details = _details_by_label(exception)
    return ExceptionPresentation(
        details=(
            ResultDetail(
                "Type IV Used",
                _visible_value(
                    details["Type IV amount recorded"],
                    invalid=True,
                ),
                INVALID_VALUE,
            ),
            ResultDetail("Precipitation", details["Recorded precipitation"]),
            ResultDetail(
                "Expected",
                (
                    "Type IV is expected during active precipitation, or a "
                    "comment if another truck was used."
                ),
            ),
        ),
    )


def _rule_012_presentation(
    exception: AuditException,
) -> ExceptionPresentation:
    details = _details_by_label(exception)
    failure = details["Failure reason"]
    failure_lower = failure.lower()
    notes_invalid = "notes are required" in failure_lower
    tail_invalid = any(
        marker in failure_lower
        for marker in (
            "tailnumber",
            "ups",
            "unsupported characters",
            "letter or number",
        )
    )
    if not notes_invalid and not tail_invalid:
        tail_invalid = True

    invalid_details: list[ResultDetail] = []
    if tail_invalid:
        invalid_details.append(
            ResultDetail(
                "Entered Tail Number",
                _visible_value(details["Original TailNumber"], invalid=True),
                INVALID_VALUE,
            )
        )
    if notes_invalid and "Original Notes" in details:
        invalid_details.append(
            ResultDetail(
                "Entered Notes",
                _visible_value(details["Original Notes"], invalid=True),
                INVALID_VALUE,
            )
        )
    format_details = (
        ()
        if failure == "Does not match UPS NxxxUP format"
        else (ResultDetail("Expected Format", details["Required format"]),)
    )
    return ExceptionPresentation(
        details=(
            *invalid_details,
            ResultDetail("Aircraft Type", details["Original AircraftType"]),
            *format_details,
            ResultDetail("Explanation", failure),
        ),
    )


def _rule_013_presentation(
    exception: AuditException,
) -> ExceptionPresentation:
    details = _details_by_label(exception)
    return ExceptionPresentation(
        details=(
            ResultDetail(
                "Type I End Time",
                details["Type I EndTime1"],
                INVALID_VALUE,
            ),
            ResultDetail(
                "Type IV Start Time",
                details["Type IV StartTime4"],
                INVALID_VALUE,
            ),
            ResultDetail(
                "Expected",
                "Type IV pass cannot start prior to Type I pass ending.",
            ),
        ),
    )


def _rule_014_presentation(
    exception: AuditException,
) -> ExceptionPresentation:
    details = _details_by_label(exception)
    failure = details["Missing or failed requirement"]
    documented_truck = details.get("Documented truck number")
    invalid_details = [
        ResultDetail(
            "Entered Notes",
            _visible_value(details["Original Notes"], invalid=True),
            INVALID_VALUE,
        )
    ]
    reference_details: list[ResultDetail] = []
    if documented_truck:
        target = (
            invalid_details
            if "current" in failure.lower()
            else reference_details
        )
        target.append(
            ResultDetail(
                "Documented Truck Number",
                documented_truck,
                (
                    INVALID_VALUE
                    if target is invalid_details
                    else REFERENCE_VALUE
                ),
            )
        )
    return ExceptionPresentation(
        details=(
            *invalid_details,
            *reference_details,
            ResultDetail(
                "Expected",
                (
                    "Notes must state that Type I was applied by a different "
                    "truck and include that truck number."
                ),
            ),
        ),
    )


def exception_presentation(
    exception: AuditException,
) -> ExceptionPresentation:
    """Return the compact, rule-specific presentation for an exception."""
    if exception.rule_id == "CC-RULE-002":
        return _late_entry_presentation(exception)
    if exception.rule_id == "CC-RULE-003":
        return _rule_003_presentation(exception)
    if exception.rule_id == "CC-RULE-007":
        return _rule_007_presentation(exception)
    if exception.rule_id == "CC-RULE-012":
        return _rule_012_presentation(exception)
    if exception.rule_id == "CC-RULE-013":
        return _rule_013_presentation(exception)
    if exception.rule_id == "CC-RULE-014":
        return _rule_014_presentation(exception)

    details = _mapped_details(
        exception,
        _STANDARD_SPECS[exception.rule_id],
    )
    invalid_identity_fields = (
        frozenset({"entry_date"})
        if exception.rule_id == "CC-RULE-001"
        else frozenset()
    )
    return ExceptionPresentation(details, invalid_identity_fields)


def concise_exception_details(
    exception: AuditException,
) -> tuple[ResultDetail, ...]:
    """Compatibility helper returning the mapped visible details only."""
    return exception_presentation(exception).details
