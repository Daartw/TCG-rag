"""
Descarga todas las cartas del set Evolving Skies desde la API pública de
Pokemon TCG y las indexa en la base de datos vectorial (Chroma).

Uso:
    python -m src.ingest
"""
import requests

from src.config import POKEMON_SET_ID
from src.vector_store import VectorStore

POKEMON_TCG_API_URL = "https://api.pokemontcg.io/v2/cards"


def fetch_cards(set_id: str) -> list[dict]:
    """Descarga todas las cartas de un set, paginando la respuesta de la API."""
    cards = []
    page = 1
    while True:
        response = requests.get(
            POKEMON_TCG_API_URL,
            params={"q": f"set.id:{set_id}", "page": page, "pageSize": 250},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        batch = payload.get("data", [])
        if not batch:
            break
        cards.extend(batch)
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
