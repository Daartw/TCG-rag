"""
Cliente del LLM usado en la etapa de generación.

Se deja como una función independiente (call_llm) para que sea fácil de
intercambiar entre proveedores sin tocar el resto del pipeline (rag_pipeline.py
y agent.py solo llaman a call_llm, sin saber qué proveedor hay detrás).

Por defecto usa la API de Groq (gratuita, sin tarjeta, formato compatible con
OpenAI). Se deja comentado el bloque equivalente para Anthropic por si el
equipo decide cambiar de proveedor más adelante.
"""
from groq import Groq

from src.config import GROQ_API_KEY

_client = Groq(api_key=GROQ_API_KEY)

MODEL_NAME = "llama-3.3-70b-versatile"


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Envía el prompt de sistema + usuario al LLM y devuelve el texto de respuesta."""
    response = _client.chat.completions.create(
        model=MODEL_NAME,
        max_tokens=800,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


# --- Alternativa con Anthropic (Claude) ---
# import anthropic
# from src.config import ANTHROPIC_API_KEY
# _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
# MODEL_NAME = "claude-sonnet-4-6"
#
# def call_llm(system_prompt: str, user_prompt: str) -> str:
#     response = _client.messages.create(
#         model=MODEL_NAME,
#         max_tokens=800,
#         system=system_prompt,
#         messages=[{"role": "user", "content": user_prompt}],
#     )
#     return "".join(block.text for block in response.content if block.type == "text")
