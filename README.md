# CryoCheck

CryoCheck is a standalone deice log audit application. This repository currently contains the production-ready Flask application shell, Neon PostgreSQL integration foundation, and in-memory CSV inspection workflow; validation rules, settings, results, and Excel export will be added in later development phases.

## Purpose

The application provides a focused starting workflow for importing and safely inspecting deice log data. Future phases will validate that data and support reviewing or exporting exceptions.

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

Flask-Migrate infrastructure is initialized in `migrations/`, but there are no migration revisions because CryoCheck has no domain models yet. Do not run `flask db migrate` until a meaningful model change is ready.

The migration repository was initialized once with `flask db init`; do not run that initialization command again.

Future migration workflow:

```powershell
flask db migrate -m "Describe the model change"
flask db upgrade
```

Review every generated revision before applying it. Production migrations must be committed with the related model change and applied as a controlled Render operation using `flask db upgrade`. They are not currently part of the Render build command.

## Render deployment

Create a Render Web Service connected to this repository and use:

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn run:app`
- Health check path: `/health`

Configure these Render environment variables:

- `DATABASE_URL`: the Neon production connection string, including its SSL parameters
- `SECRET_KEY`: a secure production secret
- `FLASK_CONFIG=production`
- `MAX_UPLOAD_MB`: optional CSV upload limit in megabytes; defaults to `10`

Do not add `flask db upgrade` to the build command yet because there are no migrations or domain models. The `/health` endpoint intentionally remains database-independent so Render can verify the web process during a temporary database outage. Use `flask db-check` separately when database connectivity must be confirmed.
