"""Wrapper sobre Chroma para indexar y consultar el catálogo de cartas."""
from __future__ import annotations

import chromadb

from src.config import CHROMA_PERSIST_DIR, COLLECTION_NAME, TOP_K
from src.embeddings import get_embedder


def build_where(filters: dict | None) -> dict | None:
    """Traduce filtros simples a la sintaxis `where` de Chroma."""
    if not filters:
        return None
    clauses = []
    if filters.get("set_id"):
        clauses.append({"set_id": filters["set_id"]})
    if filters.get("supertype"):
        clauses.append({"supertype": filters["supertype"]})
    for t in filters.get("types") or []:
        clauses.append({f"type_{t}": True})
    if filters.get("subtype"):
        clauses.append({f"sub_{filters['subtype']}": True})
    if filters.get("min_hp") is not None:
        clauses.append({"hp": {"$gte": int(filters["min_hp"])}})
    if filters.get("max_hp") is not None:
        clauses.append({"hp": {"$lte": int(filters["max_hp"])}})
    if filters.get("standard"):
        clauses.append({"standard": True})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


class VectorStore:
    def __init__(self, persist_dir: str = CHROMA_PERSIST_DIR):
        self._embedder = get_embedder()
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )

    def count(self) -> int:
        return self._collection.count()

    def reset(self):
        try:
            self._client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        self._collection = self._client.get_or_create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )

    def index(self, documents: list[str], metadatas: list[dict], ids: list[str], batch_size: int = 512):
        """Genera embeddings y los guarda junto a sus metadatos (por lotes)."""
        for start in range(0, len(documents), batch_size):
            docs = documents[start:start + batch_size]
            embeddings = self._embedder.embed(docs)
            # upsert evita duplicados si se vuelve a correr la ingesta
            self._collection.upsert(
                documents=docs,
                embeddings=embeddings,
                metadatas=metadatas[start:start + batch_size],
                ids=ids[start:start + batch_size],
            )
            done = min(start + batch_size, len(documents))
            print(f"  Embeddings: {done}/{len(documents)}", flush=True)

    def search(self, query: str, top_k: int = TOP_K, filters: dict | None = None) -> list[dict]:
        """Recupera las top_k cartas más similares a la consulta (con filtros opcionales)."""
        if self.count() == 0:
            return []
        query_embedding = self._embedder.embed([query])
        results = self._collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            where=build_where(filters),
        )
        hits = []
        for card_id, doc, meta, distance in zip(
            results["ids"][0], results["documents"][0], results["metadatas"][0], results["distances"][0]
        ):
            hits.append({"id": card_id, "document": doc, "metadata": meta, "distance": distance})
        return hits
