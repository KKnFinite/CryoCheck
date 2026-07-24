# CryoCheck Rules

This document is the approved specification for CryoCheck’s audit rules.
CC-RULE-001 through CC-RULE-012 are implemented and execute automatically
after a structurally valid CSV upload. CC-RULE-013 through CC-RULE-014 remain
implementation pending.

The in-application registry and this documentation must remain synchronized.
Rule IDs are permanent: they must never be reused or renumbered. No rule
categories are used. Rules are mandatory unless a future specification
explicitly says otherwise.

Audits use original local `ApplicationDate`, `StartTime`, and `DateCreated`
values in memory. UTC fields are not used. Anonymous audits use the immutable
Default settings profile; signed-in audits use that account’s private Personal
Settings. Uploaded rows, audit results, and exceptions are not persisted.

## CC-RULE-001 — Application Entry Proceeds Event

**Implementation status:** Implemented

### Logic

- Use local timestamps only.
- Compare local DateCreated with local ApplicationDate + StartTime.
- Do not use UTC fields.
- Generate an exception when DateCreated is earlier than the application event.

### Settings

- None.
- Mandatory.

### Exception message

`Application entry proceeds event.`

### Output details

- Application date/time
- Entry date/time
- How far before the application event the entry was created

## CC-RULE-002 — Late Entry

**Implementation status:** Implemented

### Logic

- Compare local DateCreated with local ApplicationDate + StartTime.
- Generate an exception when the delay is greater than or equal to the
  configured threshold.

### Settings

- Allowed threshold: 24 hours or 48 hours
- Default: 24 hours
- Exactly 24 hours fails when set to 24
- Exactly 48 hours fails when set to 48
- Mandatory

### Exception message

`Late entry.`

### Output details

- Application date/time
- Entry date/time
- Configured threshold
- Actual delay
- Amount beyond the threshold

## CC-RULE-003 — Incorrect Freeze Point

**Implementation status:** Implemented

### Logic

- Runs only when Type1Used is numerically greater than 0.
- Use the Type I fluid selected in active audit settings.
- Use the recorded Type1Concentration to find the exact expected freeze point
  from that fluid’s manufacturer chart.
- Concentrations 60 and 60.0 both select the 60% chart row.
- The current Cryotech Polar Plus LT chart supports whole-number
  concentrations from 0–70%.
- A non-whole or unsupported concentration is unable to evaluate.
- Compare the expected value with FreezingPoint1.
- Numerically equal decimal forms such as -50 and -50.0 are equivalent.
- Any other difference fails.

### Settings/defaults

- Type I fluid is gateway-selectable
- Default Type I fluid: Cryotech Polar Plus LT
- Mandatory

### Exception message

`Incorrect freeze point.`

### Output details

- Selected Type I fluid
- Recorded concentration
- Entered freeze point
- Expected manufacturer-chart freeze point
- Concise comparison

## CC-RULE-004 — 18 Degree Buffer Not Met

**Implementation status:** Implemented

### Logic

- Runs only when Type1Used is numerically greater than 0.
- Required buffer is 18.0°F.
- Buffer = AmbientTemp minus the correct manufacturer-chart Type I freeze
  point.
- Always use the authoritative manufacturer-chart freeze point, never an
  incorrectly entered FreezingPoint1 value.
- A buffer below 18.0°F fails.
- A buffer of 18.0°F or greater passes.
- The current Cryotech Polar Plus LT chart supports whole-number
  concentrations from 0–70%.
- A non-whole or unsupported concentration is unable to evaluate.
- Do not create a false buffer exception solely because the entered freeze
  point is wrong.
- If the entered freeze point is wrong but the correct chart value passes the
  buffer, only CC-RULE-003 applies.
- If the correct chart value still fails the buffer, CC-RULE-004 applies;
  CC-RULE-003 also applies when the entered value is wrong.

### Settings

- Required buffer: fixed at 18.0°F
- Mandatory

### Exception message

`18 degree buffer not met.`

### Output details

- Selected Type I fluid
- Recorded concentration
- Outside air temperature
- Authoritative manufacturer-chart freeze point
- Actual calculated buffer
- Required buffer
- Amount short

## CC-RULE-005 — BRIX Out of Range

**Implementation status:** Implemented

### Logic

- Runs only when Type4Used is numerically greater than 0.
- Use the Type IV fluid selected in active audit settings.
- Parse Type4ABrix using Decimal without rounding.
- For Cryotech Polar Guard Xtend, the acceptable range is 34.6–36.6
  inclusive.
- Values below 34.6 or above 36.6 fail.
- The exact lower and upper boundaries pass.
- Malformed applicability, missing or invalid BRIX, and unknown fluid profiles
  are unable to evaluate.

