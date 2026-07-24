# CryoCheck

CryoCheck is a standalone deice log audit application. This repository contains the production-ready Flask application, Neon PostgreSQL integration, an in-memory CSV audit workflow, optional local accounts with private Personal Settings, the approved audit-rule registry, and in-memory Excel exception export. All fourteen approved rules execute and produce reviewable Results.

## Purpose

The application provides a focused workflow for importing and auditing deice log data without requiring an account. Its public Rules page documents implemented and pending checks. Optional accounts let users save private settings without changing CryoCheck’s immutable Default values.

## Windows setup

The following commands are intended for PowerShell in VS Code on Windows. Python 3.10 or newer is required.

### Create a virtual environment

```powershell
py -m venv .venv
```

### Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell prevents local activation scripts from running, set an appropriate execution policy for your user account before retrying.

### Install requirements

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Configure the environment

```powershell
Copy-Item .env.example .env
```

Update `SECRET_KEY` in `.env` with a long, random value and replace the sample `DATABASE_URL` with the connection string from the Neon console. The default `FLASK_CONFIG=development` profile is appropriate for local work.

The local `.env` file contains secrets and must never be committed. It is excluded by `.gitignore`; `.env.example` contains placeholders only.

## Neon PostgreSQL

Copy the complete Neon connection string into `DATABASE_URL`, including the SSL query parameters supplied by Neon. CryoCheck accepts both `postgres://` and `postgresql://` prefixes and configures SQLAlchemy to use psycopg 3. Credentials, hosts, and passwords are never hard-coded in the application.

With the virtual environment active and `.env` configured, verify connectivity without starting the web server:

```powershell
flask db-check
```

The command runs `SELECT 1` and prints a success message. Connection failures return a nonzero exit code with a sanitized diagnostic that does not expose the database URL or credentials. Automated tests use an isolated in-memory SQLite database and never connect to Neon.

## CSV import workflow

The landing page accepts one `.csv` file through file browsing or drag and drop. CryoCheck validates its structure, keeps the complete source dataset in memory with original column order, row order, source strings, and physical CSV row numbers, then immediately audits every row. Results show audit metrics, ordered exceptions, any non-exception unable-to-evaluate warnings, and the first 10 source rows.

Uploaded content, audit results, and exceptions are not written to disk, stored in the browser session, persisted to Neon, retained as audit history, or logged. Source values are never normalized or corrected. A Results page with exceptions carries a signed, time-limited export snapshot back to CryoCheck only when the user explicitly requests an export; the server retains no export state between requests.

The current pipeline executes:

- `CC-RULE-001` — Application Entry Proceeds Event
- `CC-RULE-002` — Late Entry
- `CC-RULE-003` — Incorrect Freeze Point
- `CC-RULE-004` — 18 Degree Buffer Not Met
- `CC-RULE-005` — BRIX Out of Range
- `CC-RULE-006` — Excessive Gap Between Steps
- `CC-RULE-007` — No Type IV During Active Precipitation
- `CC-RULE-008` — Excessive Type I

The first two rules compare the local `ApplicationDate + StartTime` event timestamp with local `DateCreated`; UTC columns are not used. Blank or malformed required timestamps produce clearly separated unable-to-evaluate warnings, not rule exceptions. `CC-RULE-002` uses the active profile’s 24- or 48-hour late-entry threshold and fails at exact equality.

The Type I rules run only when `Type1Used` is numerically greater than zero. `CC-RULE-003` compares `FreezingPoint1` with the exact manufacturer value for the recorded whole-number concentration. `CC-RULE-004` calculates the buffer from `AmbientTemp` and that authoritative chart value, never from the entered freeze point; a buffer below 18.0°F fails and an exact 18.0°F passes. Decimal parsing and comparisons use Python `Decimal`, so equivalent numeric forms compare equally without rounding.

Cryotech Polar Plus LT manufacturer data is stored as a version-controlled, read-only CSV under `app/reference_data` and loaded by the reusable registry in `app/services/type1_fluids.py`. Loading profiles requires no database or network access. The chart is validated at startup for its schema, malformed or missing values, duplicate concentrations, and complete concentration coverage. Its current reference-data boundary is whole-number concentrations from 0 through 70%; non-whole and unsupported concentrations produce unable-to-evaluate warnings rather than exceptions.

Type IV fluid profiles are also version-controlled, read-only reference data. The reusable registry in `app/services/type4_fluids.py` validates fluid names, finite Decimal BRIX ranges, and required Decimal concentrations without database or network access. `CC-RULE-005` runs only for positive `Type4Used`, compares `Type4ABrix` without rounding, and treats the Cryotech Polar Guard Xtend range of 34.6–36.6 as inclusive. `CC-RULE-011` independently requires its recorded Type IV concentration to equal that profile’s 100% requirement, accepting one optional trailing percent sign and never rounding values into compliance. Missing or invalid rule inputs and unknown or invalid fluid profiles produce rule-specific unable-to-evaluate warnings.

