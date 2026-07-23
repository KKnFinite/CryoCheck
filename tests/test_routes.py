"""Route-level tests for the CryoCheck application shell."""

from sqlalchemy import event

from app.extensions import db


def test_landing_page_returns_200(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Deice Data Validation" in response.data


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
    assert b"Page not found" in response.data
