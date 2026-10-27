"""
Herramienta externa (no vectorizada) para consultar precios de mercado en vivo.

Usa la API de pokemontcg.io, que expone precios de TCGPlayer (USD) y
Cardmarket (EUR) por carta. No se indexa en la base vectorial porque cambia
constantemente; se consulta solo cuando hace falta y se cachea en memoria.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from src.config import POKEMON_TCG_API_KEY, POKEMON_TCG_API_URL, PRICE_CACHE_SECONDS

_cache: dict[str, tuple[float, dict | None]] = {}
_lock = threading.Lock()


def _headers() -> dict:
    return {"X-Api-Key": POKEMON_TCG_API_KEY} if POKEMON_TCG_API_KEY else {}


def _simplify(card: dict) -> dict:
    tcgplayer = card.get("tcgplayer") or {}
    cardmarket = card.get("cardmarket") or {}
    tcg_prices = {
        variant: {k: v for k, v in values.items() if v is not None}
        for variant, values in (tcgplayer.get("prices") or {}).items()
    }
    cm = cardmarket.get("prices") or {}
    return {
        "id": card.get("id"),
        "name": card.get("name"),
        "tcgplayer": {
            "url": tcgplayer.get("url"),
            "updated_at": tcgplayer.get("updatedAt"),
            "prices_usd": tcg_prices,
        },
        "cardmarket": {
            "url": cardmarket.get("url"),
            "updated_at": cardmarket.get("updatedAt"),
            "prices_eur": {
                k: cm.get(k) for k in ("averageSellPrice", "lowPrice", "trendPrice", "avg7", "avg30",
                                       "reverseHoloTrend") if cm.get(k) is not None
            },
        },
    }


def get_card_price(card_id: str) -> dict | None:
    """Precio de una carta por su id (ej. 'swsh7-215'). None si no hay datos o la API falla."""
    now = time.time()
    with _lock:
        cached = _cache.get(card_id)
        ttl = PRICE_CACHE_SECONDS if (cached and cached[1]) else 60  # los fallos se reintentan pronto
        if cached and now - cached[0] < ttl:
            return cached[1]
    result = None
    for attempt in range(2):
        try:
            response = requests.get(f"{POKEMON_TCG_API_URL}/cards/{card_id}", headers=_headers(), timeout=15)
            if response.status_code == 404:
                break
            if response.status_code >= 500:
                raise requests.HTTPError(str(response.status_code))
            response.raise_for_status()
            result = _simplify(response.json().get("data") or {})
            break
        except requests.RequestException:
            time.sleep(1.5 * (attempt + 1))
    with _lock:
        _cache[card_id] = (now, result)
    return result


def get_prices(card_ids: list[str]) -> dict[str, dict | None]:
    """Consulta varios precios en paralelo."""
    with ThreadPoolExecutor(max_workers=6) as pool:
        return dict(zip(card_ids, pool.map(get_card_price, card_ids)))


def headline_price(price: dict | None) -> tuple[str, float] | None:
    """Precio de referencia más representativo: TCGPlayer market, o tendencia de Cardmarket."""
    if not price:
        return None
    for variant, values in (price.get("tcgplayer", {}).get("prices_usd") or {}).items():
        if values.get("market") is not None:
            return f"US${values['market']:.2f} (TCGPlayer, {variant})", values["market"]
    trend = price.get("cardmarket", {}).get("prices_eur", {}).get("trendPrice")
    if trend is not None:
        return f"€{trend:.2f} (Cardmarket, tendencia)", trend
    return None
