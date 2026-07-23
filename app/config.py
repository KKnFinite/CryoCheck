"""Environment-specific configuration for CryoCheck."""

from __future__ import annotations

import os


class Config:
    """Settings shared by every environment."""

    APPLICATION_NAME = "CryoCheck"
    SECRET_KEY = os.getenv("SECRET_KEY")
    DEBUG = False
    TESTING = False


class DevelopmentConfig(Config):
    """Local development settings."""

    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-secret")


class TestingConfig(Config):
    """Automated test settings."""

    TESTING = True
    SECRET_KEY = "testing-only-secret"


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
