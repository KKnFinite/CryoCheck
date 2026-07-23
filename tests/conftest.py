"""Shared pytest fixtures for CryoCheck."""

import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app():
    """Create an isolated application configured for testing."""
    application = create_app("testing")
    with application.app_context():
        db.create_all()

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """Create a Flask test client."""
    return app.test_client()
