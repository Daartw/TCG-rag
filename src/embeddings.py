"""
Generación de embeddings.

- "fastembed" (por defecto): modelo ONNX local, corre en CPU sin torch ni GPU.
  El modelo multilingüe permite buscar en español sobre textos en inglés.
- "hash": embeddings deterministas por hashing de palabras. No requiere
  descargar ningún modelo; útil para pruebas o entornos sin internet.
"""
from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache

from src.config import EMBEDDING_BACKEND, EMBEDDING_CACHE_DIR, EMBEDDING_MODEL_NAME


class HashEmbedder:
    dim = 384

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = re.findall(r"\w+", text.lower())
        for token in tokens + [a + b for a, b in zip(tokens, tokens[1:])]:
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            vec[h % self.dim] += 1.0 if (h >> 9) & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(self, texts: list[str], batch_size: int = 256) -> list[list[float]]:
        return [self._vector(t) for t in texts]


class FastEmbedder:
    def __init__(self, model_name: str):
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name, cache_dir=EMBEDDING_CACHE_DIR)

    def embed(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(texts, batch_size=batch_size)]


@lru_cache(maxsize=1)
def get_embedder():
    if EMBEDDING_BACKEND == "hash":
        return HashEmbedder()
    return FastEmbedder(EMBEDDING_MODEL_NAME)
