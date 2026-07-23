"""Public routes for the CryoCheck application shell."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template


main = Blueprint("main", __name__)


@main.get("/")
def index() -> str:
    """Render the initial CryoCheck landing page."""
    return render_template("index.html")


@main.get("/health")
def health():
    """Return a database-independent service health response."""
    return jsonify(
        status="healthy",
        application=current_app.config["APPLICATION_NAME"],
    )
