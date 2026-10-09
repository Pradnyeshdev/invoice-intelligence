from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_http_200() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200


def test_health_returns_expected_response() -> None:
    response = client.get("/api/health")

    assert response.json() == {"status": "healthy"}
