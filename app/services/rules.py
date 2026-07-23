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
            "Applies to Type IV BRIX.",
            (
                "Validate Type4ABrix against the acceptable range for the Type "
                "IV fluid selected for the gateway."
            ),
            (
                "For Cryotech Polar Guard Xtend, 34.6 through 36.6 inclusive "
                "passes."
            ),
            "Below 34.6 or above 36.6 fails.",
        ),
        settings_defaults=(
            "Type IV fluid is gateway-selectable",
            "Default Type IV fluid: Cryotech Polar Guard Xtend",
            "Default range: 34.6–36.6 inclusive",
            "Mandatory",
        ),
        exception_message="BRIX out of range.",
        output_details=(
            "Selected Type IV fluid",
            "Entered BRIX",
            "Acceptable range",
            "Amount below or above the range",
        ),
    ),
    RuleDefinition(
        rule_id="CC-RULE-006",
        name="Excessive Gap Between Steps",
        description=(
            "Checks the whole-minute gap between Type I completion and Type IV "
            "start against the allowed maximum."
        ),
        logic_summary=(
            "Applies when Type I and Type IV are both used.",
            "Compare EndTime1 with StartTime4.",
            "Times are whole-minute military time in HH:MM format.",
            (
                "Generate an exception only when the calculated gap is greater "
                "than the configured allowed gap."
            ),
            "A gap equal to the setting passes.",
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
            "Actual gap",
            "Configured allowed gap",
            "Minutes over the setting",
        ),
    ),
    RuleDefinition(
        rule_id="CC-RULE-007",
        name="No Type IV During Active Precipitation",
        description=(
            "Identifies active precipitation events where no Type IV fluid "
            "amount was recorded."
        ),
        logic_summary=(
            "Treat blank Precipitation as no active precipitation.",
            "Treat any capitalization of None as no active precipitation.",
            "Treat Type4Used as no Type IV when blank or numerically 0.",
            (
                "Generate an exception when Precipitation contains an actual "
                "condition and Type4Used is blank or 0."
            ),
        ),
        settings_defaults=(
            "None",
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
    ),
    RuleDefinition(
        rule_id="CC-RULE-008",
        name="Excessive Type I",
        description=(
            "Checks the adjusted Type I application rate against its configured "
            "maximum."
        ),
        logic_summary=(
            "Use the CSV’s existing whole-number ProcessTime1 value directly.",
            "Do not recalculate duration from StartTime1 and EndTime1.",
            "Adjusted Type I rate = Type1Used / (ProcessTime1 + 1).",
            (
                "The added minute conservatively accounts for whole-minute "
                "recording precision."
            ),
            (
                "Generate an exception only when the adjusted rate is greater "
                "than the configured maximum."
            ),
            "A rate equal to the maximum passes.",
        ),
        settings_defaults=(
            "Maximum Type I rate",
            "Default: 60 gallons per minute",
            "Adjustable",
            "Mandatory",
        ),
        exception_message="Excessive Type I.",
        output_details=(
            "Type I gallons used",
            "Recorded ProcessTime1",
            "Adjusted calculation time",
            "Adjusted gallons per minute",
            "Configured maximum",
        ),
    ),
    RuleDefinition(
        rule_id="CC-RULE-009",
        name="Excessive Type IV",
        description=(
            "Checks the adjusted Type IV application rate against its "
            "independently configured maximum."
        ),
        logic_summary=(
            "Use the CSV’s existing whole-number ProcessTime4 value directly.",
            "Do not recalculate duration from StartTime4 and EndTime4.",
            "Adjusted Type IV rate = Type4Used / (ProcessTime4 + 1).",
            (
                "Generate an exception only when the adjusted rate is greater "
                "than the configured maximum."
            ),
            "A rate equal to the maximum passes.",
        ),
        settings_defaults=(
            "Maximum Type IV rate",
            "Default: 30 gallons per minute",
            "Adjustable independently from Type I",
            "Mandatory",
        ),
        exception_message="Excessive Type IV.",
        output_details=(
            "Type IV gallons used",
            "Recorded ProcessTime4",
            "Adjusted calculation time",
            "Adjusted gallons per minute",
            "Configured maximum",
        ),
    ),
    RuleDefinition(
        rule_id="CC-RULE-010",
        name="Excessive Event Time",
        description=(
            "Checks the recorded deicing process time, with an optional "
            "inter-step gap, against the configured maximum."
        ),
        logic_summary=(
            "If only Type I is used, event time = ProcessTime1.",
            (
                "If Type I and Type IV are used, event time = ProcessTime1 + "
                "ProcessTime4."
            ),
            (
                "The optional gap setting may add the gap between EndTime1 and "
                "StartTime4."
            ),
            (
                "Generate an exception only when event time is greater than the "
                "configured maximum."
            ),
            "Event time equal to the maximum passes.",
        ),
        settings_defaults=(
            "Maximum event time",
            "Default: 30 minutes",
            "Include gap between Type I and Type IV: On or Off",
            "Default Include Gap value: Off",
            "Mandatory",
        ),
        exception_message="Excessive event time.",
        output_details=(
            "ProcessTime1",
            "ProcessTime4 when applicable",
            "Gap when included",
            "Calculated event time",
            "Configured maximum",
            "Minutes over the maximum",
        ),
    ),
    RuleDefinition(
        rule_id="CC-RULE-011",
        name="Incorrect Type IV Concentration",
        description=(
            "Checks a recorded Type IV concentration against the requirement "
            "for the selected fluid."
        ),
        logic_summary=(
            "Run only when Type4Used is greater than 0.",
            "Use the Type IV fluid selected for the gateway.",
            "Cryotech Polar Guard Xtend requires 100% concentration.",
            "Accept 100, 100.0, and 100%.",
            "Any other value fails.",
        ),
        settings_defaults=(
            "Type IV fluid is gateway-selectable",
            "Default Type IV fluid: Cryotech Polar Guard Xtend",
            "Required concentration for the default fluid: 100%",
            "Mandatory",
        ),
        exception_message="Incorrect Type IV concentration.",
        output_details=(
            "Selected Type IV fluid",
            "Entered Type IV concentration",
            "Required concentration",
        ),
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
                "When AircraftType = 1, TailNumber must match the UPS format "
                "NxxxUP, where each x is a digit."
            ),
            "Normalized UPS pattern: ^N[0-9]{3}UP$",
            "When AircraftType = 2:",
            "TailNumber must not be blank.",
            "TailNumber must not match the UPS NxxxUP pattern.",
            (
                "Apply only a loose syntax check allowing letters, numbers, "
                "and hyphens."
            ),
            (
                "Do not perform FAA, ICAO, registry, country-specific, "
                "carrier-list, or ownership validation."
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
            "AircraftType",
            "Entered TailNumber",
            "Required format or reason for failure",
        ),
    ),
    RuleDefinition(
        rule_id="CC-RULE-013",
        name="Pass Overlap",
        description=(
            "Checks that a Type IV pass does not begin before the Type I pass "
            "ends, while accounting for events that cross midnight."
        ),
        logic_summary=(
            "Applies when both Type I and Type IV are used.",
            "Equality between EndTime1 and StartTime4 passes.",
            "Type IV must not begin before Type I ends.",
            (
                "Use overall StartTime and EndTime to determine whether the "
                "event crossed midnight."
            ),
            (
                "If overall EndTime is earlier than overall StartTime, treat "
                "the event as crossing midnight and allow the Type IV time to "
                "roll into the next day."
            ),
            (
                "If the overall event did not cross midnight and StartTime4 is "
                "earlier than EndTime1, generate an exception."
            ),
            "Example overnight pass:",
            "EndTime1 = 23:59",
            "StartTime4 = 00:01",
            "Overall event crosses midnight",
            "Result: pass with a two-minute gap",
        ),
        settings_defaults=(
            "None",
            "Mandatory",
        ),
        exception_message="Pass overlap.",
        output_details=(
            "Overall event StartTime",
            "Overall event EndTime",
            "Type I EndTime1",
            "Type IV StartTime4",
            "Calculated overlap in minutes when an exception occurs",
        ),
    ),
)


def _validate_registry() -> None:
    expected_ids = tuple(f"CC-RULE-{number:03d}" for number in range(1, 14))
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