`CC-RULE-006` runs only when both `Type1Used` and `Type4Used` are positive. It compares `EndTime1` with `StartTime4` using exact whole-minute HH:MM arithmetic and fails only when the calculated gap exceeds the active profile’s Allowed Gap; equality passes and Default is 5 minutes. Overall `StartTime` and `EndTime` distinguish a positive overnight gap from a same-day overlap. Same-day overlaps remain a zero-gap condition for this rule and are evaluated independently by `CC-RULE-013`, while missing or malformed values needed for evaluation produce non-exception warnings.

`CC-RULE-007` treats blank, whitespace-only, and case-insensitive `None` precipitation as inactive; every other nonblank source value is active without requiring a fixed condition list. During active precipitation, blank or Decimal-equivalent zero `Type4Used` produces an exception, positive usage passes, and malformed, non-finite, or negative usage produces an unable-to-evaluate warning. Original source text is preserved for Results. The rule has no setting, so anonymous and signed-in audits behave identically.

`CC-RULE-008` runs only for positive `Type1Used` and uses the CSV’s existing whole-minute `ProcessTime1` value without recalculating it from start/end times. The adjusted rate is `Type1Used / (ProcessTime1 + 1)` using Decimal-safe arithmetic. A rate equal to the active profile’s maximum passes; only a greater rate fails. Default is 60 GPM, and signed-in Personal Settings apply immediately to the next upload. Malformed or non-finite usage, invalid whole-minute process time, and invalid runtime maximum settings produce unable-to-evaluate warnings rather than exceptions.

`CC-RULE-010` sums the original whole-minute process time for every positively used fluid step and compares the result with the active profile’s maximum event time. Default is 30 minutes. Type I-only and Type IV-only rows are both evaluated. For combined events, the Include Gap setting optionally adds the whole-minute Type I-to-Type IV gap, including a recognized overnight gap; same-day overlaps contribute zero and are evaluated independently by `CC-RULE-013`. Equality passes, and invalid required inputs produce unable-to-evaluate warnings.

`CC-RULE-012` validates trimmed, case-insensitive tail-number requirements for numeric AircraftType 0, 1, and 2 without external registry, web, API, or ownership checks. Type 0 requires a blank tail and nonblank Notes, Type 1 requires UPS format `NxxxUP`, and Type 2 requires a nonblank non-UPS value containing only letters, numbers, and hyphens with at least one letter or number. Original CSV values remain unchanged for Results display.

`CC-RULE-013` runs only when both fluid usages are numerically positive. Equality and a later Type IV start pass. When `StartTime4` is earlier than `EndTime1`, valid overall times determine whether the event crossed midnight: an earlier overall `EndTime` means the Type IV start belongs to the next day and passes; otherwise CryoCheck reports the exact whole-minute overlap. Invalid usage or required time values produce unable-to-evaluate warnings. Rule 006 continues treating overlap as no excessive gap, and Rule 010 continues adding zero gap when Include Gap is On.

`CC-RULE-014` applies to AircraftType 1 and 2 rows with positive Type IV usage and blank or nonpositive Type I usage. Notes must deterministically contain a Type I reference (`Type I`, `Type 1`, or `T1`), approved application wording, and a whole-number identifier associated with `truck`. The documented truck must differ numerically from the current whole-number `TruckNumber`; leading zeros are ignored, while any different identifier passes when several trucks are documented. Matching normalizes case, whitespace, and punctuation only and never uses AI, fuzzy interpretation, web lookups, or external validation.

## Excel exception export

Results with exceptions provide a checkbox for every finding, Select All and Clear All controls, and Export Selected and Export All actions. Exports include exceptions only; unable-to-evaluate warnings are never included.

CryoCheck validates every selected identifier against the signed snapshot for that Results page, preserves CSV-row then Rule-ID ordering, and rejects expired, malformed, duplicate, or unrelated selections. Snapshots expire after `EXPORT_TOKEN_MAX_AGE_SECONDS`, which defaults to 1800 seconds.

Each download is generated entirely in memory as `CryoCheck_Exceptions_YYYYMMDD_HHMMSS.xlsx`. Its `Exceptions` sheet contains the source-identification fields shown in Results, active settings profile, rule metadata, individual rule-detail columns, and combined details text. The header is frozen, filtered, styled, and wrapped with readable column widths. Text beginning with `=`, `+`, `-`, or `@` is escaped before being written to prevent Excel formula injection. Workbooks and export state are never saved to disk or Neon.

The upload limit is configured with `MAX_UPLOAD_MB` and defaults to 10 MB. The same request-size protection covers signed export submissions. Oversized uploads and exports receive branded HTTP 413 responses without echoing submitted data.

## Optional accounts

Accounts are optional. Anonymous users can continue to import and audit CSV files, review and export exception Results, view the Rules catalog, and view the built-in Default settings.

