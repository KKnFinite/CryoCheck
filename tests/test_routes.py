"""Route-level tests for the CryoCheck application shell."""

import re

from sqlalchemy import event

from app.extensions import db


def test_landing_page_returns_200(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b'class="landing-brand__lockup"' in response.data
    assert b'class="landing-brand__mark"' in response.data
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

    assert response.status_code == 200
    assert re.search(rb'href="/"[^>]*>\s*Import\s*</a>', response.data)
    assert re.search(rb'href="/rules"[^>]*>\s*Rules\s*</a>', response.data)
    assert re.search(
        rb'href="/settings"[^>]*>\s*Settings\s*</a>',
        response.data,
    )
    assert response.data.count(b'aria-label="Primary navigation"') == 1


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
