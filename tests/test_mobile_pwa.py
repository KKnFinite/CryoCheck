"""Mobile, installability, and Android share-target coverage."""

from __future__ import annotations

import csv
import io
import json
import re
import struct
from pathlib import Path

from sqlalchemy import event
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.services.csv_import import EXPECTED_COLUMNS


def _csv_payload(
    *,
    columns: tuple[str, ...] = EXPECTED_COLUMNS,
    overrides: dict[str, str] | None = None,
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    row = {column: "" for column in columns}
    row.update(
        {
            "RecordID": "mobile-record-001",
            "ApplicationNumber": "mobile-application-001",
            "GatewayCode": "MOBILE",
            "ApplicationDate": "2026-01-01",
            "StartTime": "08:00",
            "EndTime": "08:30",
            "DateCreated": "2026-01-01 08:00",
            "AircraftType": "2",
            "TailNumber": "N00001",
            "TruckNumber": "1",
            "Operator": "Mobile Operator",
            "Driver": "Mobile Driver",
            "AmbientTemp": "1",
            "Type1Used": "10",
            "Type1Concentration": "50",
            "FreezingPoint1": "-17.3",
            "EndTime1": "08:10",
            "ProcessTime1": "1",
            "Type4Used": "0",
            "Type4AConcentration": "100",
            "StartTime4": "08:15",
            "ProcessTime4": "1",
            "Notes": "Type I applied by truck 2",
        }
    )
    if overrides:
        row.update(overrides)
    writer.writerow({column: row.get(column, "") for column in columns})
    return output.getvalue().encode("utf-8")


def _shared_file(payload: bytes, filename: str = "shared-deice.csv"):
    return {"csv_file": (io.BytesIO(payload), filename)}


def _png_size(payload: bytes) -> tuple[int, int]:
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"
    assert payload[12:16] == b"IHDR"
    return struct.unpack(">II", payload[16:24])


def test_desktop_shell_remains_and_mobile_shell_is_separate(client):
    landing = client.get("/").get_data(as_text=True)

    assert 'class="site-header"' in landing
    assert 'class="header-actions"' in landing
    assert 'class="landing-brand"' in landing
    assert 'class="upload-dropzone"' in landing
    assert 'class="mobile-header"' in landing
    assert 'data-mobile-menu-toggle' in landing
    assert 'data-mobile-menu' in landing
    assert 'data-install-action' in landing
    assert 'class="site-footer"' not in landing


def test_mobile_header_navigation_branding_are_preserved_and_footer_is_removed(
    client,
):
    landing = client.get("/").get_data(as_text=True)
    mobile_menu_match = re.search(
        r'<nav\s+id="mobile-menu".*?</nav>',
        landing,
        flags=re.DOTALL,
    )

    assert mobile_menu_match is not None
    mobile_menu = mobile_menu_match.group(0)
    assert 'class="mobile-brand"' in landing
    assert 'src="/static/img/logo_silver.png"' in landing
    assert ">Import Deice Log</a>" in mobile_menu
    assert ">Rules</a>" in mobile_menu
    assert ">Settings</a>" in mobile_menu
    assert "Reports" not in mobile_menu
    assert 'class="mobile-menu__account"' in mobile_menu
    assert ">Sign In</a>" in mobile_menu
    assert ">Create Account</a>" in mobile_menu
    assert "<footer" not in landing
    assert "Standalone Deice Log Audit System" not in landing


def test_footer_is_absent_from_every_shared_desktop_and_mobile_shell(client):
    for path in (
        "/",
        "/rules",
        "/settings",
        "/login",
        "/register",
        "/not-a-real-page",
    ):
        page = client.get(path).get_data(as_text=True)
        assert "<footer" not in page
        assert "Standalone Deice Log Audit System" not in page


def test_mobile_import_auto_runs_once_and_retains_no_javascript_fallback():
    upload_script = Path("app/static/js/upload.js").read_text(encoding="utf-8")
    template = Path("app/templates/index.html").read_text(encoding="utf-8")

    assert 'window.matchMedia("(max-width: 47.99rem)")' in upload_script
    assert "form.requestSubmit(submitButton)" in upload_script
    assert "if (isSubmitting)" in upload_script
    assert "event.preventDefault()" in upload_script
    assert ".method =" not in upload_script
    assert "window.location" not in upload_script
    assert "location.href" not in upload_script
    assert 'action="{{ url_for(\'main.import_csv\') }}"' in template
    assert 'method="post"' in template
    assert 'enctype="multipart/form-data"' in template
    assert "CryoCheck Activated" in template
    assert (
        '<span class="desktop-validation-copy">'
        "Validating securely&hellip;</span>"
    ) in template
    assert (
        '<span class="mobile-validation-copy">'
        "CryoCheck Activated</span>"
    ) in template
    assert "data-replace-file" in template
    assert "data-submit-button" in template
    assert "Run Validation" in template
    assert (
        '<span class="upload-dropzone__title mobile-upload-copy">'
        "Upload Deice Log</span>"
    ) in template
    assert "Import deicing log" in template
    assert "Select from Files or Downloads" in template
    assert "Maximum allowed file size: {{ max_upload_mb }} MB" in template
    assert "Choose a CSV" not in template
    assert (
        '{% block body_attributes %} class="mobile-import-page"{% endblock %}'
        in template
    )


def test_get_share_target_uses_branded_405_without_running_validation(
    client,
    monkeypatch,
):
    def fail_if_audit_runs():
        raise AssertionError("GET /share/csv must not run validation")

    monkeypatch.setattr("app.routes._audit_uploaded_csv", fail_if_audit_runs)

    response = client.get("/share/csv")

    assert response.status_code == 405
    assert b"Action Not Available | CryoCheck" in response.data
    assert b'class="error-panel"' in response.data
    assert b"That action is not available" in response.data
    assert b"Return to Import" in response.data
    assert b"The method is not allowed for the requested URL." not in response.data
    assert "private" in response.headers["Cache-Control"]
    assert "no-store" in response.headers["Cache-Control"]


def test_results_have_mobile_cards_and_sticky_selection_controls(client):
    response = client.post(
        "/import",
        data=_shared_file(
            _csv_payload(overrides={"Type1Concentration": "65"})
        ),
        content_type="multipart/form-data",
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert page.count("data-exception-checkbox") == 1
    assert page.count('class="exception-card__top-row"') == 1
    assert "data-mobile-exception-content" not in page
    assert 'class="exception-export__toolbar"' in page
    assert 'class="mobile-export-bar mobile-results-only"' in page
    assert page.count("data-select-all") == 2
    assert page.count("data-clear-all") == 2
    assert page.count("data-export-selected") == 2
    assert page.count("data-export-feedback\n") == 2
    assert page.count('formtarget="_blank"') == 4
    assert "Export All" in page
    assert "Application Number" in page
    assert "Entry Date" in page
    assert "Record ID" not in page
    assert "Truck Number" not in page
    assert ">Rule ID<" not in page
    assert "CSV row <strong>" not in page
    assert 'data-rule-id="CC-RULE-003"' in page
    assert 'data-source-row-number="2"' in page


def test_mobile_exception_cards_reuse_the_server_rendered_top_row():
    script = Path("app/static/js/mobile-shell.js").read_text(encoding="utf-8")
    template = Path("app/templates/results.html").read_text(encoding="utf-8")

    assert "hydrateMobileExceptions" not in script
    assert "data-mobile-exception-content" not in template
    assert 'class="exception-card__top-row"' in template
    top_row = template.index('class="exception-card__top-row"')
    checkbox = template.index('class="exception-card__selection"', top_row)
    message = template.index('class="exception-card__message"', checkbox)
    identity = template.index('class="exception-card__identity"', message)
    details = template.index('class="exception-details"', identity)
    assert top_row < checkbox < message < identity < details


def test_mobile_warnings_preview_rules_settings_auth_and_errors_are_dedicated(
    client,
):
    warning_page = client.post(
        "/import",
        data=_shared_file(
            _csv_payload(overrides={"ProcessTime1": "not-a-time"})
        ),
        content_type="multipart/form-data",
    ).get_data(as_text=True)
    rules_page = client.get("/rules").get_data(as_text=True)
    settings_page = client.get("/settings").get_data(as_text=True)
    login_page = client.get("/login").get_data(as_text=True)
    error_page = client.get("/not-a-real-page").get_data(as_text=True)

    assert 'class="mobile-warning-summary mobile-results-only"' in warning_page
    assert 'class="mobile-preview mobile-results-only"' in warning_page
    assert warning_page.count("CC-RULE-008") == 1
    assert 'class="rules-list rules-list--desktop"' in rules_page
    assert 'data-mobile-rules-list' in rules_page
    assert rules_page.count(">CC-RULE-001<") == 1
    assert "rule-card__status" not in rules_page
    assert "mobile-rule__status" not in Path(
        "app/static/js/mobile-shell.js"
    ).read_text(encoding="utf-8")
    assert 'class="settings-page"' in settings_page
    assert 'class="auth-page"' in login_page
    assert 'class="error-panel"' in error_page


def test_signed_in_settings_include_mobile_sticky_save(app, client):
    from app.models import User
    from app.services.settings import create_default_user_settings

    with app.app_context():
        user = User(username="MobileUser", username_normalized="mobileuser")
        user.set_password("SyntheticPassphrase-42")
        create_default_user_settings(user)
        db.session.add(user)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": "MobileUser",
            "password": "SyntheticPassphrase-42",
        },
    )
    page = client.get("/settings").get_data(as_text=True)

    assert 'class="settings-save"' in page
    assert 'class="mobile-settings-save"' in page
    assert "Save Settings" in page


