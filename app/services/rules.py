"""Authoritative registry for approved CryoCheck audit rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


IMPLEMENTED_STATUS: Final = "Implemented"
IMPLEMENTATION_PENDING_STATUS: Final = "Documented — implementation pending"


@dataclass(frozen=True, slots=True)
class RuleDefinition:
    """Immutable, user-facing specification for one approved audit rule."""

    rule_id: str
    name: str
    description: str
    logic_summary: tuple[str, ...]
    settings_defaults: tuple[str, ...]
    exception_message: str
    output_details: tuple[str, ...]
    implementation_status: str = IMPLEMENTATION_PENDING_STATUS

    @property
    def is_implemented(self) -> bool:
        return self.implementation_status == IMPLEMENTED_STATUS


RULES: Final[tuple[RuleDefinition, ...]] = (
    RuleDefinition(
        rule_id="CC-RULE-001",
        name="Application Entry Proceeds Event",
        description=(
            "Identifies an application entry created before its recorded "
            "application event."
        ),
        logic_summary=(
            "Use local timestamps only.",
            "Compare local DateCreated with local ApplicationDate + StartTime.",
            "Do not use UTC fields.",
            (
                "Generate an exception when DateCreated is earlier than the "
                "application event."
            ),
        ),
        settings_defaults=(
            "None.",
            "Mandatory.",
        ),
        exception_message="Application entry proceeds event.",
        output_details=(
            "Application date/time",
            "Entry date/time",
            "How far before the application event the entry was created",
        ),
        implementation_status=IMPLEMENTED_STATUS,
    ),
    RuleDefinition(
        rule_id="CC-RULE-002",
        name="Late Entry",
        description=(
            "Identifies an application entry created at or beyond the allowed "
            "delay after its recorded event."
        ),
        logic_summary=(
            "Compare local DateCreated with local ApplicationDate + StartTime.",
            (
                "Generate an exception when the delay is greater than or equal "
                "to the configured threshold."
            ),
        ),
        settings_defaults=(
            "Allowed threshold: 24 hours or 48 hours",
            "Default: 24 hours",
            "Exactly 24 hours fails when set to 24",
            "Exactly 48 hours fails when set to 48",
            "Mandatory",
        ),
        exception_message="Late entry.",
        output_details=(
            "Application date/time",
            "Entry date/time",
            "Configured threshold",
            "Actual delay",
            "Amount beyond the threshold",
        ),
        implementation_status=IMPLEMENTED_STATUS,
    ),
    RuleDefinition(
        rule_id="CC-RULE-003",
        name="Incorrect Freeze Point",
        description=(
            "Checks a recorded Type I freeze point against the exact value in "
            "the selected fluid’s manufacturer chart."
        ),
        logic_summary=(
            "Runs only when Type1Used is numerically greater than 0.",
            "Use the Type I fluid selected in active audit settings.",
            (
                "Use the recorded Type1Concentration to find the exact expected "
                "freeze point from that fluid’s manufacturer chart."
            ),
            "Concentrations 60 and 60.0 both select the 60% chart row.",
            (
                "The current Cryotech Polar Plus LT chart supports whole-number "
                "concentrations from 0–70%."
            ),
            (
                "A non-whole or unsupported concentration is unable to "
                "evaluate."
            ),
            "Compare the expected value with FreezingPoint1.",
            "Numerically equal decimal forms such as -50 and -50.0 are equivalent.",
            "Any other difference fails.",
        ),
        settings_defaults=(
            "Type I fluid is gateway-selectable",
            "Default Type I fluid: Cryotech Polar Plus LT",
            "Mandatory",
        ),
        exception_message="Incorrect freeze point.",
        output_details=(
            "Selected Type I fluid",
            "Recorded concentration",
            "Entered freeze point",
            "Expected manufacturer-chart freeze point",
            "Concise comparison",
        ),
        implementation_status=IMPLEMENTED_STATUS,
    ),
    RuleDefinition(
        rule_id="CC-RULE-004",
        name="18 Degree Buffer Not Met",
        description=(
            "Checks whether the correct Type I chart freeze point provides the "
            "required 18°F temperature buffer."
        ),
        logic_summary=(
            "Runs only when Type1Used is numerically greater than 0.",
            "Required buffer is 18.0°F.",
            (
                "Buffer = AmbientTemp minus the correct manufacturer-chart "
                "Type I freeze point."
            ),
            (
                "Always use the authoritative manufacturer-chart freeze point, "
                "never an incorrectly entered FreezingPoint1 value."
            ),
            "A buffer below 18.0°F fails.",
            "A buffer of 18.0°F or greater passes.",
            (
                "The current Cryotech Polar Plus LT chart supports whole-number "
                "concentrations from 0–70%."
            ),
            (
                "A non-whole or unsupported concentration is unable to "
                "evaluate."
            ),
            (
                "Do not create a false buffer exception solely because the "
                "entered freeze point is wrong."
            ),
            (
                "If the entered freeze point is wrong but the correct chart "
                "value passes the buffer, only CC-RULE-003 applies."
            ),
            (
                "If the correct chart value still fails the buffer, "
                "CC-RULE-004 applies; CC-RULE-003 also applies when the entered "
                "value is wrong."
            ),
        ),
        settings_defaults=(
            "Required buffer: fixed at 18.0°F",
            "Mandatory",
        ),
        exception_message="18 degree buffer not met.",
        output_details=(
            "Selected Type I fluid",
            "Recorded concentration",
            "Outside air temperature",
            "Authoritative manufacturer-chart freeze point",
            "Actual calculated buffer",
            "Required buffer",
            "Amount short",
        ),
        implementation_status=IMPLEMENTED_STATUS,
    ),
    RuleDefinition(
        rule_id="CC-RULE-005",
        name="BRIX Out of Range",
        description=(
            "Checks recorded Type IV BRIX against the inclusive range for the "
            "selected fluid."
        ),
        logic_summary=(
            "Runs only when Type4Used is numerically greater than 0.",
            "Use the Type IV fluid selected in active audit settings.",
            "Parse Type4ABrix using Decimal without rounding.",
            (
                "For Cryotech Polar Guard Xtend, the acceptable range is "
                "34.6–36.6 inclusive."
            ),
            "Values below 34.6 or above 36.6 fail.",
            "The exact lower and upper boundaries pass.",
            (
                "Malformed applicability, missing or invalid BRIX, and unknown "
                "fluid profiles are unable to evaluate."
            ),
        ),
        settings_defaults=(
            "Type IV fluid is selected in active audit settings",
            "Default Type IV fluid: Cryotech Polar Guard Xtend",
            "Default range: 34.6–36.6 inclusive",
            "Mandatory",
        ),
        exception_message="BRIX out of range.",
        output_details=(
            "Selected Type IV fluid",
            "Entered BRIX",
            "Acceptable inclusive range",
            "Whether the value is below or above the range",
            "Exact amount below or above the nearest boundary",
            "Concise comparison",
        ),
        implementation_status=IMPLEMENTED_STATUS,
    ),
    RuleDefinition(
        rule_id="CC-RULE-006",
        name="Excessive Gap Between Steps",
        description=(
            "Checks the whole-minute gap between Type I completion and Type IV "
            "start against the allowed maximum."
        ),
        logic_summary=(
            (
                "Applies only when Type1Used and Type4Used are both "
                "numerically greater than 0."
            ),
            "Compare EndTime1 with StartTime4.",
            "Use exact whole-minute military HH:MM arithmetic.",
            (
                "Generate an exception only when the calculated gap is greater "
                "than the configured allowed gap."
            ),
            "A gap equal to the setting passes.",
            (
                "When the overall event crosses midnight, treat an earlier "
                "StartTime4 as occurring on the next calendar day."
            ),
            (
                "An earlier StartTime4 during a same-day event is an overlap "
                "evaluated by CC-RULE-013, not a 24-hour gap."
            ),
            (
                "Blank or malformed required values produce an "
                "unable-to-evaluate warning when applicability is positive."
            ),
        ),
        settings_defaults=(
            "Allowed Gap accepts 0–99 whole minutes",
            "Default: 5 minutes",
            "With a setting of 5, gaps of 0–5 pass and 6 or more fail",
            "Mandatory",
        ),
        exception_message="Excessive gap between steps.",
        output_details=(
            "Type I end time",
            "Type IV start time",
            "Actual gap in whole minutes",
            "Configured Allowed Gap",
            "Whole minutes over the setting",
            "Concise comparison",
        ),
        implementation_status=IMPLEMENTED_STATUS,
    ),
    RuleDefinition(
        rule_id="CC-RULE-007",
        name="No Type IV During Active Precipitation",
        description=(
            "Identifies active precipitation events where no Type IV fluid "
            "amount was recorded."
        ),
        logic_summary=(
            (
                "Treat blank or whitespace-only Precipitation as no active "
                "precipitation."
            ),
            (
                "After trimming whitespace, treat any capitalization of None "
                "as no active precipitation."
            ),
            "Treat every other nonblank precipitation value as active.",
            (
                "Treat blank or numerically zero Type4Used as no recorded "
                "Type IV."
            ),
            (
                "Generate an exception when precipitation is active and "
                "Type4Used is blank or numerically zero."
            ),
            (
                "Positive Type4Used passes; malformed, non-finite, or negative "
                "Type4Used is unable to evaluate when precipitation is active."
            ),
            (
                "When precipitation is not active, skip without evaluating "
                "Type4Used."
            ),
        ),
        settings_defaults=(
            "No configurable setting.",
            "Mandatory",
        ),
        exception_message="No Type IV during active precipitation.",
        output_details=(
            "Recorded precipitation",
            "Type IV amount recorded",
            (
                "Statement that no Type IV was recorded during active "
                "precipitation"
            ),
        ),
        implementation_status=IMPLEMENTED_STATUS,
    ),
    RuleDefinition(
        rule_id="CC-RULE-008",
        name="Excessive Type I",
        description=(
            "Checks the adjusted Type I application rate against its configured "
            "maximum."
        ),
        logic_summary=(
            "Run only when Type1Used is numerically greater than 0.",
            (
                "Blank, zero, or negative Type1Used skips the rule; malformed "
                "or non-finite Type1Used is unable to evaluate."
            ),
            "Use the CSV’s existing whole-number ProcessTime1 value directly.",
            "Do not recalculate duration from StartTime1 and EndTime1.",
            (
                "ProcessTime1 must be finite, nonnegative, and numerically a "
                "whole number when Type I usage is positive."
            ),
            "Adjusted Type I rate = Type1Used / (ProcessTime1 + 1).",
            (
                "The added minute conservatively accounts for whole-minute "
                "recording precision."
            ),
            "Use Decimal-safe arithmetic without rounding before comparison.",
            (
                "Generate an exception only when the adjusted rate is greater "
                "than the configured maximum."
            ),
            "A rate equal to the maximum passes.",
            (
                "Invalid required values or an invalid runtime maximum produce "
                "an unable-to-evaluate warning, not an exception."
            ),
        ),
        settings_defaults=(
            "Maximum Type I rate: active profile setting",
            "Default: 60 gallons per minute",
            "Personal Settings apply to the next signed-in upload",
            "Mandatory",
        ),
        exception_message="Excessive Type I.",
        output_details=(
            "Type I gallons used",
            "Recorded ProcessTime1",
            "Adjusted calculation time",
            "Adjusted gallons per minute",
            "Configured maximum",
            "Comparison statement",
        ),
        implementation_status=IMPLEMENTED_STATUS,
    ),
    RuleDefinition(
        rule_id="CC-RULE-009",
        name="Excessive Type IV",
        description=(
            "Checks the adjusted Type IV application rate against its "
            "independently configured maximum."
        ),
        logic_summary=(
            "Run only when Type4Used is numerically greater than 0.",
            (
                "Blank, zero, or negative Type4Used skips the rule; malformed "
                "or non-finite Type4Used is unable to evaluate."
            ),
            "Use the CSV’s existing whole-number ProcessTime4 value directly.",
            "Do not recalculate duration from StartTime4 and EndTime4.",
            (
                "ProcessTime4 must be finite, nonnegative, and numerically a "
                "whole number when Type IV usage is positive."
            ),
            "Adjusted Type IV rate = Type4Used / (ProcessTime4 + 1).",
            (
                "The added minute conservatively accounts for whole-minute "
                "recording precision."
            ),
            "Use Decimal-safe arithmetic without rounding before comparison.",
            (
                "Generate an exception only when the adjusted rate is greater "
                "than the configured maximum."
            ),
            "A rate equal to the maximum passes.",
            (
                "Invalid required values or an invalid runtime maximum produce "
                "an unable-to-evaluate warning, not an exception."
            ),
        ),
        settings_defaults=(
            "Maximum Type IV rate: active profile setting",
            "Default: 30 gallons per minute",
            "Adjustable independently from the Type I maximum",
            "Personal Settings apply to the next signed-in upload",
            "Mandatory",
        ),
        exception_message="Excessive Type IV.",
        output_details=(
            "Type IV gallons used",
            "Recorded ProcessTime4",
            "Adjusted calculation time",
            "Adjusted gallons per minute",
            "Configured maximum",
            "Comparison statement",
        ),
        implementation_status=IMPLEMENTED_STATUS,
    ),
    RuleDefinition(
        rule_id="CC-RULE-010",
        name="Excessive Event Time",
        description=(
            "Checks the recorded deicing process time, with an optional "
            "inter-step gap, against the configured maximum."
        ),
        logic_summary=(
            (
                "Parse Type1Used and Type4Used with Decimal-safe logic; a step "
                "is used only when its recorded amount is greater than 0."
            ),
            (
                "Blank, zero, or negative usage excludes that step; malformed "
                "or non-finite usage is unable to evaluate."
            ),
            (
                "When neither step is positively used, skip without an "
                "exception or warning."
            ),
            "If only Type I is used, event time = ProcessTime1.",
            "If only Type IV is used, event time = ProcessTime4.",
            (
                "If Type I and Type IV are used, event time = ProcessTime1 + "
                "ProcessTime4."
            ),
            (
                "Use original process times directly without the one-minute "
                "rate adjustment from CC-RULE-008 and CC-RULE-009."
            ),
            (
                "Every positively used step requires a finite, nonnegative, "
                "numerically whole process time."
            ),
            (
                "When Include Gap is Off, do not add a gap or require step or "
                "overall clock times."
            ),
            (
                "When Include Gap is On and both steps are used, add the "
                "whole-minute gap from EndTime1 to StartTime4."
            ),
            (
                "Use overall StartTime and EndTime to recognize an overnight "
                "gap when StartTime4 is earlier than EndTime1."
            ),
            (
                "A same-day overlap contributes a 0-minute gap to CC-RULE-010 "
                "and is independently evaluated by CC-RULE-013."
            ),
            (
                "Type I-only and Type IV-only events never include a gap, even "
                "when Include Gap is On."
            ),
            (
                "Invalid required process, clock, maximum, or Include Gap "
                "values produce an unable-to-evaluate warning."
            ),
            (
                "Generate an exception only when event time is greater than the "
                "configured maximum."
            ),
            "Event time equal to the maximum passes.",
        ),
        settings_defaults=(
            "Maximum event time: active profile setting",
            "Default: 30 minutes",
            "Valid range: whole numbers from 1 through 999 minutes",
            "Include gap between Type I and Type IV: On or Off",
            "Default Include Gap value: Off",
            "Personal Settings apply to the next signed-in upload",
            "Mandatory",
        ),
        exception_message="Excessive event time.",
        output_details=(
            "Type I usage status",
            "Type IV usage status",
            "Applicable original process times",
            "Include Gap setting",
            "Included gap and source clock times when applicable",
            "Overlap handling when a 0-minute gap is used",
            "Calculated event time",
            "Configured maximum event time",
            "Minutes over the maximum",
            "Comparison statement",
        ),
        implementation_status=IMPLEMENTED_STATUS,
    ),
    RuleDefinition(
        rule_id="CC-RULE-011",
        name="Incorrect Type IV Concentration",
        description=(
            "Checks a recorded Type IV concentration against the requirement "
            "for the selected fluid."
        ),
        logic_summary=(
            (
                "Run only when Type4Used is numerically greater than 0; blank, "
                "zero, or negative usage skips."
            ),
            (
                "Malformed or non-finite Type4Used is unable to evaluate "
                "without blocking other Type IV rules."
            ),
            (
                "Use the required concentration from the Type IV fluid "
                "selected in the active audit settings."
            ),
            (
                "Cryotech Polar Guard Xtend requires exactly 100% "
                "concentration."
            ),
            (
                "Accept a finite numeric concentration with or without one "
                "optional trailing percent sign, including surrounding "
                "whitespace."
            ),
            (
                "Compare with Decimal-safe exact equality; do not interpret "
                "fractions as percentages and do not round into compliance."
            ),
            (
                "Blank, malformed, non-finite, unsupported, or ambiguously "
                "formatted concentration is unable to evaluate."
            ),
            (
                "An unavailable or invalid selected fluid requirement is "
                "unable to evaluate."
            ),
            (
                "Evaluate independently from CC-RULE-005 BRIX and CC-RULE-009 "
                "adjusted-rate validation."
            ),
            "Generate an exception only when the exact concentrations differ.",
        ),
        settings_defaults=(
            "Type IV fluid is selected by the active settings profile",
            "Default Type IV fluid: Cryotech Polar Guard Xtend",
            "Required concentration for the default fluid: 100%",
            "Mandatory",
        ),
        exception_message="Incorrect Type IV concentration.",
        output_details=(
            "Selected Type IV fluid",
            "Entered Type IV concentration",
            "Required Type IV concentration",
            "Comparison statement",
        ),
        implementation_status=IMPLEMENTED_STATUS,
    ),
    RuleDefinition(
        rule_id="CC-RULE-012",
        name="Incorrect Tail Number",
        description=(
            "Checks a tail number against the approved format requirement for "
            "its recorded aircraft type."
        ),
        logic_summary=(
            (
                "Trim surrounding whitespace and compare letters "
                "case-insensitively."
            ),
            (
                "AircraftType must resolve numerically to whole-number 0, 1, "
                "or 2; equivalent Decimal forms such as 0.0, 1.0, and 2.00 "
                "are accepted."
            ),
            (
                "Blank, malformed, non-finite, non-whole, or unsupported "
                "AircraftType is unable to evaluate."
            ),
            (
                "When AircraftType = 0, TailNumber must be blank and Notes "
                "must contain nonblank text."
            ),
            (
                "Type I and Type IV usage do not affect AircraftType 0 "
                "validation."
            ),
            (
                "When AircraftType = 1, TailNumber must match the UPS format "
                "NxxxUP, where each x is a digit."
            ),
            "Normalized UPS pattern: ^N[0-9]{3}UP$",
            "When AircraftType = 2:",
            "TailNumber must not be blank.",
            "TailNumber must not match the UPS NxxxUP pattern.",
            (
                "TailNumber may contain only letters, numbers, and hyphens and "
                "must contain at least one letter or number."
            ),
            (
                "Leading, trailing, and repeated hyphens are allowed for "
                "AircraftType 2."
            ),
            (
                "Do not perform FAA, ICAO, registry, country-specific, "
                "carrier-list, ownership, web, or API validation."
            ),
            (
                "Generate an exception when the tail does not meet the "
                "requirement for its aircraft type."
            ),
        ),
        settings_defaults=(
            "None",
            "Mandatory",
        ),
        exception_message="Incorrect tail number.",
        output_details=(
            "Original AircraftType",
            "Original TailNumber",
            "Original Notes for AircraftType 0",
            "Required format",
            "Specific failure reason",
        ),
        implementation_status=IMPLEMENTED_STATUS,
    ),
    RuleDefinition(
        rule_id="CC-RULE-013",
        name="Pass Overlap",
        description=(
            "Checks that a Type IV pass does not begin before the Type I pass "
            "ends, while accounting for events that cross midnight."
        ),
        logic_summary=(
            (
                "Run only when Type1Used and Type4Used are both numerically "
                "greater than 0."
            ),
            (
                "Blank, zero, or negative usage skips the rule; malformed or "
                "non-finite usage is unable to evaluate."
            ),
            (
                "Parse EndTime1 and StartTime4 as exact whole-minute military "
                "HH:MM values."
            ),
            (
                "Equality or a later StartTime4 passes without requiring "
                "overall StartTime or EndTime."
            ),
            (
                "When StartTime4 is earlier than EndTime1, use overall "
                "StartTime and EndTime to determine whether the event crossed "
                "midnight."
            ),
            (
                "Overall event crosses midnight only when EndTime is earlier "
                "than StartTime; then treat StartTime4 as occurring the next "
                "day and pass."
            ),
            (
                "If the overall event did not cross midnight, generate an "
                "exception and calculate overlap as EndTime1 minus StartTime4."
            ),
            (
                "Missing or malformed step times, or missing or malformed "
                "overall times needed to resolve an earlier StartTime4, are "
                "unable to evaluate."
            ),
        ),
        settings_defaults=(
            "None",
            "Mandatory",
        ),
        exception_message="Pass overlap.",
        output_details=(
            "Original overall StartTime",
            "Original overall EndTime",
            "Original Type I EndTime1",
            "Original Type IV StartTime4",
            "Calculated overlap minutes",
            "Concise explanation",
        ),
        implementation_status=IMPLEMENTED_STATUS,
    ),
    RuleDefinition(
        rule_id="CC-RULE-014",
        name="Type IV Without Type I Explanation Required",
        description=(
            "Checks that a Type IV-only row deterministically documents Type I "
            "application by a different truck."
        ),
        logic_summary=(
            (
                "Future applicability: Type4Used is greater than 0 while "
                "Type1Used is blank, zero, or negative."
            ),
            (
                "Notes must deterministically state that Type I was applied by "
                "another truck and include that truck's numeric identifier."
            ),
            (
                "Recognize a Type I reference such as Type I, Type 1, or T1."
            ),
            (
                "Require language indicating Type I was applied, sprayed, "
                "completed, performed, or done."
            ),
            (
                "Require a whole-number identifier of any length clearly "
                "associated with the word truck."
            ),
            (
                "The documented other-truck number must differ from the current "
                "row's TruckNumber."
            ),
            (
                "An unrelated number not associated with the word truck does "
                "not qualify."
            ),
            "Do not use AI or semantic guessing.",
        ),
        settings_defaults=(
            "No configurable setting.",
            "Mandatory",
        ),
        exception_message=(
            "Type IV applied without documented Type I truck."
        ),
        output_details=(
            "Type1Used",
            "Type4Used",
            "Current TruckNumber",
            "Entered Notes",
            "Deterministic qualification failure",
        ),
    ),
)


def _validate_registry() -> None:
    expected_ids = tuple(f"CC-RULE-{number:03d}" for number in range(1, 15))
    actual_ids = tuple(rule.rule_id for rule in RULES)
    if actual_ids != expected_ids or len(actual_ids) != len(set(actual_ids)):
        raise RuntimeError(
            "CryoCheck rule IDs must be unique and remain in permanent numeric order."
        )


_validate_registry()


__all__ = [
    "IMPLEMENTATION_PENDING_STATUS",
    "IMPLEMENTED_STATUS",
    "RULES",
    "RuleDefinition",
]
