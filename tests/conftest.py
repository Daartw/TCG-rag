"""
Las pruebas usan un catálogo reducido (tests/fixtures) y embeddings por
hashing, así que no requieren internet, API keys ni descargar modelos.
"""
import os
import tempfile
from pathlib import Path

import pytest

_TMP = tempfile.mkdtemp(prefix="tcg-rag-tests-")
os.environ.update({
    "DATA_DIR": _TMP,
    "CARD_DATA_DIR": str(Path(__file__).parent / "fixtures" / "pokemon-tcg-data"),
    "EMBEDDING_BACKEND": "hash",
    "LLM_PROVIDER": "none",
    "INGEST_SET_IDS": "",
    "CHAT_RATE_LIMIT_PER_MIN": "1000",
    # la API de precios no se contacta en las pruebas
    "POKEMON_TCG_API_URL": "http://127.0.0.1:9/v2",
})


@pytest.fixture(scope="session", autouse=True)
def indexed():
    from src.ingest import run

    run()
    yield


@pytest.fixture(scope="session")
def catalog():
    from src.catalog import Catalog

    return Catalog()


@pytest.fixture(scope="session")
def store():
    from src.vector_store import VectorStore

    return VectorStore()
