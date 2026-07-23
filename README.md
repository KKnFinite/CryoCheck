# CryoCheck

CryoCheck is a standalone deice log audit application. This repository currently contains the production-ready Flask application shell and landing experience; CSV importing, validation rules, settings, Excel export, and database integration will be added in later development phases.

## Purpose

The application will provide a focused workflow for importing deice log data, validating it, and reviewing or exporting exceptions. The initial foundation includes an application factory, environment-specific configuration, health monitoring, custom error pages, and a tested landing page.

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

Update `SECRET_KEY` in `.env` with a long, random value. The default `APP_CONFIG=development` profile is appropriate for local work.

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

Select a profile with the `APP_CONFIG` environment variable.

## Future Render deployment

Create a Render Web Service connected to this repository and use:

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn run:app`
- Health check path: `/health`

Set `APP_CONFIG=production` and a secure `SECRET_KEY` in the Render environment. Neon PostgreSQL configuration will be added in a later phase; the current health endpoint intentionally does not require a database connection.