- Create an account at `/register`.
- Sign in at `/login`.
- Sign out with the Logout action in the application header.
- Account names are unique without regard to casing.
- CryoCheck does not request or store email addresses.
- Password recovery is not available. Users must retain their own passwords securely.
- Passwords are stored only as Werkzeug scrypt hashes.

Login and registration are protected by CSRF validation and IP-based rate limits. The current single-instance Render deployment uses in-memory rate-limit storage. Counters reset when the process restarts and are not shared across multiple application instances; move to a shared supported backend before scaling horizontally.

## Default and Personal Settings

The `/settings` page is public. Anonymous users see the authoritative, immutable **Default** profile in read-only form. Default is the fallback for all anonymous use and is never stored as an editable database row.

Registering creates exactly one private `UserSettings` record copied from the current Default values. A signed-in user can explicitly save changes to that record or reset it to the current Default. Personal changes affect only the owning account and never modify Default or another user’s settings. Anonymous audits use **Default**; signed-in audits use that account’s **Personal** profile. The Personal late-entry threshold affects `CC-RULE-002`, the active Type I fluid selection affects `CC-RULE-003` and `CC-RULE-004`, the active Type IV fluid selection affects `CC-RULE-005` and `CC-RULE-011`, the Personal Allowed Gap affects `CC-RULE-006`, the Personal maximum Type I and Type IV rates independently affect `CC-RULE-008` and `CC-RULE-009`, and the Personal maximum event time and Include Gap setting affect `CC-RULE-010` immediately on the next upload; settings for pending rules are retained for later implementation.

## Rules catalog

The read-only Rules page at `/rules` documents all 14 approved audit checks in permanent rule-ID order and shows each implementation status. The application registry in `app/services/rules.py` and [the detailed rules specification](docs/rules.md) must remain synchronized. `CC-RULE-001` through `CC-RULE-014` are implemented.

### Required baseline columns

All baseline columns must be present, but their order may vary. Additional columns are allowed and reported in the summary.

```text
RecordID
ApplicationNumber
GatewayUID
GatewayCode
RRDD
ApplicationDate
StartTime
EndTime
ElapsedTime
ModifiedBy
ModifiedByName
LastModified
CreatedBy
CreatedByName
DateCreated
AircraftType
TailNumber
Reason
Precipitation
AmbientTemp
DewPoint
OtherConditions
EquipmentOwnedBy
ConductedBy
TruckNumber
Operator
Driver
Posted
VendorName
AuthorizedBy
DialToTemperatureTruck
DateCreatedUTC
LastModifiedUTC
LiquidUOM
TempUOM
Type1Used
Type1SKU
Type1Concentration
FreezingPoint1
StartTime1
EndTime1
ProcessTime1
FromInventory1
ForcedAir1
LowFlow1
Type4Used
Type4SKU
Type4AConcentration
FreezingPoint4
StartTime4
EndTime4
ProcessTime4
FromInventory4
ForcedAir4
LowFlow4
Type4ABrix
Notes
```

### Run the application

```powershell
python run.py
```

Open `http://127.0.0.1:5000` in a browser. The database-independent health endpoint is available at `http://127.0.0.1:5000/health`.

### Run tests

```powershell
pytest -q
```

## Configuration profiles

- `development` enables Flask debugging for local work.
- `testing` enables Flask testing behavior and is used by pytest.
- `production` explicitly disables debugging, testing behavior, and exception propagation, and enables secure cookie transport.

Select a profile with the `FLASK_CONFIG` environment variable.

CryoCheck provides branded, detail-safe responses for HTTP 400, 403, 404, 413, 429, and 500 failures. The conventional `/favicon.ico` path serves the CryoCheck snowflake favicon.

## Database migrations

The initial migration creates the `users` and `user_settings` tables. The migration repository was initialized once with `flask db init`; do not run that initialization command again.

Apply committed migrations locally:

```powershell
flask db upgrade
flask db-check
```

Workflow for future model changes:

```powershell
flask db migrate -m "Describe the model change"
flask db upgrade
```

Review every generated revision before applying it. Production migrations must be committed with the related model change and applied before the new application code handles production traffic.

## Render deployment

Create a Render Web Service connected to this repository and use:

- Build command: `pip install -r requirements.txt && flask db upgrade`
- Start command: `gunicorn run:app`
- Health check path: `/health`

Configure these Render environment variables:

- `DATABASE_URL`: the Neon production connection string, including its SSL parameters
- `SECRET_KEY`: a secure production secret
- `FLASK_CONFIG=production`
- `MAX_UPLOAD_MB`: optional CSV upload limit in megabytes; defaults to `10`

The `/health` endpoint intentionally remains database-independent so Render can verify the web process during a temporary database outage. Use `flask db-check` separately when database connectivity must be confirmed. The build must fail rather than start application code against an unapplied schema migration.
