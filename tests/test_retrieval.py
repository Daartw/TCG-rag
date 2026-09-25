"""
Prueba básica de la recuperación semántica.

Requiere haber corrido `python -m src.ingest` al menos una vez para que
exista la base vectorial en data/chroma_db/.
"""
from src.vector_store import VectorStore


def test_search_returns_results():
    store = VectorStore()
    hits = store.search("carta de tipo Dragón con habilidad de curación", top_k=3)

    assert len(hits) > 0
    assert len(hits) <= 3
    for hit in hits:
        assert "document" in hit
        assert "metadata" in hit
        assert "name" in hit["metadata"]


def test_search_respects_top_k():
    store = VectorStore()
    hits = store.search("Rayquaza VMAX", top_k=2)

    assert len(hits) <= 2
