"""Database foundation tests that remain isolated from Neon."""

from app import cli as cli_module
from app.config import prepare_database_url
from app.extensions import db


def test_sqlalchemy_and_migrate_extensions_are_initialized(app):
    assert app.extensions["sqlalchemy"] is db
    assert "migrate" in app.extensions


def test_testing_database_is_isolated_from_production(app):
    database_uri = app.config["SQLALCHEMY_DATABASE_URI"]

    assert database_uri == "sqlite+pysqlite:///:memory:"
    assert "postgres" not in database_uri
    assert "neon" not in database_uri


def test_legacy_postgres_url_uses_psycopg_driver():
    database_url = "postgres://user:password@database.invalid/cryocheck"

    assert prepare_database_url(database_url) == (
        "postgresql+psycopg://user:password@database.invalid/cryocheck"
    )


def test_db_check_succeeds_against_isolated_database(app):
    result = app.test_cli_runner().invoke(args=["db-check"])

    assert result.exit_code == 0, result.output
    assert result.output == "Database connection successful.\n"


def test_db_check_failure_does_not_expose_connection_details(app, monkeypatch):
    sensitive_error = RuntimeError(
        "postgresql://database_user:database_password@private-host.invalid/cryocheck"
    )

    def fail_database_check():
        raise sensitive_error

    monkeypatch.setattr(cli_module, "_execute_database_check", fail_database_check)
    result = app.test_cli_runner().invoke(args=["db-check"])

    assert result.exit_code != 0
    assert "Database connection failed (RuntimeError)." in result.output
    assert "database_user" not in result.output
    assert "database_password" not in result.output
    assert "private-host" not in result.output
