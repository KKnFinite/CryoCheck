"""Application extension registration."""

from __future__ import annotations

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
migrate = Migrate()


def init_extensions(app: Flask) -> None:
    """Initialize Flask extensions for an application instance."""
    db.init_app(app)
    migrate.init_app(app, db, compare_type=True)


__all__ = ["db", "init_extensions", "migrate"]
