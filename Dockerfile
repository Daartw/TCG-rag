# Imagen lista para producción: incluye el catálogo completo (~20.600 cartas),
# la base vectorial y el modelo de embeddings, así que arranca en segundos.
#
#   docker build -t tcg-rag .
#   docker run -p 8000:8000 --env-file .env tcg-rag
#
# Para una imagen liviana que indexe al primer arranque: --build-arg BUILD_INDEX=false
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/app/data \
    ANONYMIZED_TELEMETRY=False

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --create-home --uid 1000 app \
 && mkdir -p /app/data/images \
 && chown -R app:app /app
USER app

COPY --chown=app:app src ./src
COPY --chown=app:app web ./web
COPY --chown=app:app scripts ./scripts

# Descarga el catálogo, genera los embeddings y descarta los JSON originales.
# Cambia CACHE_BUST (p. ej. con la fecha) para forzar una actualización del catálogo.
ARG BUILD_INDEX=true
ARG CACHE_BUST=1
RUN if [ "$BUILD_INDEX" = "true" ]; then \
      echo "catalog build $CACHE_BUST" && python -m src.ingest && rm -rf /app/data/source; \
    fi

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/api/health" || exit 1

CMD ["sh", "scripts/start.sh"]
