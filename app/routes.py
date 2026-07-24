"""Public routes for the CryoCheck application shell."""

from __future__ import annotations

import secrets
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)
from sqlalchemy.exc import IntegrityError

from app.extensions import db, limiter
from app.forms import LoginForm, RegisterForm, ResetSettingsForm, SettingsForm
from app.models import User, normalize_username, utc_now

from app.services.csv_import import (
    CSVImportError,
    PREVIEW_DISPLAY_COLUMNS,
    parse_csv_upload,
)
from app.services.excel_export import (
    ExportRequestError,
    build_exception_workbook,
    load_export_snapshot,
    prepare_export,
    select_export_rows,
)
from app.services.rules import RULES
from app.services.settings import (
    DEFAULT_SETTINGS,
    create_default_user_settings,
    get_active_settings,
    reset_user_settings,
)
from app.services.validation_engine import run_audit


main = Blueprint("main", __name__)


@main.get("/")
def index() -> str:
    """Render the initial CryoCheck landing page."""
    active_settings = get_active_settings()
    return render_template(
        "index.html",
        active_page="import",
        active_settings=active_settings,
        max_upload_mb=current_app.config["MAX_UPLOAD_MB"],
    )


@main.post("/import")
def import_csv():
    """Parse and audit one deicing CSV entirely in memory."""
    try:
        uploads = request.files.getlist("csv_file")
        if len(uploads) > 1:
            raise CSVImportError("Import one CSV file at a time.")
        result = parse_csv_upload(uploads[0] if uploads else None)
    except CSVImportError as error:
        return (
            render_template(
                "import_error.html",
                active_page="import",
                error=error,
            ),
            400,
        )

    active_settings = get_active_settings()
    audit_result = run_audit(result, active_settings)
    if audit_result.exceptions:
        export_context_id = secrets.token_urlsafe(32)
        session["export_context_id"] = export_context_id
        prepared_export = prepare_export(
            audit_result,
            secret_key=current_app.config["SECRET_KEY"],
            context_id=export_context_id,
        )
    else:
        session.pop("export_context_id", None)
        prepared_export = None
    return render_template(
        "results.html",
        active_page="import",
        audit=audit_result,
        import_result=result,
        preview_columns=PREVIEW_DISPLAY_COLUMNS,
        export_token=(
            prepared_export.token if prepared_export is not None else None
        ),
        export_entries=(
            tuple(
                zip(
                    prepared_export.identifiers,
                    audit_result.exceptions,
                )
            )
            if prepared_export is not None
            else ()
        ),
    )


