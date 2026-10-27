"""
Recuperación híbrida + generación.

Recuperación:
  1. Cartas nombradas explícitamente en la consulta (búsqueda exacta en SQLite).
  2. Búsqueda semántica en Chroma, aplicando los filtros detectados (tipo, HP, set...).
  3. Respaldo con búsqueda de texto completo (FTS5) si lo anterior no alcanza.
Las reimpresiones de una misma carta se agrupan para dar variedad al contexto.
"""
from __future__ import annotations

from src.catalog import Catalog, normalize
from src.config import TOP_K
from src.llm_client import call_llm, llm_available
from src.query_parser import ParsedQuery
from src.vector_store import VectorStore

SYSTEM_PROMPT = (
    "Eres un asistente experto en el juego de cartas coleccionables Pokémon (Pokémon TCG). "
    "Respondes en el idioma del usuario (por defecto español), de forma clara y concisa. "
    "Usa ÚNICAMENTE la información de las cartas del contexto para datos concretos "
    "(HP, ataques, daño, habilidades, set, rareza, legalidad). Si algo no está en el "
    "contexto, dilo explícitamente en vez de inventarlo; puedes aportar conocimiento "
    "general de estrategia del juego, dejando claro que es una sugerencia. "
    "Cita cada carta por su nombre exacto seguido de su id entre corchetes, por ejemplo "
    "Rayquaza VMAX [swsh7-111]. Los textos de las cartas están en inglés: tradúcelos "
    "o resúmelos cuando ayude."
)

MAX_PER_NAME = 3


def retrieve(parsed: ParsedQuery, catalog: Catalog, store: VectorStore | None, top_k: int = TOP_K) -> list[str]:
    ids: list[str] = []
    seen_names: dict[str, int] = {}

    def add(card_id: str, name: str, limit: int) -> bool:
        key = normalize(name)
        if card_id in ids or seen_names.get(key, 0) >= limit:
            return False
        ids.append(card_id)
        seen_names[key] = seen_names.get(key, 0) + 1
        return True

    filters = dict(parsed.filters)

    # 1) cartas mencionadas por nombre
    for name in parsed.names[:4]:
        items, _ = parsed_search(catalog, name_exact=name, set_id=filters.get("set_id"))
        if not items and filters.get("set_id"):
            items, _ = parsed_search(catalog, name_exact=name)
        for item in items:
            add(item["id"], item["name"], MAX_PER_NAME)

    # 2) búsqueda semántica (una sola impresión por nombre)
    if store is not None:
        hits = store.search(parsed.text, top_k=top_k * 3, filters=filters)
        if not hits and filters:
            hits = store.search(parsed.text, top_k=top_k * 3)
        for hit in hits:
            if len(ids) >= top_k + len(parsed.names):
                break
            add(hit["id"], hit["metadata"].get("name", hit["id"]), 1)

    # 3) respaldo con texto completo / filtros en SQLite
    if len(ids) < top_k:
        items, _ = catalog.search(q=parsed.text, **_sql_filters(parsed.filters), page_size=top_k * 3)
        if not items and parsed.has_filters:
            items, _ = catalog.search(**_sql_filters(parsed.filters), sort="newest", page_size=top_k * 3)
        for item in items:
            if len(ids) >= top_k:
                break
            add(item["id"], item["name"], 1)
    return ids


def _sql_filters(filters: dict) -> dict:
    allowed = {"set_id", "types", "supertype", "subtype", "min_hp", "max_hp", "standard"}
    return {k: v for k, v in filters.items() if k in allowed}


def parsed_search(catalog: Catalog, **kwargs):
    return catalog.search(sort="newest", page_size=MAX_PER_NAME * 2, **kwargs)


def build_context(card_ids: list[str], catalog: Catalog) -> str:
    blocks = []
    for i, card_id in enumerate(card_ids, start=1):
        doc = catalog.card_document(card_id)
        if doc:
            blocks.append(f"[Carta {i} | id {card_id}]\n{doc}")
    return "\n\n".join(blocks)


def fallback_answer(cards: list[dict], parsed: ParsedQuery) -> str:
    if not cards:
        return "No encontré cartas que coincidan con tu consulta. Prueba con otro nombre o menos filtros."
    lines = ["Estas son las cartas más relevantes que encontré:"]
    for c in cards:
        bits = [c["set"]["name"], c.get("rarity") or ""]
        if c.get("hp"):
            bits.append(f"{c['hp']} HP")
        if c.get("types"):
            bits.append("/".join(c["types"]))
        lines.append(f"- {c['name']} [{c['id']}] — " + ", ".join(b for b in bits if b))
    lines.append("\n(Configura una API key de LLM para obtener respuestas redactadas y recomendaciones.)")
    return "\n".join(lines)


def answer_with_rag(parsed: ParsedQuery, catalog: Catalog, store: VectorStore | None,
                    history: list[dict] | None = None) -> dict:
    card_ids = retrieve(parsed, catalog, store)
    cards = catalog.get_cards(card_ids)

    if not llm_available():
        return {"answer": fallback_answer(cards, parsed), "cards": cards, "llm": False}

    context = build_context(card_ids, catalog)
    user_prompt = (
        f"Contexto (cartas recuperadas del catálogo):\n{context or '(sin resultados)'}\n\n"
        f"Pregunta del usuario: {parsed.text}"
    )
    try:
        answer = call_llm(SYSTEM_PROMPT, user_prompt, history=history)
        return {"answer": answer, "cards": cards, "llm": True}
    except Exception as exc:  # el LLM no debe tumbar la respuesta: mostramos las cartas
        print(f"[llm] error: {exc}")
        return {"answer": fallback_answer(cards, parsed), "cards": cards, "llm": False,
                "warning": "El modelo de lenguaje no respondió; se muestran las cartas encontradas."}
