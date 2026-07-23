"""Route-level tests for the CryoCheck application shell."""


def test_landing_page_returns_200(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Deice Data Validation" in response.data


def test_health_returns_healthy_status(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "healthy",
        "application": "CryoCheck",
    }


def test_not_found_page_uses_custom_template(client):
    response = client.get("/this-page-does-not-exist")

    assert response.status_code == 404
    assert b"Page not found" in response.data
