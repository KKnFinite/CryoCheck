# CryoCheck Rules

This document is the approved specification for CryoCheck’s audit rules.
CC-RULE-001 through CC-RULE-007 are implemented and execute automatically
after a structurally valid CSV upload. CC-RULE-008 through CC-RULE-013 remain
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

**Implementation status:** Documented — implementation pending

### Logic

- Use the CSV’s existing whole-number ProcessTime1 value directly.
- Do not recalculate duration from StartTime1 and EndTime1.
- Adjusted Type I rate = Type1Used / (ProcessTime1 + 1).
- The added minute conservatively accounts for whole-minute recording
  precision.
- Generate an exception only when the adjusted rate is greater than the
  configured maximum.
- A rate equal to the maximum passes.

### Settings

- Maximum Type I rate
- Default: 60 gallons per minute
- Adjustable
- Mandatory

### Exception message

`Excessive Type I.`

### Output details

- Type I gallons used
- Recorded ProcessTime1
- Adjusted calculation time
- Adjusted gallons per minute
- Configured maximum

## CC-RULE-009 — Excessive Type IV

**Implementation status:** Documented — implementation pending

### Logic

- Use the CSV’s existing whole-number ProcessTime4 value directly.
- Do not recalculate duration from StartTime4 and EndTime4.
- Adjusted Type IV rate = Type4Used / (ProcessTime4 + 1).
- Generate an exception only when the adjusted rate is greater than the
  configured maximum.
- A rate equal to the maximum passes.

### Settings

- Maximum Type IV rate
- Default: 30 gallons per minute
- Adjustable independently from Type I
- Mandatory

### Exception message

`Excessive Type IV.`

### Output details

- Type IV gallons used
- Recorded ProcessTime4
- Adjusted calculation time
- Adjusted gallons per minute
- Configured maximum

## CC-RULE-010 — Excessive Event Time

**Implementation status:** Documented — implementation pending

### Logic

- If only Type I is used, event time = ProcessTime1.
- If Type I and Type IV are used, event time = ProcessTime1 + ProcessTime4.
- The optional gap setting may add the gap between EndTime1 and StartTime4.
- Generate an exception only when event time is greater than the configured
  maximum.
- Event time equal to the maximum passes.

### Settings

- Maximum event time
- Default: 30 minutes
- Include gap between Type I and Type IV: On or Off
- Default Include Gap value: Off
- Mandatory

### Exception message

`Excessive event time.`

### Output details

- ProcessTime1
- ProcessTime4 when applicable
- Gap when included
- Calculated event time
- Configured maximum
- Minutes over the maximum

## CC-RULE-011 — Incorrect Type IV Concentration

**Implementation status:** Documented — implementation pending

### Logic

- Run only when Type4Used is greater than 0.
- Use the Type IV fluid selected for the gateway.
- Cryotech Polar Guard Xtend requires 100% concentration.
- Accept 100, 100.0, and 100%.
- Any other value fails.

### Settings/defaults

- Type IV fluid is gateway-selectable
- Default Type IV fluid: Cryotech Polar Guard Xtend
- Required concentration for the default fluid: 100%
- Mandatory

### Exception message

`Incorrect Type IV concentration.`

### Output details

- Selected Type IV fluid
- Entered Type IV concentration
- Required concentration

## CC-RULE-012 — Incorrect Tail Number

**Implementation status:** Documented — implementation pending

### Logic

- Trim surrounding whitespace and compare letters case-insensitively.
- When AircraftType = 1, TailNumber must match the UPS format NxxxUP, where
  each x is a digit.
- Normalized UPS pattern: ^N[0-9]{3}UP$
- When AircraftType = 2:
  - TailNumber must not be blank.
  - TailNumber must not match the UPS NxxxUP pattern.
  - Apply only a loose syntax check allowing letters, numbers, and hyphens.
  - Do not perform FAA, ICAO, registry, country-specific, carrier-list, or
    ownership validation.
- Generate an exception when the tail does not meet the requirement for its
  aircraft type.

### Settings

- None
- Mandatory

### Exception message

`Incorrect tail number.`

### Output details

- AircraftType
- Entered TailNumber
- Required format or reason for failure

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
