"""Pruebas de la herramienta de precios en vivo, sin contactar la API real."""
import pytest
import requests

from src.tools import price_api


class FakeResponse:
    def __init__(self, status: int, payload: dict | None = None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


CARD = {
    "id": "swsh7-215",
    "name": "Umbreon VMAX",
    "tcgplayer": {"url": "https://tcg.example", "updatedAt": "2026/10/01", "prices": {"holofoil": {"market": 1234.5, "low": None}}},
    "cardmarket": {"url": "https://cm.example", "updatedAt": "2026/10/01", "prices": {"trendPrice": 1100.0, "lowPrice": None}},
}


@pytest.fixture(autouse=True)
def clean_cache(monkeypatch):
    price_api._cache.clear()
    monkeypatch.setattr(price_api.time, "sleep", lambda _s: None)
    yield
    price_api._cache.clear()


def test_simplifies_and_caches(monkeypatch):
    calls = []

    def fake_get(url, **_kw):
        calls.append(url)
        return FakeResponse(200, {"data": CARD})

    monkeypatch.setattr(price_api.requests, "get", fake_get)
    price = price_api.get_card_price("swsh7-215")
    assert price["tcgplayer"]["prices_usd"] == {"holofoil": {"market": 1234.5}}  # sin valores None
    assert price["cardmarket"]["prices_eur"] == {"trendPrice": 1100.0}
    assert price_api.get_card_price("swsh7-215") == price
    assert len(calls) == 1  # la segunda vez sale de la caché


def test_not_found_returns_none_without_retry(monkeypatch):
    calls = []
    monkeypatch.setattr(price_api.requests, "get", lambda url, **kw: calls.append(url) or FakeResponse(404))
    assert price_api.get_card_price("nope-1") is None
    assert len(calls) == 1


def test_server_errors_are_retried_then_give_up(monkeypatch):
    calls = []
    monkeypatch.setattr(price_api.requests, "get", lambda url, **kw: calls.append(url) or FakeResponse(503))
    assert price_api.get_card_price("swsh7-215") is None
    assert len(calls) == 2


def test_headline_price_prefers_tcgplayer_market():
    assert price_api.headline_price(price_api._simplify(CARD)) == ("US$1234.50 (TCGPlayer, holofoil)", 1234.5)
    only_cm = {**CARD, "tcgplayer": {}}
    assert price_api.headline_price(price_api._simplify(only_cm)) == ("€1100.00 (Cardmarket, tendencia)", 1100.0)
    assert price_api.headline_price(None) is None
