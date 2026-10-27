"""
Construye el catálogo completo (todas las cartas de todos los sets) y la base
vectorial.

Uso:
    python -m src.ingest                 # todo el catálogo (~20.600 cartas)
    python -m src.ingest --sets swsh7    # solo algunos sets
    python -m src.ingest --refresh       # vuelve a descargar los datos
    python -m src.ingest --skip-vectors  # solo SQLite (rápido, sin embeddings)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time

from src.catalog import Catalog, card_to_document
from src.config import INGEST_SET_IDS
from src.data_sources import ensure_source_dir, load_cards, load_sets
from src.vector_store import VectorStore


def card_metadata(card: dict, set_info: dict) -> dict:
    """Metadatos para filtrar en la búsqueda semántica (Chroma solo admite escalares)."""
    hp = card.get("hp")
    meta = {
        "name": card.get("name", ""),
        "set_id": set_info["id"],
        "set_name": set_info["name"],
        "supertype": card.get("supertype") or "",
        "rarity": card.get("rarity") or "N/A",
        "number": card.get("number") or "",
        "hp": int(hp) if str(hp or "").isdigit() else 0,
        "standard": (card.get("legalities") or {}).get("standard") == "Legal",
        "release": (set_info.get("releaseDate") or "").replace("/", "-"),
    }
    for t in card.get("types") or []:
        meta[f"type_{t}"] = True
    for sub in card.get("subtypes") or []:
        meta[f"sub_{sub}"] = True
    return meta


def fingerprint(cards_by_set: dict[str, list[dict]]) -> str:
    h = hashlib.sha256()
    for set_id in sorted(cards_by_set):
        h.update(json.dumps(cards_by_set[set_id], sort_keys=True).encode())
    return h.hexdigest()[:16]


def run(set_ids: list[str] | None = None, refresh: bool = False, skip_vectors: bool = False,
        force_vectors: bool = False):
    start = time.time()
    source = ensure_source_dir(refresh=refresh)
    sets = load_sets(source)
    cards_by_set = load_cards(source, set_ids or None)
    total = sum(len(c) for c in cards_by_set.values())
    print(f"Catálogo: {len(cards_by_set)} sets, {total} cartas (fuente: {source})")

    catalog = Catalog()
    count = catalog.rebuild(sets, cards_by_set)
    print(f"SQLite listo: {count} cartas indexadas con búsqueda de texto completo.")

    if skip_vectors:
        print("Se omitió la base vectorial (--skip-vectors).")
        return

    fp = fingerprint(cards_by_set)
    store = VectorStore()
    if not force_vectors and catalog.get_meta("vector_fingerprint") == fp and store.count() == count:
        print("La base vectorial ya está al día; no se regeneran embeddings.")
        return

    set_index = {s["id"]: s for s in sets}
    documents, metadatas, ids = [], [], []
    for set_id, cards in cards_by_set.items():
        set_info = set_index.get(set_id)
        if not set_info:
            continue
        for card in cards:
            documents.append(card_to_document({**card, "set": set_info}))
            metadatas.append(card_metadata(card, set_info))
            ids.append(card["id"])

    print(f"Generando embeddings para {len(documents)} cartas (puede tardar varios minutos)...")
    store.reset()
    store.index(documents=documents, metadatas=metadatas, ids=ids)
    catalog.set_meta("vector_fingerprint", fp)
    print(f"Indexación completada en {time.time() - start:.0f}s.")


def main():
    parser = argparse.ArgumentParser(description="Ingesta del catálogo Pokémon TCG")
    parser.add_argument("--sets", help="ids de sets separados por coma (por defecto: todos)")
    parser.add_argument("--refresh", action="store_true", help="vuelve a descargar el volcado de datos")
    parser.add_argument("--skip-vectors", action="store_true", help="no generar embeddings")
    parser.add_argument("--force-vectors", action="store_true", help="regenera embeddings aunque estén al día")
    args = parser.parse_args()
    set_ids = [s.strip() for s in args.sets.split(",")] if args.sets else INGEST_SET_IDS
    run(set_ids=set_ids, refresh=args.refresh, skip_vectors=args.skip_vectors,
        force_vectors=args.force_vectors)


if __name__ == "__main__":
    main()
