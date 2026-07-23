"""Public routes for the CryoCheck application shell."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template, request

from app.services.csv_import import (
    CSVImportError,
    PREVIEW_DISPLAY_COLUMNS,
    parse_csv_upload,
)


main = Blueprint("main", __name__)


@main.get("/")
def index() -> str:
    """Render the initial CryoCheck landing page."""
    return render_template(
        "index.html",
        max_upload_mb=current_app.config["MAX_UPLOAD_MB"],
    )


@main.post("/import")
def import_csv():
    """Parse one deicing CSV and render a non-persistent summary."""
    try:
        uploads = request.files.getlist("csv_file")
        if len(uploads) > 1:
            raise CSVImportError("Import one CSV file at a time.")
        result = parse_csv_upload(uploads[0] if uploads else None)
    except CSVImportError as error:
        return render_template("import_error.html", error=error), 400

    return render_template(
        "import_summary.html",
        result=result,
        preview_columns=PREVIEW_DISPLAY_COLUMNS,
    )


@main.get("/health")
def health():
    """Return a database-independent service health response."""
    return jsonify(
        status="healthy",
        application=current_app.config["APPLICATION_NAME"],
    )
