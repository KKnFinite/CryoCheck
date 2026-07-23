"""Environment-specific configuration for CryoCheck."""

from __future__ import annotations

import os
from datetime import timedelta

from dotenv import load_dotenv


load_dotenv()


def _positive_integer_setting(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError:
        raise ValueError(f"{name} must be a positive integer.") from None

    if value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value


def prepare_database_url(database_url: str | None) -> str | None:
    """Normalize PostgreSQL URLs and select the installed psycopg 3 driver."""
    if not database_url:
        return database_url

    if database_url.startswith("postgres://"):
        database_url = f"postgresql://{database_url.removeprefix('postgres://')}"

    if database_url.startswith("postgresql://"):
        database_url = (
            f"postgresql+psycopg://{database_url.removeprefix('postgresql://')}"
        )

    return database_url


class Config:
    """Settings shared by every environment."""

    APPLICATION_NAME = "CryoCheck"
    SECRET_KEY = os.getenv("SECRET_KEY")
    DEBUG = False
    TESTING = False
    MAX_UPLOAD_MB = _positive_integer_setting("MAX_UPLOAD_MB", 10)
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    SQLALCHEMY_DATABASE_URI = prepare_database_url(os.getenv("DATABASE_URL"))
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = False
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    WTF_CSRF_ENABLED = True
    RATELIMIT_ENABLED = True
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_STORAGE_URI = "memory://"
    LOGIN_RATE_LIMIT = "10 per 15 minutes"
    REGISTRATION_RATE_LIMIT = "5 per hour"


class DevelopmentConfig(Config):
    """Local development settings."""

    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-secret")


class TestingConfig(Config):
    """Automated test settings."""

    TESTING = True
    SECRET_KEY = "testing-only-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite+pysqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    """Production-safe defaults for Render."""

    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


CONFIGURATIONS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
