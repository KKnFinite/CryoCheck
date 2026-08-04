"""Presentation-only detail selection for compact Results cards."""

from __future__ import annotations

from collections.abc import Iterable

from app.services.validation_engine import AuditException, RuleDetail


_FLUID_LABELS = {
    "Selected Type I fluid",
    "Selected Type IV fluid",
}
_MINIMUM_LABELS_BY_RULE = {
    "CC-RULE-001": (
        "Application date/time",
        "How far before the application event the entry was created",
    ),
    "CC-RULE-003": ("Comparison",),
    "CC-RULE-005": ("Comparison",),
    "CC-RULE-006": ("Comparison",),
    "CC-RULE-007": (
        "Recorded precipitation",
        "Type IV amount recorded",
    ),
    "CC-RULE-008": (
        "Type I gallons used",
        "Recorded ProcessTime1",
        "Adjusted calculation time",
        "Comparison",
    ),
    "CC-RULE-009": (
        "Type IV gallons used",
        "Recorded ProcessTime4",
        "Adjusted calculation time",
        "Comparison",
    ),
    "CC-RULE-010": (
        "Type I usage status",
        "Type IV usage status",
        "ProcessTime1",
        "ProcessTime4",
        "Include Gap setting",
        "Included gap",
        "Overlap handling",
        "Comparison",
    ),
    "CC-RULE-011": ("Comparison",),
    "CC-RULE-012": (
        "Original AircraftType",
        "Original TailNumber",
        "Original Notes",
        "Required format",
        "Failure reason",
    ),
    "CC-RULE-013": ("Explanation",),
    "CC-RULE-014": (
        "Missing or failed requirement",
        "Documented truck number",
    ),
}

_RULE_004_DISPLAY_LABELS = (
    ("Recorded concentration", "Recorded Concentration"),
    ("Outside air temperature", "OAT"),
    (
        "Authoritative manufacturer-chart freeze point",
        "Correct Freeze Point",
    ),
    ("Actual calculated buffer", "Calculated Buffer"),
)


def _details_with_labels(
    details: Iterable[RuleDetail],
    labels: tuple[str, ...],
) -> tuple[RuleDetail, ...]:
    details_by_label = {
        detail.label: detail
        for detail in details
        if detail.label not in _FLUID_LABELS
    }
    return tuple(
        details_by_label[label]
        for label in labels
        if label in details_by_label
    )


def _details_by_label(exception: AuditException) -> dict[str, RuleDetail]:
    return {detail.label: detail for detail in exception.details}


def _late_entry_details(exception: AuditException) -> tuple[RuleDetail, ...]:
    details = _details_by_label(exception)
    threshold = details["Configured threshold"].value
    overage = details["Amount beyond the threshold"].value
    threshold_parts = threshold.split(maxsplit=1)
    threshold_adjective = threshold
    if len(threshold_parts) == 2:
        quantity, unit = threshold_parts
        threshold_adjective = f"{quantity}-{unit.removesuffix('s')}"
    return (
        RuleDetail(
            "",
            f"{overage} past the {threshold_adjective} threshold.",
        ),
    )


def _buffer_details(exception: AuditException) -> tuple[RuleDetail, ...]:
    details = _details_by_label(exception)
    return tuple(
        RuleDetail(display_label, details[source_label].value)
        for source_label, display_label in _RULE_004_DISPLAY_LABELS
    )


def concise_exception_details(
    exception: AuditException,
) -> tuple[RuleDetail, ...]:
    """Return only nonduplicated details needed to understand an exception."""
    if exception.rule_id == "CC-RULE-002":
        return _late_entry_details(exception)
    if exception.rule_id == "CC-RULE-004":
        return _buffer_details(exception)
    if (
        exception.rule_id == "CC-RULE-003"
        and any(
            detail.label == "Supported chart range"
            for detail in exception.details
        )
    ):
        return exception.details

    details = tuple(
        detail
        for detail in exception.details
        if detail.label not in _FLUID_LABELS
    )
    minimum_labels = _MINIMUM_LABELS_BY_RULE.get(exception.rule_id)
    if minimum_labels is None:
        return details
    return _details_with_labels(details, minimum_labels)
