#!/bin/sh
# Arranque del servidor. Si el catálogo no existe (imagen construida con
# BUILD_INDEX=false o volumen vacío), lo genera antes de levantar la web.
set -e

if [ ! -s "${DATA_DIR:-data}/catalog.sqlite" ]; then
  echo "Catálogo no encontrado: ejecutando la ingesta inicial (puede tardar varios minutos)..."
  python -m src.ingest
fi

exec uvicorn src.api:app \
  --host "${HOST:-0.0.0.0}" \
  --port "${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-1}" \
  --proxy-headers \
  --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}"