### Settings/defaults

- Type IV fluid is selected in active audit settings
- Default Type IV fluid: Cryotech Polar Guard Xtend
- Default range: 34.6–36.6 inclusive
- Mandatory

### Exception message

`BRIX out of range.`

### Output details

- Selected Type IV fluid
- Entered BRIX
- Acceptable inclusive range
- Whether the value is below or above the range
- Exact amount below or above the nearest boundary
- Concise comparison

## CC-RULE-006 — Excessive Gap Between Steps

**Implementation status:** Implemented

### Logic

- Applies only when Type1Used and Type4Used are both numerically greater than
  0.
- Compare EndTime1 with StartTime4.
- Use exact whole-minute military HH:MM arithmetic.
- Generate an exception only when the calculated gap is greater than the
  configured allowed gap.
- A gap equal to the setting passes.
- When the overall event crosses midnight, treat an earlier StartTime4 as
  occurring on the next calendar day.
- An earlier StartTime4 during a same-day event is an overlap left to pending
  CC-RULE-013, not a 24-hour gap.
- Blank or malformed required values produce an unable-to-evaluate warning when
  applicability is positive.

### Settings

- Allowed Gap accepts 0–99 whole minutes
- Default: 5 minutes
- With a setting of 5, gaps of 0–5 pass and 6 or more fail
- Mandatory

### Exception message

`Excessive gap between steps.`

### Output details

- Type I end time
- Type IV start time
- Actual gap in whole minutes
- Configured Allowed Gap
- Whole minutes over the setting
- Concise comparison

## CC-RULE-007 — No Type IV During Active Precipitation

**Implementation status:** Implemented

### Logic

- Treat blank or whitespace-only Precipitation as no active precipitation.
- After trimming whitespace, treat any capitalization of None as no active
  precipitation.
- Treat every other nonblank precipitation value as active.
- Treat blank or numerically zero Type4Used as no recorded Type IV.
- Generate an exception when precipitation is active and Type4Used is blank or
  numerically zero.
- Positive Type4Used passes; malformed, non-finite, or negative Type4Used is
  unable to evaluate when precipitation is active.
- When precipitation is not active, skip without evaluating Type4Used.

### Settings

- No configurable setting.
- Mandatory

### Exception message

`No Type IV during active precipitation.`

### Output details

- Recorded precipitation
- Type IV amount recorded
- Statement that no Type IV was recorded during active precipitation

## CC-RULE-008 — Excessive Type I

**Implementation status:** Implemented

### Logic

- Run only when Type1Used is numerically greater than 0.
- Blank, zero, or negative Type1Used skips the rule; malformed or non-finite
  Type1Used is unable to evaluate.
- Use the CSV’s existing whole-number ProcessTime1 value directly.
- Do not recalculate duration from StartTime1 and EndTime1.
- ProcessTime1 must be finite, nonnegative, and numerically a whole number when
  Type I usage is positive.
- Adjusted Type I rate = Type1Used / (ProcessTime1 + 1).
- The added minute conservatively accounts for whole-minute recording
  precision.
- Use Decimal-safe arithmetic without rounding before comparison.
- Generate an exception only when the adjusted rate is greater than the
  configured maximum.
- A rate equal to the maximum passes.
- Invalid required values or an invalid runtime maximum produce an
  unable-to-evaluate warning, not an exception.

### Settings

- Maximum Type I rate: active profile setting
- Default: 60 gallons per minute
- Personal Settings apply to the next signed-in upload
- Mandatory

### Exception message

`Excessive Type I.`

### Output details

- Type I gallons used
- Recorded ProcessTime1
- Adjusted calculation time
- Adjusted gallons per minute
- Configured maximum
- Comparison statement

## CC-RULE-009 — Excessive Type IV

**Implementation status:** Implemented

### Logic

- Run only when Type4Used is numerically greater than 0.
- Blank, zero, or negative Type4Used skips the rule; malformed or non-finite
  Type4Used is unable to evaluate.
- Use the CSV’s existing whole-number ProcessTime4 value directly.
- Do not recalculate duration from StartTime4 and EndTime4.
- ProcessTime4 must be finite, nonnegative, and numerically a whole number when
  Type IV usage is positive.
- Adjusted Type IV rate = Type4Used / (ProcessTime4 + 1).
- The added minute conservatively accounts for whole-minute recording
  precision.
- Use Decimal-safe arithmetic without rounding before comparison.
- Generate an exception only when the adjusted rate is greater than the
  configured maximum.
- A rate equal to the maximum passes.
- Invalid required values or an invalid runtime maximum produce an
  unable-to-evaluate warning, not an exception.

