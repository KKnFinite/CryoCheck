"""CryoCheck Flask application factory."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from app.errors import register_error_handlers
from app.extensions import init_extensions
from app.routes import main


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure a CryoCheck application instance."""
    load_dotenv()

    # Import after loading .env so class-based settings read local values.
    from app.config import CONFIGURATIONS

    selected_config = config_name or os.getenv("APP_CONFIG", "development")
    try:
        config_class = CONFIGURATIONS[selected_config.lower()]
    except KeyError as exc:
        available = ", ".join(sorted(CONFIGURATIONS))
        raise ValueError(
            f"Unknown APP_CONFIG '{selected_config}'. Choose from: {available}."
        ) from exc

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    app.json.sort_keys = False

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    init_extensions(app)
    app.register_blueprint(main)
    register_error_handlers(app)

    return app


__all__ = ["create_app"]
