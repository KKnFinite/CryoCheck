# CryoCheck Rules

This document is the approved specification for CryoCheck’s audit rules.
These rules are documented but not executed yet.

The in-application registry and this documentation must remain synchronized.
Rule IDs are permanent: they must never be reused or renumbered. No rule
categories are used. Rules are mandatory unless a future specification
explicitly says otherwise.

Every rule currently has the implementation status **Documented —
implementation pending**.

## CC-RULE-001 — Application Entry Proceeds Event

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
- How far before the event the entry was created

## CC-RULE-002 — Late Entry

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

### Logic

- Applies to Type I.
- Use the Type I fluid selected for the gateway.
- Use the recorded Type1Concentration to find the exact expected freeze point
  from that fluid’s manufacturer chart.
- Compare the expected value with FreezingPoint1.
- Whole-number forms such as -39 and -39.0 are equivalent.
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

## CC-RULE-004 — 18 Degree Buffer Not Met

### Logic

- Applies to Type I only.
- Required buffer is 18°F.
- Buffer = AmbientTemp minus the correct manufacturer-chart Type I freeze
  point.
- A buffer of 18°F or greater passes.
- A buffer of 17°F or less fails.
- Do not create a false buffer exception solely because the entered freeze
  point is wrong.
- If the entered freeze point is wrong but the correct chart value passes the
  buffer, only CC-RULE-003 applies.
- If the correct chart value still fails the buffer, CC-RULE-004 applies;
  CC-RULE-003 also applies when the entered value is wrong.

### Settings

- Required buffer: fixed at 18°F
- Mandatory

### Exception message

`18 degree buffer not met.`

### Output details

- Outside air temperature
- Correct chart freeze point
- Actual buffer
- Required buffer
- Degrees short

## CC-RULE-005 — BRIX Out of Range

### Logic

- Applies to Type IV BRIX.
- Validate Type4ABrix against the acceptable range for the Type IV fluid
  selected for the gateway.
- For Cryotech Polar Guard Xtend, 34.6 through 36.6 inclusive passes.
- Below 34.6 or above 36.6 fails.

### Settings/defaults

- Type IV fluid is gateway-selectable
- Default Type IV fluid: Cryotech Polar Guard Xtend
- Default range: 34.6–36.6 inclusive
- Mandatory

### Exception message

`BRIX out of range.`

### Output details

- Selected Type IV fluid
- Entered BRIX
- Acceptable range
- Amount below or above the range

## CC-RULE-006 — Excessive Gap Between Steps

### Logic

- Applies when Type I and Type IV are both used.
- Compare EndTime1 with StartTime4.
- Times are whole-minute military time in HH:MM format.
- Generate an exception only when the calculated gap is greater than the
  configured allowed gap.
- A gap equal to the setting passes.

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
- Actual gap
- Configured allowed gap
- Minutes over the setting

## CC-RULE-007 — No Type IV During Active Precipitation

### Logic

- Treat blank Precipitation as no active precipitation.
- Treat any capitalization of None as no active precipitation.
- Treat Type4Used as no Type IV when blank or numerically 0.
- Generate an exception when Precipitation contains an actual condition and
  Type4Used is blank or 0.

### Settings

- None
- Mandatory

### Exception message

`No Type IV during active precipitation.`

### Output details

- Recorded precipitation
- Type IV amount recorded
- Statement that no Type IV was recorded during active precipitation

## CC-RULE-008 — Excessive Type I

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