### Settings

- Maximum Type IV rate: active profile setting
- Default: 30 gallons per minute
- Adjustable independently from the Type I maximum
- Personal Settings apply to the next signed-in upload
- Mandatory

### Exception message

`Excessive Type IV.`

### Output details

- Type IV gallons used
- Recorded ProcessTime4
- Adjusted calculation time
- Adjusted gallons per minute
- Configured maximum
- Comparison statement

## CC-RULE-010 — Excessive Event Time

**Implementation status:** Implemented

### Logic

- Parse Type1Used and Type4Used with Decimal-safe logic; a step is used only
  when its recorded amount is greater than 0.
- Blank, zero, or negative usage excludes that step; malformed or non-finite
  usage is unable to evaluate.
- When neither step is positively used, skip without an exception or warning.
- If only Type I is used, event time = ProcessTime1.
- If only Type IV is used, event time = ProcessTime4.
- If Type I and Type IV are used, event time = ProcessTime1 + ProcessTime4.
- Use original process times directly without the one-minute rate adjustment
  from CC-RULE-008 and CC-RULE-009.
- Every positively used step requires a finite, nonnegative, numerically whole
  process time.
- When Include Gap is Off, do not add a gap or require step or overall clock
  times.
- When Include Gap is On and both steps are used, add the whole-minute gap from
  EndTime1 to StartTime4.
- Use overall StartTime and EndTime to recognize an overnight gap when
  StartTime4 is earlier than EndTime1.
- A same-day overlap contributes a 0-minute gap and remains assigned to pending
  CC-RULE-013.
- Type I-only and Type IV-only events never include a gap, even when Include
  Gap is On.
- Invalid required process, clock, maximum, or Include Gap values produce an
  unable-to-evaluate warning.
- Generate an exception only when event time is greater than the configured
  maximum.
- Event time equal to the maximum passes.

Type I-only events use only `ProcessTime1`; Type IV-only events use only
`ProcessTime4`. For combined events with Include Gap Off, invalid or missing
step and overall clock times do not block this rule because they are not used.

With Include Gap On for a combined event, same-day forward gaps are added
directly. When `StartTime4` is earlier than `EndTime1`, valid overall
`StartTime` and `EndTime` determine whether to add an overnight gap or use a
0-minute same-day-overlap gap. Ambiguous or invalid required clock values
produce a warning.

### Settings

- Maximum event time: active profile setting
- Default: 30 minutes
- Valid range: whole numbers from 1 through 999 minutes
- Include gap between Type I and Type IV: On or Off
- Default Include Gap value: Off
- Personal Settings apply to the next signed-in upload
- Mandatory

### Exception message

`Excessive event time.`

### Output details

- Type I usage status
- Type IV usage status
- Applicable original process times
- Include Gap setting
- Included gap and source clock times when applicable
- Overlap handling when a 0-minute gap is used
- Calculated event time
- Configured maximum event time
- Minutes over the maximum
- Comparison statement

## CC-RULE-011 — Incorrect Type IV Concentration

**Implementation status:** Implemented

### Logic

- Run only when Type4Used is numerically greater than 0; blank, zero, or
  negative usage skips.
- Malformed or non-finite Type4Used is unable to evaluate without blocking
  other Type IV rules.
- Use the required concentration from the Type IV fluid selected in the active
  audit settings.
- Cryotech Polar Guard Xtend requires exactly 100% concentration.
- Accept a finite numeric concentration with or without one optional trailing
  percent sign, including surrounding whitespace.
- Compare with Decimal-safe exact equality; do not interpret fractions as
  percentages and do not round into compliance.
- Blank, malformed, non-finite, unsupported, or ambiguously formatted
  concentration is unable to evaluate.
- An unavailable or invalid selected fluid requirement is unable to evaluate.
- Evaluate independently from CC-RULE-005 BRIX and CC-RULE-009 adjusted-rate
  validation.
- Generate an exception only when the exact concentrations differ.

Accepted representations of the required current concentration include `100`,
`100.0`, `100.00`, `100%`, `100.0%`, and whitespace-padded forms such as
` 100 % `. Values such as `1`, `99.999`, and `100.001` are compared exactly
as entered; they are not converted or rounded to 100%.

When positive Type IV usage is present, blank or invalid
`Type4AConcentration` produces an unable-to-evaluate warning. The original CSV
text is retained for Results details when a numeric value differs from the
profile requirement. BRIX, concentration, and adjusted-rate evaluation remain
independent so one rule's invalid input does not block the others.

### Settings/defaults

