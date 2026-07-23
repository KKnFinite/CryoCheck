"""Application extension registration."""

from __future__ import annotations

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[])


@login_manager.user_loader
def load_user(user_id: str):
    """Load one signed-in user without accepting malformed session IDs."""
    try:
        numeric_user_id = int(user_id)
    except (TypeError, ValueError):
        return None

    from app.models import User

    return db.session.get(User, numeric_user_id)


def init_extensions(app: Flask) -> None:
    """Initialize Flask extensions for an application instance."""
    db.init_app(app)
    migrate.init_app(app, db, compare_type=True)
    login_manager.login_view = "main.login"
    login_manager.login_message = "Sign in to continue."
    login_manager.login_message_category = "info"
    login_manager.session_protection = "strong"
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)


__all__ = [
    "csrf",
    "db",
    "init_extensions",
    "limiter",
    "login_manager",
    "migrate",
]
