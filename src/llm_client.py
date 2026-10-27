"""
Cliente del LLM usado en la etapa de generación.

`call_llm` es la única función que usa el resto del sistema, así que cambiar
de proveedor no afecta al pipeline. Proveedores soportados (LLM_PROVIDER):

- groq       (por defecto si hay GROQ_API_KEY; gratuito, sin tarjeta)
- anthropic  (Claude; requiere `pip install anthropic`)
- openai     (OpenAI o cualquier API compatible vía OPENAI_BASE_URL)
- none       (sin LLM: el sistema responde mostrando las cartas recuperadas)
"""
from __future__ import annotations

from functools import lru_cache

import requests

from src.config import (
    ANTHROPIC_API_KEY, GROQ_API_KEY, LLM_MAX_TOKENS, LLM_MODEL, LLM_PROVIDER,
    OPENAI_API_KEY, OPENAI_BASE_URL,
)

DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-4o-mini",
}


@lru_cache(maxsize=1)
def provider() -> str:
    if LLM_PROVIDER != "auto":
        return LLM_PROVIDER
    if GROQ_API_KEY:
        return "groq"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    if OPENAI_API_KEY:
        return "openai"
    return "none"


def llm_available() -> bool:
    return provider() != "none"


def model_name() -> str | None:
    p = provider()
    return LLM_MODEL or DEFAULT_MODELS.get(p)


@lru_cache(maxsize=1)
def _groq_client():
    from groq import Groq

    return Groq(api_key=GROQ_API_KEY)


@lru_cache(maxsize=1)
def _anthropic_client():
    import anthropic

    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def call_llm(system_prompt: str, user_prompt: str, history: list[dict] | None = None) -> str:
    """Envía el prompt al LLM y devuelve el texto. `history` = [{role, content}, ...]."""
    p = provider()
    messages = [m for m in (history or []) if m.get("role") in {"user", "assistant"} and m.get("content")]
    messages = messages[-6:] + [{"role": "user", "content": user_prompt}]

    if p == "groq":
        response = _groq_client().chat.completions.create(
            model=model_name(),
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.3,
            messages=[{"role": "system", "content": system_prompt}, *messages],
        )
        return response.choices[0].message.content

    if p == "anthropic":
        response = _anthropic_client().messages.create(
            model=model_name(),
            max_tokens=LLM_MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        )
        return "".join(block.text for block in response.content if block.type == "text")

    if p == "openai":
        response = requests.post(
            f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": model_name(),
                "max_tokens": LLM_MAX_TOKENS,
                "temperature": 0.3,
                "messages": [{"role": "system", "content": system_prompt}, *messages],
            },
            timeout=90,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    raise RuntimeError("No hay proveedor de LLM configurado")
