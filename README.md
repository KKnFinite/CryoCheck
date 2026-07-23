# CryoCheck

CryoCheck is a standalone deice log audit application. This repository contains the production-ready Flask application shell, Neon PostgreSQL integration, in-memory CSV inspection workflow, optional local accounts with private Personal Settings, and a read-only catalog of approved audit rule specifications. Rule execution, results, and Excel export will be added in later development phases.

## Purpose

The application provides a focused workflow for importing and safely inspecting deice log data without requiring an account. Its public Rules page documents the checks planned for future validation. Optional accounts let users save private settings for those future audits without changing CryoCheck’s immutable Default values.

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

The landing page accepts one `.csv` file through file browsing or drag and drop. CryoCheck parses the file in memory with pandas, validates its header, and shows an import summary plus the first 10 data rows. Uploaded content is not written to the repository, retained on the server, stored in Neon, or added to an upload history.

Importing only inspects the CSV structure and display values. It does not normalize values or run audit rules.

The upload limit is configured with `MAX_UPLOAD_MB` and defaults to 10 MB. Oversized requests receive a branded HTTP 413 response.

## Optional accounts

Accounts are optional. Anonymous users can continue to import CSV files, inspect import summaries, view the Rules catalog, and view the built-in Default settings.

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

Registering creates exactly one private `UserSettings` record copied from the current Default values. A signed-in user can explicitly save changes to that record or reset it to the current Default. Personal changes affect only the owning account and never modify Default or another user’s settings. Settings are not yet attached to imports or used to execute audit rules.

## Rules catalog

The read-only Rules page at `/rules` documents all 13 approved audit checks in permanent rule-ID order. The application registry in `app/services/rules.py` and [the detailed rules specification](docs/rules.md) must remain synchronized. The documented rules are not executed during CSV import.

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
- `production` disables debugging and enables secure cookie transport.

Select a profile with the `FLASK_CONFIG` environment variable.

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