@main.post("/export")
def export_exceptions():
    """Validate one Results snapshot and stream an in-memory XLSX file."""
    try:
        snapshot = load_export_snapshot(
            request.form.get("export_token", ""),
            secret_key=current_app.config["SECRET_KEY"],
            max_age_seconds=current_app.config[
                "EXPORT_TOKEN_MAX_AGE_SECONDS"
            ],
            expected_context_id=session.get("export_context_id", ""),
        )
        selected_rows = select_export_rows(
            snapshot,
            scope=request.form.get("scope", ""),
            selected_identifiers=request.form.getlist("exception_id"),
        )
    except ExportRequestError as error:
        return (
            render_template(
                "export_error.html",
                active_page="import",
                error=error,
            ),
            400,
        )

    workbook, filename = build_exception_workbook(selected_rows)
    response = send_file(
        workbook,
        as_attachment=True,
        download_name=filename,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@main.get("/rules")
def rules() -> str:
    """Render the approved audit rule catalog and implementation status."""
    return render_template(
        "rules.html",
        active_page="rules",
        rules=RULES,
    )


def _is_safe_next_url(target: str | None) -> bool:
    """Allow only local absolute-path redirects."""
    if (
        not target
        or "\\" in target
        or not target.startswith("/")
        or any(ord(character) < 32 for character in target)
    ):
        return False

    parsed = urlsplit(target)
    return not parsed.scheme and not parsed.netloc and not target.startswith("//")


@main.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour", exempt_when=lambda: request.method != "POST")
def register():
    """Create an optional account and its private Default settings copy."""
    if current_user.is_authenticated:
        return redirect(url_for("main.settings"))

    form = RegisterForm()
    status_code = 200
    if form.validate_on_submit():
        username = form.username.data
        username_normalized = normalize_username(username)

        if User.query.filter_by(
            username_normalized=username_normalized
        ).first() is not None:
            form.username.errors.append("That account name is unavailable.")
            status_code = 400
        else:
            user = User(
                username=username,
                username_normalized=username_normalized,
            )
            user.set_password(form.password.data)
            create_default_user_settings(user)
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                form.username.errors.append("That account name is unavailable.")
                status_code = 400
            else:
                login_user(user)
                flash(
                    "Account created. Your Personal Settings start with Default values.",
                    "success",
                )
                return redirect(url_for("main.settings"))
    elif request.method == "POST":
        status_code = 400

    return (
        render_template(
            "auth/register.html",
            active_page="register",
            form=form,
        ),
        status_code,
    )


@main.route("/login", methods=["GET", "POST"])
@limiter.limit(
    "10 per 15 minutes",
    exempt_when=lambda: request.method != "POST",
)
def login():
    """Authenticate an optional account without revealing account existence."""
    if current_user.is_authenticated:
        return redirect(url_for("main.settings"))

    form = LoginForm()
    if request.method == "GET":
        form.next_url.data = request.args.get("next", "")

    status_code = 200
    if form.validate_on_submit():
        user = User.query.filter_by(
            username_normalized=normalize_username(form.username.data)
        ).first()
        if user is None or not user.check_password(form.password.data):
            form.password.errors.append("Invalid account name or password.")
            status_code = 400
        else:
            user.last_login_at = utc_now()
            db.session.commit()
            login_user(
                user,
                remember=form.remember.data,
                duration=current_app.config["REMEMBER_COOKIE_DURATION"],
            )
            session.permanent = form.remember.data
            flash(f"Welcome back, {user.username}.", "success")

            if _is_safe_next_url(form.next_url.data):
                return redirect(form.next_url.data)
            return redirect(url_for("main.settings"))
    elif request.method == "POST":
        status_code = 400

    return (
        render_template(
            "auth/login.html",
            active_page="login",
            form=form,
        ),
        status_code,
    )


@main.post("/logout")
@login_required
def logout():
    """End the current account session and restore anonymous Default use."""
    logout_user()
    flash("You have signed out. Default settings are now active.", "success")
    return redirect(url_for("main.index"))


def _format_updated_at(settings) -> str:
    timestamp = settings.updated_at
    return timestamp.strftime("%B %d, %Y at %I:%M %p UTC")


@main.route("/settings", methods=["GET", "POST"])
def settings():
    """Show immutable Default settings or edit the signed-in user's copy."""
    if not current_user.is_authenticated:
        if request.method == "POST":
            return redirect(url_for("main.login", next=url_for("main.settings")))
        return render_template(
            "settings.html",
            active_page="settings",
            default_settings=DEFAULT_SETTINGS,
            personal_settings=None,
            reset_form=None,
            settings_form=None,
        )

    personal_settings = current_user.settings
    if personal_settings is None:
        raise RuntimeError("Signed-in account does not have Personal Settings.")

    form = SettingsForm(obj=personal_settings)
    reset_form = ResetSettingsForm()
    status_code = 200
    if form.validate_on_submit():
        personal_settings.late_entry_threshold_hours = (
            form.late_entry_threshold_hours.data
        )
        personal_settings.type1_fluid = form.type1_fluid.data
        personal_settings.type4_fluid = form.type4_fluid.data
        personal_settings.allowed_gap_minutes = form.allowed_gap_minutes.data
        personal_settings.max_type1_rate_gpm = form.max_type1_rate_gpm.data
        personal_settings.max_type4_rate_gpm = form.max_type4_rate_gpm.data
        personal_settings.max_event_time_minutes = (
            form.max_event_time_minutes.data
        )
        personal_settings.include_gap_in_event_time = (
            form.include_gap_in_event_time.data
        )
        db.session.commit()
        flash("Personal Settings saved.", "success")
        return redirect(url_for("main.settings"))
    if request.method == "POST":
        status_code = 400

    return (
        render_template(
            "settings.html",
            active_page="settings",
            default_settings=DEFAULT_SETTINGS,
            personal_settings=personal_settings,
            reset_form=reset_form,
            settings_form=form,
            updated_at_display=_format_updated_at(personal_settings),
        ),
        status_code,
    )


@main.post("/settings/reset")
@login_required
def reset_settings():
    """Restore current built-in defaults after explicit confirmation."""
    form = ResetSettingsForm()
    if not form.validate_on_submit():
        personal_settings = current_user.settings
        return (
            render_template(
                "settings.html",
                active_page="settings",
                default_settings=DEFAULT_SETTINGS,
                personal_settings=personal_settings,
                reset_form=form,
                settings_form=SettingsForm(obj=personal_settings),
                updated_at_display=_format_updated_at(personal_settings),
            ),
            400,
        )

    reset_user_settings(current_user.settings)
    db.session.commit()
    flash("Personal Settings reset to Default values.", "success")
    return redirect(url_for("main.settings"))


@main.get("/health")
def health():
    """Return a database-independent service health response."""
    return jsonify(
        status="healthy",
        application=current_app.config["APPLICATION_NAME"],
    )
