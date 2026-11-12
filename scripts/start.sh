#!/bin/sh
# Arranque del servidor. Si el catálogo no existe (imagen construida con
# BUILD_INDEX=false o volumen vacío), lo genera antes de levantar la web.
set -e

if [ ! -s "${DATA_DIR:-data}/catalog.sqlite" ]; then
  echo "Catálogo no encontrado: ejecutando la ingesta inicial (puede tardar varios minutos)..."
  python -m src.ingest
fi

# Solo se confía en X-Forwarded-For cuando la conexión llega desde un proxy en una red privada
# (Caddy en docker-compose, o el balanceador de la plataforma). Si la app se expone directamente
# a internet, la cabecera se ignora y nadie puede falsear su IP para saltarse el límite del chat.
TRUSTED_PROXIES="127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,fc00::/7"

exec uvicorn src.api:app \
  --host "${HOST:-0.0.0.0}" \
  --port "${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-1}" \
  --proxy-headers \
  --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-$TRUSTED_PROXIES}"