def test_phone_css_prevents_page_horizontal_overflow_and_preserves_breakpoint():
    stylesheet = Path("app/static/css/app.css").read_text(encoding="utf-8")

    assert "@media (max-width: 47.99rem)" in stylesheet
    assert re.search(
        r"html,\s*body\s*\{[^}]*max-width:\s*100%;",
        stylesheet,
        flags=re.DOTALL,
    )
    assert ".mobile-layout-ready .mobile-rules-list" in stylesheet
    assert ".mobile-layout-ready .mobile-export-bar.mobile-results-only" in (
        stylesheet
    )
    assert re.search(
        r"\.mobile-header\s*\{[^}]*position:\s*sticky;"
        r"[^}]*top:\s*0;[^}]*z-index:\s*65;",
        stylesheet,
        flags=re.DOTALL,
    )
    assert re.search(
        r"\.site-shell\s*\{[^}]*display:\s*flex;"
        r"[^}]*flex-direction:\s*column;",
        stylesheet,
        flags=re.DOTALL,
    )
    assert "scroll-padding-top: calc(3.75rem + env(safe-area-inset-top));" in (
        stylesheet
    )
    assert (
        "padding-bottom: calc(11.5rem + env(safe-area-inset-bottom));"
        in stylesheet
    )
    assert (
        "scroll-padding-bottom: "
        "calc(11.5rem + env(safe-area-inset-bottom));"
        in stylesheet
    )
    bottom_bar_rule = re.search(
        r"\.mobile-export-bar\s*\{[^}]*\}",
        stylesheet,
        flags=re.DOTALL,
    )
    assert bottom_bar_rule is not None
    for declaration in (
        "right: 0;",
        "bottom: 0;",
        "left: 0;",
        "width: 100%;",
        "max-width: none;",
        "padding: 0.55rem 0.65rem calc(0.55rem + env(safe-area-inset-bottom));",
        "border-radius: 0;",
    ):
        assert declaration in bottom_bar_rule.group()
    assert "minmax(5.7rem, 1.05fr)" in stylesheet
    assert "minmax(8rem, 1.35fr)" in stylesheet
    assert ".exception-card__top-row" in stylesheet
    assert ".mobile-exception-card__details" not in stylesheet
    assert ".mobile-exception-card__row" not in stylesheet
    assert re.search(
        r"\.site-main--import\s*\{[^}]*padding-top:\s*0;",
        stylesheet,
        flags=re.DOTALL,
    )
    import_body_rule = re.search(
        r"body\.mobile-import-page\s*\{[^}]*\}",
        stylesheet,
        flags=re.DOTALL,
    )
    assert import_body_rule is not None
    for declaration in (
        "height: 100dvh;",
        "min-height: 100svh;",
        "max-height: 100dvh;",
        "overflow: hidden;",
        "overscroll-behavior: none;",
    ):
        assert declaration in import_body_rule.group()
    import_main_rule = re.search(
        r"\.mobile-import-page \.site-main--import\s*\{[^}]*\}",
        stylesheet,
        flags=re.DOTALL,
    )
    assert import_main_rule is not None
    for declaration in (
        "min-height: 0;",
        "flex: 1 1 0;",
        "padding-bottom: max(0.75rem, env(safe-area-inset-bottom));",
        "overflow: hidden;",
    ):
        assert declaration in import_main_rule.group()
    assert ".mobile-rule__status" not in stylesheet
    assert re.search(
        r"\.launch-control__label\s*\{[^}]*display:\s*none;",
        stylesheet,
        flags=re.DOTALL,
    )


