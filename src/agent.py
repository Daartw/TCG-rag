"""
Agente orquestador: decide si una consulta requiere la base de cartas (RAG),
la herramienta de precios en vivo, o ambas, y compone la respuesta final.

Ruta de decisión:
  - Intención de precio + carta identificada -> herramienta de precios
    (muestra hasta 6 impresiones de esa carta, ordenadas por valor).
  - Cualquier otra consulta -> recuperación híbrida + LLM (rag_pipeline).
"""
from __future__ import annotations

from src.catalog import Catalog
from src.query_parser import ParsedQuery, parse_query
from src.rag_pipeline import answer_with_rag, retrieve
from src.tools.price_api import get_prices, headline_price
from src.vector_store import VectorStore

MAX_PRICE_CARDS = 6


def _price_candidates(parsed: ParsedQuery, catalog: Catalog, store: VectorStore | None) -> list[dict]:
    if parsed.names:
        items, _ = catalog.search(
            name_exact=parsed.names[0], set_id=parsed.filters.get("set_id"),
            sort="newest", page_size=24,
        )
        if items:
            return items
    ids = retrieve(parsed, catalog, store, top_k=3)
    return catalog.get_cards(ids[:1])


def answer_price(parsed: ParsedQuery, catalog: Catalog, store: VectorStore | None) -> dict:
    candidates = _price_candidates(parsed, catalog, store)
    if not candidates:
        return {"answer": "No pude identificar la carta. Escribe su nombre exacto, por ejemplo "
                          "\"Umbreon VMAX\".", "cards": [], "llm": False}

    prices = get_prices([c["id"] for c in candidates])
    rows = []
    for card in candidates:
        card["price"] = prices.get(card["id"])
        head = headline_price(card["price"])
        rows.append((head[1] if head else -1, head[0] if head else None, card))
    rows.sort(key=lambda r: r[0], reverse=True)
    shown = [r for r in rows][:MAX_PRICE_CARDS]

    if all(r[1] is None for r in shown):
        answer = (f"Encontré {len(candidates)} impresión(es) de {candidates[0]['name']}, pero la API de "
                  "precios no respondió o no tiene datos ahora. Revisa los enlaces de cada carta.")
    else:
        lines = [f"Precios de referencia para {candidates[0]['name']} "
                 f"({len(candidates)} impresiones en el catálogo, ordenadas por valor):"]
        for _, label, card in shown:
            lines.append(f"- {card['name']} [{card['id']}] — {card['set']['name']} #{card['number']}"
                         f" ({card.get('rarity') or 's/r'}): {label or 'sin precio'}")
        lines.append("\nLos arte alternativo y secret rare suelen ser las impresiones de mayor valor. "
                     "Precios de TCGPlayer/Cardmarket vía pokemontcg.io; pueden variar.")
        answer = "\n".join(lines)
    return {"answer": answer, "cards": [r[2] for r in shown], "llm": False}


def handle_query(query: str, catalog: Catalog, store: VectorStore | None,
                 history: list[dict] | None = None) -> dict:
    parsed = parse_query(query, catalog)
    if parsed.wants_price:
        result = answer_price(parsed, catalog, store)
        intent = "price"
    else:
        result = answer_with_rag(parsed, catalog, store, history=history)
        intent = "rag"
    result.update({"intent": intent, "detected": {"names": parsed.names, "filters": parsed.filters}})
    return result
