"""Environment-specific configuration for CryoCheck."""

from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()


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
    SQLALCHEMY_DATABASE_URI = prepare_database_url(os.getenv("DATABASE_URL"))
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False


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


class ProductionConfig(Config):
    """Production-safe defaults for Render."""

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


CONFIGURATIONS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