- Type IV fluid is selected by the active settings profile
- Default Type IV fluid: Cryotech Polar Guard Xtend
- Required concentration for the default fluid: 100%
- Mandatory

### Exception message

`Incorrect Type IV concentration.`

### Output details

- Selected Type IV fluid
- Entered Type IV concentration
- Required Type IV concentration
- Comparison statement

## CC-RULE-012 — Incorrect Tail Number

**Implementation status:** Implemented

### Logic

- Trim surrounding whitespace and compare letters case-insensitively.
- AircraftType must resolve numerically to whole-number 0, 1, or 2; equivalent
  Decimal forms such as 0.0, 1.0, and 2.00 are accepted.
- Blank, malformed, non-finite, non-whole, or unsupported AircraftType is
  unable to evaluate.
- When AircraftType = 0, TailNumber must be blank and Notes must contain
  nonblank text.
- Type I and Type IV usage do not affect AircraftType 0 validation.
- When AircraftType = 1, TailNumber must match the UPS format NxxxUP, where
  each x is a digit.
- Normalized UPS pattern: ^N[0-9]{3}UP$
- When AircraftType = 2:
  - TailNumber must not be blank.
  - TailNumber must not match the UPS NxxxUP pattern.
  - TailNumber may contain only letters, numbers, and hyphens and must contain
    at least one letter or number.
  - Leading, trailing, and repeated hyphens are allowed for AircraftType 2.
  - Do not perform FAA, ICAO, registry, country-specific, carrier-list,
    ownership, web, or API validation.
- Generate an exception when the tail does not meet the requirement for its
  aircraft type.

AircraftType 0 represents a non-aircraft spray. A blank TailNumber with
nonblank Notes passes, while a populated TailNumber, blank Notes, or both
produce one exception with the applicable failure reasons. Fluid usage does
not affect this path.

AircraftType 1 uses the exact case-insensitive UPS expression
`^N[0-9]{3}UP$` after trimming. AircraftType 2 accepts values such as
`AB-123`, `12345`, `-A123-`, and `A--123`, but rejects blank values, UPS-format
tails, hyphen-only values, spaces, underscores, slashes, and other unsupported
characters. CryoCheck does not query external registries or infer ownership.

### Settings

- None
- Mandatory

### Exception message

`Incorrect tail number.`

### Output details

- Original AircraftType
- Original TailNumber
- Original Notes for AircraftType 0
- Required format
- Specific failure reason

## CC-RULE-013 — Pass Overlap

**Implementation status:** Documented — implementation pending

### Logic

- Applies when both Type I and Type IV are used.
- Equality between EndTime1 and StartTime4 passes.
- Type IV must not begin before Type I ends.
- Use overall StartTime and EndTime to determine whether the event crossed
  midnight.
- If overall EndTime is earlier than overall StartTime, treat the event as
  crossing midnight and allow the Type IV time to roll into the next day.
- If the overall event did not cross midnight and StartTime4 is earlier than
  EndTime1, generate an exception.
- Example overnight pass:
  - EndTime1 = 23:59
  - StartTime4 = 00:01
  - Overall event crosses midnight
  - Result: pass with a two-minute gap

### Settings

- None
- Mandatory

### Exception message

`Pass overlap.`

### Output details

- Overall event StartTime
- Overall event EndTime
- Type I EndTime1
- Type IV StartTime4
- Calculated overlap in minutes when an exception occurs

## CC-RULE-014 — Type IV Without Type I Explanation Required

**Implementation status:** Documented — implementation pending

### Logic

- Future applicability: Type4Used is greater than 0 while Type1Used is blank,
  zero, or negative.
- Notes must deterministically state that Type I was applied by another truck
  and include that truck's numeric identifier.
- Recognize a Type I reference such as Type I, Type 1, or T1.
- Require language indicating Type I was applied, sprayed, completed,
  performed, or done.
- Require a whole-number identifier of any length clearly associated with the
  word truck.
- The documented other-truck number must differ from the current row's
  TruckNumber.
- An unrelated number not associated with the word truck does not qualify.
- Do not use AI or semantic guessing.

Examples that a future deterministic implementation should accept:

- `Type I applied by truck 12`
- `Truck 831996 completed Type 1`
- `T1 was sprayed by another truck, truck 7`

Examples that a future deterministic implementation should reject:

- `Type IV only`
- `Another truck applied Type I`
- `Type I completed`
- Type I applied by the current record's own truck number
- Notes containing an unrelated number without a truck-number association

### Settings

- No configurable setting.
- Mandatory

### Exception message

`Type IV applied without documented Type I truck.`

### Output details

- Type1Used
- Type4Used
- Current TruckNumber
- Entered Notes
- Deterministic qualification failure
