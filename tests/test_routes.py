"""Route-level tests for the CryoCheck application shell."""

import re
from pathlib import Path

from sqlalchemy import event

from app.extensions import db
from app.models import User
from app.services.settings import create_default_user_settings


_VALID_PASSWORD = "SyntheticPassphrase-42"


def _desktop_navigation(html: str) -> str:
    match = re.search(
        r'<nav class="site-nav".*?</nav>',
        html,
        flags=re.DOTALL,
    )
    assert match is not None
    return match.group(0)


def test_landing_page_returns_200(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b'class="landing-brand__lockup"' in response.data
    assert b'class="landing-brand__mark"' in response.data
    assert b'src="/static/img/logo_blue.png"' in response.data
    assert b'class="landing-brand__name">CryoCheck</h1>' in response.data
    assert b"Run Validation" in response.data
    assert b"Settings:" in response.data
    assert b'name="csv_file"' in response.data
    assert b"Deice operations assurance" not in response.data
    assert b"Deice Data Validation" not in response.data
    assert b"A clear, dependable workflow" not in response.data
    assert b"Import and Inspect" not in response.data
    assert b'class="workflow"' not in response.data
    assert b"Review &amp; Export Exceptions" not in response.data
    assert b"Export Exceptions" not in response.data


def test_landing_navigation_has_primary_destinations(client):
    response = client.get("/")
    html = response.get_data(as_text=True)
    desktop_nav = _desktop_navigation(html)

    assert response.status_code == 200
    assert re.search(rb'href="/"[^>]*>\s*Import\s*</a>', response.data)
    assert re.search(rb'href="/rules"[^>]*>\s*Rules\s*</a>', response.data)
    assert re.search(
        rb'href="/settings"[^>]*>\s*Settings\s*</a>',
        response.data,
    )
    assert response.data.count(b'aria-label="Primary navigation"') == 1
    assert "Reports" not in html
    assert 'class="brand"' not in html
    assert re.findall(
        r">\s*(Import|Rules|Reports|Settings|Sign In|Create Account)\s*<",
        desktop_nav,
    ) == ["Import", "Rules", "Settings", "Sign In", "Create Account"]
    assert 'class="account-nav"' not in html


def test_signed_in_controls_share_the_centered_desktop_navigation(app, client):
    with app.app_context():
        user = User(
            username="UnifiedNavUser",
            username_normalized="unifiednavuser",
        )
        user.set_password(_VALID_PASSWORD)
        create_default_user_settings(user)
        db.session.add(user)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": "UnifiedNavUser",
            "password": _VALID_PASSWORD,
        },
    )
    html = client.get("/").get_data(as_text=True)
    desktop_nav = _desktop_navigation(html)

    assert re.findall(
        r">\s*(Import|Rules|Reports|Settings|UnifiedNavUser|Logout)\s*<",
        desktop_nav,
    ) == ["Import", "Rules", "Settings", "UnifiedNavUser", "Logout"]
    assert 'action="/logout"' in desktop_nav
    assert 'name="csrf_token"' in desktop_nav
    assert "Sign In" not in desktop_nav
    assert "Create Account" not in desktop_nav
    assert 'class="account-nav"' not in html


def test_desktop_header_and_hero_css_use_desktop_only_polish():
    stylesheet = Path("app/static/css/app.css").read_text(encoding="utf-8")

    header_actions = re.search(
        r"\.header-actions\s*\{(?P<rules>[^}]+)\}",
        stylesheet,
    )
    site_nav = re.search(
        r"\.site-nav\s*\{(?P<rules>[^}]+)\}",
        stylesheet,
    )
    assert header_actions is not None
    assert "display: flex" in header_actions.group("rules")
    assert "justify-content: center" in header_actions.group("rules")
    assert site_nav is not None
    assert "grid-column" not in site_nav.group("rules")
    assert ".account-nav" not in stylesheet
    assert ".site-footer" not in stylesheet

    hero_logo = re.search(
        r"\.landing-brand__mark\s*\{(?P<rules>[^}]+)\}",
        stylesheet,
    )
    hero_title = re.search(
        r"\.landing-brand__name\s*\{(?P<rules>[^}]+)\}",
        stylesheet,
    )
    assert hero_logo is not None
    assert "width: clamp(5.75rem, 10vw, 7.75rem)" in (
        hero_logo.group("rules")
    )
    assert hero_title is not None
    assert "color: var(--color-brand-navy)" in hero_title.group("rules")
    assert "font-size: clamp(2.6rem, 6.5vw, 4.75rem)" in (
        hero_title.group("rules")
    )


def test_import_drop_area_uses_configured_limit_and_updated_copy(app, client):
    response = client.get("/")

    assert app.config["MAX_UPLOAD_MB"] == 15
    assert app.config["MAX_CONTENT_LENGTH"] == 15 * 1024 * 1024
    assert b"Drop your deice log here" in response.data
    assert b"or click to browse" in response.data
    assert b"Upload Deice Log" in response.data
    assert b"Import deicing log" in response.data
    assert b"Select from Files or Downloads" in response.data
    assert b"Maximum allowed file size: 15 MB" in response.data
    assert b"Drop your CSV here" not in response.data
    assert b"One .csv file" not in response.data


def test_neofont_is_loaded_from_local_cryocheck_assets(client):
    stylesheet = client.get("/static/css/app.css")
    woff2 = client.get("/static/fonts/neofont/NeoFont.woff2")
    truetype = client.get("/static/fonts/neofont/NeoFont.ttf")

    assert stylesheet.status_code == 200
    assert b'font-family: "NeoFont"' in stylesheet.data
    assert b'url("../fonts/neofont/NeoFont.woff2")' in stylesheet.data
    assert b'url("../fonts/neofont/NeoFont.ttf")' in stylesheet.data
    assert b"NeoApps" not in stylesheet.data
    assert woff2.status_code == 200
    assert len(woff2.data) == 2944
    assert truetype.status_code == 200
    assert len(truetype.data) == 4872


def test_health_returns_healthy_status_without_database_query(app, client):
    executed_statements = []

    def record_statement(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        del connection, cursor, parameters, context, executemany
        executed_statements.append(statement)

    with app.app_context():
        engine = db.engine
        event.listen(engine, "before_cursor_execute", record_statement)
        try:
            response = client.get("/health")
        finally:
            event.remove(engine, "before_cursor_execute", record_statement)

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "healthy",
        "application": "CryoCheck",
    }
    assert executed_statements == []


def test_not_found_page_uses_custom_template(client):
    response = client.get("/this-page-does-not-exist")

    assert response.status_code == 404
    assert b'class="error-panel"' in response.data
    assert b"CryoCheck" in response.data
    assert b"Page not found" in response.data


def test_internal_server_error_uses_custom_template(app, client):
    @app.get("/test-only-server-error")
    def trigger_server_error():
        raise RuntimeError("synthetic test error")

    app.config["PROPAGATE_EXCEPTIONS"] = False
    response = client.get("/test-only-server-error")

    assert response.status_code == 500
    assert b"Something went wrong" in response.data
    assert b"synthetic test error" not in response.data
