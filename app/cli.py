"""Flask CLI commands for operational checks."""

from __future__ import annotations

import click
from flask import Flask
from sqlalchemy import text

from app.extensions import db


def _execute_database_check() -> None:
    """Execute the minimal query used to verify database connectivity."""
    result = db.session.execute(text("SELECT 1")).scalar_one()
    if result != 1:
        raise RuntimeError("Database returned an unexpected health-check result.")


def register_cli_commands(app: Flask) -> None:
    """Register application-specific Flask CLI commands."""

    @app.cli.command("db-check")
    def db_check() -> None:
        """Verify database connectivity without exposing connection details."""
        try:
            _execute_database_check()
            db.session.remove()
        except Exception as exc:
            try:
                db.session.remove()
            except Exception:
                pass

            error_type = type(exc).__name__
            raise click.ClickException(
                "Database connection failed "
                f"({error_type}). Verify DATABASE_URL, SSL settings, and network access."
            ) from None

        click.echo("Database connection successful.")
