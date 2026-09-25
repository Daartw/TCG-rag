"""
Herramienta externa (no vectorizada) para consultar el precio de mercado
actual de una carta. Se reutiliza la misma API de Pokemon TCG, que expone
precios de TCGPlayer y Cardmarket junto a los datos de cada carta.

Esta fuente NO se indexa en la base vectorial porque su valor cambia
constantemente; se consulta en vivo solo cuando la consulta del usuario lo
requiere (ver src/agent.py).
"""
import requests

POKEMON_TCG_API_URL = "https://api.pokemontcg.io/v2/cards"


def get_card_price(card_name: str) -> dict | None:
    """Busca una carta por nombre y devuelve su información de precio.

    Devuelve None si no se encuentra la carta.
    """
    response = requests.get(
        POKEMON_TCG_API_URL,
        params={"q": f'name:"{card_name}"', "pageSize": 1},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json().get("data", [])
    if not data:
        return None

    card = data[0]
    tcgplayer = card.get("tcgplayer", {}).get("prices", {})
    cardmarket = card.get("cardmarket", {}).get("prices", {})

    return {
        "name": card.get("name"),
        "tcgplayer_usd": tcgplayer,
        "cardmarket_eur": cardmarket,
        "source_url": card.get("tcgplayer", {}).get("url"),
    }
