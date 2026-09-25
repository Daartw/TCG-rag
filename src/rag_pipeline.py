"""Orquesta la recuperación semántica y la generación de la respuesta final."""
from src.llm_client import call_llm
from src.vector_store import VectorStore

SYSTEM_PROMPT = (
    "Eres un asistente experto en el set Pokemon TCG Evolving Skies. "
    "Responde unicamente usando la informacion de las cartas recuperadas en el "
    "contexto. Si la informacion no esta en el contexto, dilo explicitamente en "
    "vez de inventar datos. Cita el nombre exacto de cada carta que menciones."
)


def build_context(hits: list[dict]) -> str:
    """Concatena las cartas recuperadas en un bloque de contexto legible."""
    blocks = []
    for i, hit in enumerate(hits, start=1):
        blocks.append(f"[Carta {i}]\n{hit['document']}")
    return "\n\n".join(blocks)


def answer_with_rag(query: str, store: VectorStore) -> str:
    """Recupera cartas relevantes y genera la respuesta final anclada al contexto."""
    hits = store.search(query)
    context = build_context(hits)

    user_prompt = (
        f"Contexto (cartas recuperadas del catalogo del set):\n{context}\n\n"
        f"Pregunta del usuario: {query}"
    )
    return call_llm(SYSTEM_PROMPT, user_prompt)
