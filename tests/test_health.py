"""Health endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_check_returns_service_status(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "be-vita-hot-engine-test"
    assert body["environment"] == "test"
