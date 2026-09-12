from fastapi.testclient import TestClient

from application.main import app


def test_health_is_a_basic_liveness_endpoint() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