def test_export_script_preserves_results_and_manages_async_download_state():
    script = Path("app/static/js/exception-export.js").read_text(
        encoding="utf-8"
    )

    assert 'event.preventDefault();' in script
    assert 'method: "POST"' in script
    assert "new FormData(form)" in script
    assert script.index("new FormData(form)") < script.index(
        "exportInProgress = true"
    )
    assert 'credentials: "same-origin"' in script
    assert 'cache: "no-store"' in script
    assert 'showFeedback("loading", "Preparing Excel\\u2026");' in script
    assert "if (exportInProgress)" in script
    assert "checkbox.disabled = exportInProgress" in script
    assert "control.disabled = exportInProgress" in script
    assert "window.open(\"\", \"_blank\")" in script
    assert "downloadContext === false" in script
    assert 'requestData.set("delivery", "validate")' in script
    assert 'formData.set("delivery", "native")' in script
    assert 'nativeForm.method = "post"' in script
    assert "nativeForm.target = downloadContext.name" in script
    assert "nativeForm.submit()" in script
    assert "startNativeDownload(" in script
    assert "serverErrorMessage(response)" in script
    assert "response.status >= 500" in script
    assert "fallbackMessages[response.status]" in script
    assert "400:" in script
    assert "403:" in script
    assert script.index("if (iosDownload) {") < script.index(
        "workbook = await response.blob()"
    )
    assert "URL.createObjectURL(blob)" in script
    assert "downloadLink.download = filename" in script
    assert 'finishExport("success", "Excel export ready.");' in script
    assert "Excel could not be prepared." not in script
    assert "CryoCheck could not reach the export service." in script
    assert "Safari could not open the secure Excel download." in script
    assert "window.location" not in script
    assert "location.href" not in script


