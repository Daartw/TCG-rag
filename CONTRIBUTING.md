# Cómo contribuir

¡Gracias por tu interés en mejorar Pokémon TCG RAG!

## Preparar el entorno

```bash
python -m venv .venv && source .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Las pruebas usan un catálogo reducido (`tests/fixtures`) y embeddings por hashing, así que no
necesitan internet, API keys ni descargar modelos:

```bash
pytest -q
```

## Flujo de trabajo

1. Crea una rama desde `main` con un nombre descriptivo (`fix/...`, `feat/...`, `docs/...`, `test/...`).
2. Haz cambios pequeños y enfocados; agrega o actualiza pruebas cuando cambie el comportamiento.
3. Usa mensajes de commit en español con prefijo: `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `chore:`.
4. Abre un pull request completando la plantilla. El CI debe pasar antes de unirlo.

## Estilo

- Python 3.12, funciones pequeñas y con nombres claros.
- Comentarios en español cuando expliquen el *porqué*.
- Nunca subas claves ni el archivo `.env`.
