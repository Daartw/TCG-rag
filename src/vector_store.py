"""Wrapper sobre Chroma para indexar y consultar el catálogo de cartas."""
import chromadb
from sentence_transformers import SentenceTransformer

from src.config import CHROMA_PERSIST_DIR, COLLECTION_NAME, EMBEDDING_MODEL_NAME, TOP_K


class VectorStore:
    def __init__(self):
        self._embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
        self._client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        self._collection = self._client.get_or_create_collection(COLLECTION_NAME)

    def index(self, documents: list[str], metadatas: list[dict], ids: list[str]):
        """Genera embeddings y los guarda junto a sus metadatos en la colección."""
        embeddings = self._embedder.encode(documents).tolist()
        # upsert evita duplicados si se vuelve a correr la ingesta
        self._collection.upsert(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

    def search(self, query: str, top_k: int = TOP_K) -> list[dict]:
        """Recupera las top_k cartas más similares semánticamente a la consulta."""
        query_embedding = self._embedder.encode([query]).tolist()
        results = self._collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
        )
        hits = []
        for doc, meta, distance in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        ):
            hits.append({"document": doc, "metadata": meta, "distance": distance})
        return hits
