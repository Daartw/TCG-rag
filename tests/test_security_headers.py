"""Cabeceras de seguridad y caché de la API."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from src.api import app

    with TestClient(app) as c:
        yield c


def test_security_headers_on_every_response(client):
    for path in ("/", "/api/health", "/api/cards/nope-1"):
        headers = client.get(path).headers
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_successful_api_gets_are_cacheable_but_errors_are_not(client):
    assert client.get("/api/sets").headers["cache-control"] == "public, max-age=300"
    assert "public" not in client.get("/api/cards/nope-1").headers.get("cache-control", "")


def test_chat_rejects_invalid_body(client):
    assert client.post("/api/chat", json={}).status_code == 422
