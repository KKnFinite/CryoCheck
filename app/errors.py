"""Custom HTTP error handlers for CryoCheck."""

from __future__ import annotations

from flask import Flask, current_app, render_template, request
from flask_limiter.errors import RateLimitExceeded
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import BadRequest, Forbidden, RequestEntityTooLarge


def register_error_handlers(app: Flask) -> None:
    """Register application-wide error pages."""

    @app.errorhandler(BadRequest)
    def bad_request(error):
        del error
        return render_template("errors/400.html"), 400

    @app.errorhandler(Forbidden)
    def forbidden(error):
        del error
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        del error
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        del error
        return render_template("errors/500.html"), 500

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(error):
        del error
        is_export_request = (
            request.endpoint == "main.export_exceptions"
            or request.path.rstrip("/") == "/export"
        )
        return (
            render_template(
                "errors/413.html",
                is_export_request=is_export_request,
                max_upload_mb=current_app.config["MAX_UPLOAD_MB"],
            ),
            413,
        )

    @app.errorhandler(CSRFError)
    def csrf_failed(error):
        del error
        return render_template("errors/csrf.html"), 400

    @app.errorhandler(RateLimitExceeded)
    def rate_limit_exceeded(error):
        del error
        return render_template("errors/429.html"), 429