def test_manifest_has_standalone_icons_and_csv_share_target(client):
    response = client.get("/static/manifest.webmanifest")
    manifest = json.loads(response.get_data(as_text=True))

    assert response.status_code == 200
    assert manifest["name"] == "CryoCheck"
    assert manifest["display"] == "standalone"
    assert manifest["scope"] == "/"
    assert manifest["start_url"] == "/"
    assert manifest["theme_color"] == "#071b33"
    assert manifest["share_target"] == {
        "action": "/share/csv",
        "method": "POST",
        "enctype": "multipart/form-data",
        "params": {
            "files": [
                {
                    "name": "csv_file",
                    "accept": [
                        ".csv",
                        "text/csv",
                        "text/comma-separated-values",
                    ],
                }
            ]
        },
    }
    icon_sizes = {icon["sizes"] for icon in manifest["icons"]}
    assert {"192x192", "512x512", "1024x1024"} <= icon_sizes
    assert any(
        icon.get("purpose") == "maskable"
        and icon["sizes"] == "512x512"
        for icon in manifest["icons"]
    )


def test_pwa_icons_are_served_at_declared_dimensions(client):
    expected = {
        "/static/img/icon-180.png": (180, 180),
        "/static/img/icon-192.png": (192, 192),
        "/static/img/icon-512.png": (512, 512),
        "/static/img/icon-maskable-512.png": (512, 512),
        "/static/img/logo_blue.png": (1024, 1024),
    }

    for path, dimensions in expected.items():
        response = client.get(path)
        assert response.status_code == 200
        assert response.mimetype == "image/png"
        assert _png_size(response.data) == dimensions


def test_install_ui_covers_native_ios_and_standalone_states(client):
    page = client.get("/").get_data(as_text=True)
    install_script = Path("app/static/js/pwa-install.js").read_text(
        encoding="utf-8"
    )

    assert "Install CryoCheck" in page
    assert "Add CryoCheck to your Home Screen" in page
    assert "<strong>Share</strong>" in page
    assert "<strong>Add to Home Screen</strong>" in page
    assert "beforeinstallprompt" in install_script
    assert 'window.matchMedia("(display-mode: standalone)")' in install_script
    assert "window.navigator.standalone === true" in install_script
    assert "appinstalled" in install_script


