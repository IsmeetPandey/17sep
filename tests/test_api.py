from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "invoiceguard"}


def test_api_key_is_enforced_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_key", "secret-test-key")
    with TestClient(app) as client:
        assert client.get("/exceptions").status_code == 401
        assert client.get("/exceptions", headers={"X-API-Key": "secret-test-key"}).status_code == 200
