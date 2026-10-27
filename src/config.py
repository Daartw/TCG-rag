"""Carga de configuración desde variables de entorno (.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


# --- Datos ---------------------------------------------------------------
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
# Catálogo estructurado (SQLite + búsqueda de texto completo FTS5)
CATALOG_DB_PATH = Path(os.getenv("CATALOG_DB_PATH", DATA_DIR / "catalog.sqlite"))
# Base vectorial (Chroma)
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", str(DATA_DIR / "chroma_db"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "pokemon_tcg_cards")

# Fuente del catálogo: volcado JSON oficial del proyecto pokemontcg.io en GitHub
# (todas las cartas en inglés de todos los sets, con URLs de imágenes).
CARD_DATA_REPO = os.getenv(
    "CARD_DATA_REPO", "https://github.com/PokemonTCG/pokemon-tcg-data"
)
CARD_DATA_BRANCH = os.getenv("CARD_DATA_BRANCH", "master")
# Si ya tienes el repo clonado, apunta aquí para no volver a descargarlo.
CARD_DATA_DIR = os.getenv("CARD_DATA_DIR")
# Opcional: limitar la ingesta a ciertos sets (ids separados por coma, ej. "swsh7,sv1").
# Vacío = todos los sets.
INGEST_SET_IDS = [s.strip() for s in os.getenv("INGEST_SET_IDS", "").split(",") if s.strip()]

# --- API pública de Pokémon TCG (precios en vivo) -------------------------
POKEMON_TCG_API_URL = os.getenv("POKEMON_TCG_API_URL", "https://api.pokemontcg.io/v2")
# Opcional: API key propia de https://pokemontcg.io/ para subir el límite de tasa.
POKEMON_TCG_API_KEY = os.getenv("POKEMON_TCG_API_KEY")
PRICE_CACHE_SECONDS = int(os.getenv("PRICE_CACHE_SECONDS", "3600"))

# --- Imágenes -------------------------------------------------------------
# Por defecto las imágenes se sirven desde el CDN de pokemontcg.io.
# Si las espejas localmente (scripts/mirror_images.py), pon IMAGE_BASE_URL=/images
REMOTE_IMAGE_BASE = "https://images.pokemontcg.io"
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL", REMOTE_IMAGE_BASE).rstrip("/")
IMAGES_DIR = Path(os.getenv("IMAGES_DIR", DATA_DIR / "images"))

# --- Embeddings -----------------------------------------------------------
# Modelo ONNX local vía fastembed (sin GPU ni torch). El multilingüe permite
# consultas en español contra textos de cartas en inglés.
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
# "fastembed" (producción) o "hash" (sin descarga de modelo; solo para pruebas)
EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "fastembed")
EMBEDDING_CACHE_DIR = os.getenv("EMBEDDING_CACHE_DIR", str(DATA_DIR / "models"))

# Cantidad de cartas a recuperar por consulta (top-k)
TOP_K = int(os.getenv("TOP_K", "8"))

# --- LLM ------------------------------------------------------------------
# "groq", "anthropic", "openai", "none" o "auto" (elige según la API key presente)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").lower()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Para OpenAI u otro proveedor compatible (OpenRouter, Together, Ollama...)
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL")  # vacío = modelo por defecto del proveedor
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "900"))

# --- Servidor web ---------------------------------------------------------
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
# Orígenes permitidos para CORS (coma). "*" = cualquiera.
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
# Límite de consultas al chat por IP y por minuto (protege tu API key del LLM)
CHAT_RATE_LIMIT_PER_MIN = int(os.getenv("CHAT_RATE_LIMIT_PER_MIN", "15"))
SITE_NAME = os.getenv("SITE_NAME", "PokéDex TCG")
EXPOSE_DOCS = _env_bool("EXPOSE_DOCS", True)