def test_service_worker_only_caches_explicit_static_shell_assets(client):
    response = client.get("/service-worker.js")
    script = response.get_data(as_text=True)
    asset_block = re.search(
        r"const APP_SHELL_ASSETS = \[(.*?)\];",
        script,
        flags=re.DOTALL,
    )

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert response.headers["Service-Worker-Allowed"] == "/"
    assert response.headers["Cache-Control"] == "no-store"
    assert asset_block is not None
    assets = re.findall(r'"([^"]+)"', asset_block.group(1))
    assert assets
    assert all(asset.startswith("/static/") for asset in assets)
    for sensitive_path in (
        "/",
        "/import",
        "/share/csv",
        "/export",
        "/login",
        "/register",
        "/settings",
        "/health",
    ):
        assert sensitive_path not in assets
    assert 'event.request.method === "GET"' in script
    assert "APP_SHELL_PATHS.has(requestUrl.pathname)" in script
    assert '"/import"' not in script
    assert '"/share/csv"' not in script


def test_android_share_target_runs_existing_validation_without_csrf(app, client):
    app.config["WTF_CSRF_ENABLED"] = True

    shared = client.post(
        "/share/csv",
        data=_shared_file(
            _csv_payload(overrides={"Type1Concentration": "65"})
        ),
        content_type="multipart/form-data",
    )
    regular_import = client.post(
        "/import",
        data=_shared_file(_csv_payload()),
        content_type="multipart/form-data",
    )

    assert shared.status_code == 200
    assert b"Audit Results" in shared.data
    assert b"CC-RULE-003" in shared.data
    assert "no-store" in shared.headers["Cache-Control"]
    assert regular_import.status_code == 400
    assert b"Security check failed" in regular_import.data


def test_android_share_target_reuses_extension_schema_and_single_file_checks(
    client,
):
    wrong_extension = client.post(
        "/share/csv",
        data=_shared_file(_csv_payload(), "shared-deice.txt"),
        content_type="multipart/form-data",
    )
    missing_schema = client.post(
        "/share/csv",
        data=_shared_file(
            _csv_payload(
                columns=tuple(
                    column for column in EXPECTED_COLUMNS if column != "Notes"
                )
            )
        ),
        content_type="multipart/form-data",
    )
    multiple_files = client.post(
        "/share/csv",
        data=MultiDict(
            [
                (
                    "csv_file",
                    (io.BytesIO(_csv_payload()), "one.csv"),
                ),
                (
                    "csv_file",
                    (io.BytesIO(_csv_payload()), "two.csv"),
                ),
            ]
        ),
        content_type="multipart/form-data",
    )

    assert wrong_extension.status_code == 400
    assert b".csv extension" in wrong_extension.data
    assert missing_schema.status_code == 400
    assert b"Missing required columns" in missing_schema.data
    assert multiple_files.status_code == 400
    assert b"Import one CSV file at a time" in multiple_files.data


def test_android_share_target_reuses_upload_size_limit(app, client):
    app.config["MAX_CONTENT_LENGTH"] = 256
    marker = b"private-shared-csv-marker"

    response = client.post(
        "/share/csv",
        data=_shared_file(marker * 100, "oversize.csv"),
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert b"CSV file is too large" in response.data
    assert marker not in response.data
    assert "no-store" in response.headers["Cache-Control"]


def test_android_share_target_performs_no_database_mutation(app, client):
    statements: list[str] = []

    def record_statement(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        del connection, cursor, parameters, context, executemany
        statements.append(statement)

    with app.app_context():
        engine = db.engine
        event.listen(engine, "before_cursor_execute", record_statement)
        try:
            response = client.post(
                "/share/csv",
                data=_shared_file(_csv_payload()),
                content_type="multipart/form-data",
            )
        finally:
            event.remove(engine, "before_cursor_execute", record_statement)

    mutating = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith(
            ("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")
        )
    ]
    assert response.status_code == 200
    assert mutating == []


def test_dynamic_posts_and_account_pages_are_not_cacheable(client):
    shared = client.post(
        "/share/csv",
        data=_shared_file(_csv_payload()),
        content_type="multipart/form-data",
    )
    login = client.get("/login")
    settings = client.get("/settings")

    for response in (shared, login, settings):
        assert "no-store" in response.headers["Cache-Control"]
        assert response.headers["Pragma"] == "no-cache"


def test_health_exposes_render_revision_without_changing_payload(
    client,
    monkeypatch,
):
    revision = "0123456789abcdef0123456789abcdef01234567"
    monkeypatch.setenv("RENDER_GIT_COMMIT", revision)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "healthy",
        "application": "CryoCheck",
    }
    assert response.headers["X-CryoCheck-Revision"] == revision
