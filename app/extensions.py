"""Application extension registration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Flask, current_app, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_login.config import (
    COOKIE_DURATION,
    COOKIE_HTTPONLY,
    COOKIE_NAME,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
)
from flask_login.utils import encode_cookie
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect


class TimezoneAwareLoginManager(LoginManager):
    """Set persistent-login cookie expiry with an aware UTC timestamp.

    Flask-Login 0.6.3 still uses ``datetime.utcnow()`` internally. Python
    3.14 deprecates that naive-UTC API, so CryoCheck keeps the extension's
    cookie behavior while using the supported timezone-aware equivalent.
    """

    def _set_cookie(self, response) -> None:
        config = current_app.config
        cookie_name = config.get("REMEMBER_COOKIE_NAME", COOKIE_NAME)
        domain = config.get("REMEMBER_COOKIE_DOMAIN")
        path = config.get("REMEMBER_COOKIE_PATH", "/")
        secure = config.get("REMEMBER_COOKIE_SECURE", COOKIE_SECURE)
        httponly = config.get("REMEMBER_COOKIE_HTTPONLY", COOKIE_HTTPONLY)
        samesite = config.get("REMEMBER_COOKIE_SAMESITE", COOKIE_SAMESITE)

        if "_remember_seconds" in session:
            duration = timedelta(seconds=session["_remember_seconds"])
        else:
            duration = config.get("REMEMBER_COOKIE_DURATION", COOKIE_DURATION)

        data = encode_cookie(str(session["_user_id"]))
        if isinstance(duration, int):
            duration = timedelta(seconds=duration)

        try:
            expires = datetime.now(timezone.utc) + duration
        except TypeError as error:
            raise Exception(
                "REMEMBER_COOKIE_DURATION must be a datetime.timedelta, "
                f"instead got: {duration}"
            ) from error

        response.set_cookie(
            cookie_name,
            value=data,
            expires=expires,
            domain=domain,
            path=path,
            secure=secure,
            httponly=httponly,
            samesite=samesite,
        )


db = SQLAlchemy()
migrate = Migrate()
login_manager = TimezoneAwareLoginManager()
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
