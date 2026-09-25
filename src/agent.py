"""
Agente orquestador: decide si una consulta requiere la base vectorial (RAG),
la herramienta de precios externa, o ambas, y compone la respuesta final.

Nota de diseño: esta implementación usa una regla simple basada en palabras
clave para decidir la ruta, suficiente para el alcance de esta evaluación.
Una extensión natural es reemplazarla por "tool calling" nativo del LLM
(dejando que el propio modelo decida qué herramienta invocar), manteniendo
la misma interfaz de las funciones `rag_pipeline.answer_with_rag` y
`tools.price_api.get_card_price`.
"""
import re

from src.rag_pipeline import answer_with_rag
from src.tools.price_api import get_card_price
from src.vector_store import VectorStore

PRICE_KEYWORDS = ["precio", "cuesta", "vale", "valor de mercado", "cuánto vale"]


def _wants_price(query: str) -> bool:
    q = query.lower()
    return any(keyword in q for keyword in PRICE_KEYWORDS)


def _extract_card_name(query: str) -> str:
    """Heurística simple: usa el texto entre comillas si existe, o la consulta
    completa como fallback (para casos como '¿cuánto vale Umbreon VMAX?')."""
    match = re.search(r'"([^"]+)"', query)
    return match.group(1) if match else query


def handle_query(query: str, store: VectorStore) -> str:
    if _wants_price(query):
        card_name = _extract_card_name(query)
        price_info = get_card_price(card_name)
        if price_info is None:
            return f"No encontré información de precio para '{card_name}'."
        return (
            f"{price_info['name']} — precios de referencia:\n"
            f"TCGPlayer (USD): {price_info['tcgplayer_usd']}\n"
            f"Cardmarket (EUR): {price_info['cardmarket_eur']}"
        )

    # Caso general: búsqueda de cartas, sinergias o reglas -> RAG interno
    return answer_with_rag(query, store)
