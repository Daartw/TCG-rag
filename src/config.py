"""Carga de configuración desde variables de entorno (.env)."""
import os
from dotenv import load_dotenv

load_dotenv()

POKEMON_SET_ID = os.getenv("POKEMON_SET_ID", "swsh7")
# Opcional: API key propia de https://pokemontcg.io/ para subir el límite de tasa
# y reducir errores 5xx del servicio. Sin ella, la API sigue funcionando pero con
# límites más bajos y mayor probabilidad de fallos intermitentes.
POKEMON_TCG_API_KEY = os.getenv("POKEMON_TCG_API_KEY")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "data/chroma_db")
COLLECTION_NAME = "evolving_skies_cards"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Modelo de embeddings local (no requiere API key)
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# Cantidad de cartas a recuperar por consulta (top-k)
TOP_K = 5
