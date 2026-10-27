"""Pruebas de la API web (sin LLM ni red)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from src.api import app

    with TestClient(app) as c:
        yield c


def test_health_and_meta(client):
    assert client.get("/api/health").json()["cards"] == 35
    meta = client.get("/api/meta").json()
    assert meta["set_count"] == 2 and "Dragon" in meta["filters"]["types"]


def test_cards_endpoint(client):
    r = client.get("/api/cards", params={"set": "swsh7", "type": "Darkness", "page_size": 5}).json()
    assert r["total"] >= 1 and all(c["set"]["id"] == "swsh7" for c in r["data"])
    detail = client.get("/api/cards/swsh7-215").json()
    assert detail["printings"] and all(p["name"] == "Umbreon VMAX" for p in detail["printings"])
    assert client.get("/api/cards/nope-1").status_code == 404


def test_chat_without_llm_returns_cards(client):
    r = client.post("/api/chat", json={"message": "cartas de tipo Dragón con más de 300 HP"}).json()
    assert r["intent"] == "rag" and r["cards"]
    assert all("Dragon" in c["types"] for c in r["cards"])


def test_price_intent_degrades_gracefully(client):
    r = client.post("/api/chat", json={"message": "¿cuánto vale Umbreon VMAX?"}).json()
    assert r["intent"] == "price" and r["cards"][0]["name"] == "Umbreon VMAX"


def test_spa_routes(client):
    for path in ("/", "/carta/swsh7-215", "/set/swsh7", "/asistente"):
        assert client.get(path).status_code == 200
