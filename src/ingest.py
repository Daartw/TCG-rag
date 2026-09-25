"""
Descarga todas las cartas del set Evolving Skies desde la API pública de
Pokemon TCG y las indexa en la base de datos vectorial (Chroma).

Uso:
    python -m src.ingest
"""
import time

import requests

from src.config import POKEMON_SET_ID, POKEMON_TCG_API_KEY
from src.vector_store import VectorStore

POKEMON_TCG_API_URL = "https://api.pokemontcg.io/v2/cards"
PAGE_SIZE = 250
MAX_RETRIES = 5
BACKOFF_SECONDS = 3  # crece exponencialmente: 3, 6, 12, 24, 48...


def _get_with_retry(params: dict) -> dict:
    """Hace la petición a la API con reintentos y backoff exponencial.

    La API pública de pokemontcg.io es conocida por responder de forma
    intermitente con errores 5xx (502/503/504). En vez de fallar al primer
    error transitorio, reintentamos varias veces antes de abortar.
    """
    headers = {"X-Api-Key": POKEMON_TCG_API_KEY} if POKEMON_TCG_API_KEY else {}

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                POKEMON_TCG_API_URL, params=params, headers=headers, timeout=30
            )
            if response.status_code >= 500:
                raise requests.exceptions.HTTPError(
                    f"{response.status_code} Server Error", response=response
                )
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError,
                 requests.exceptions.Timeout) as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            wait = BACKOFF_SECONDS * (2 ** (attempt - 1))
            print(f"  Intento {attempt}/{MAX_RETRIES} falló ({exc}). "
                  f"Reintentando en {wait}s...")
            time.sleep(wait)

    raise RuntimeError(
        f"No se pudo consultar la API de Pokemon TCG tras {MAX_RETRIES} intentos."
    ) from last_error


def fetch_cards(set_id: str) -> list[dict]:
    """Descarga todas las cartas de un set, paginando la respuesta de la API."""
    cards = []
    page = 1
    while True:
        payload = _get_with_retry(
            {"q": f"set.id:{set_id}", "page": page, "pageSize": PAGE_SIZE}
        )
        batch = payload.get("data", [])
        cards.extend(batch)
        # Si la página trae menos cartas que el tamaño pedido, ya no hay más
        # páginas: evitamos pedir una página extra de más.
        if len(batch) < PAGE_SIZE:
            break
        page += 1
    return cards


def card_to_document(card: dict) -> str:
    """Convierte una carta (JSON de la API) en un documento de texto para embeber.

    Cada carta se trata como una unidad de información autocontenida (un chunk
    = una carta), según lo definido en el diseño del pipeline RAG.
    """
    lines = [
        f"Nombre: {card.get('name')}",
        f"Tipo(s): {', '.join(card.get('types', []) or ['N/A'])}",
        f"HP: {card.get('hp', 'N/A')}",
        f"Rareza: {card.get('rarity', 'N/A')}",
        f"Número en el set: {card.get('number')}",
    ]

    abilities = card.get("abilities") or []
    for ability in abilities:
        lines.append(f"Habilidad ({ability.get('name')}): {ability.get('text')}")

    attacks = card.get("attacks") or []
    for attack in attacks:
        lines.append(
            f"Ataque ({attack.get('name')}, costo {attack.get('convertedEnergyCost')}, "
            f"daño {attack.get('damage') or 'N/A'}): {attack.get('text') or ''}"
        )

    weaknesses = card.get("weaknesses") or []
    if weaknesses:
        lines.append(
            "Debilidad: " + ", ".join(f"{w['type']} {w['value']}" for w in weaknesses)
        )

    resistances = card.get("resistances") or []
    if resistances:
        lines.append(
            "Resistencia: " + ", ".join(f"{r['type']} {r['value']}" for r in resistances)
        )

    return "\n".join(lines)


def card_metadata(card: dict) -> dict:
    """Metadatos usados para filtrar antes/después de la búsqueda semántica."""
    return {
        "name": card.get("name", ""),
        "types": ",".join(card.get("types", []) or []),
        "rarity": card.get("rarity", "N/A"),
        "number": card.get("number", ""),
    }


def main():
    print(f"Descargando cartas del set '{POKEMON_SET_ID}'...")
    cards = fetch_cards(POKEMON_SET_ID)
    print(f"Se obtuvieron {len(cards)} cartas.")

    documents = [card_to_document(c) for c in cards]
    metadatas = [card_metadata(c) for c in cards]
    ids = [c["id"] for c in cards]

    store = VectorStore()
    store.index(documents=documents, metadatas=metadatas, ids=ids)
    print("Indexación completada en la base de datos vectorial.")


if __name__ == "__main__":
    main()
