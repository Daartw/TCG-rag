# Historial de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Sin publicar]

### Seguridad
- Content Security Policy, `X-Frame-Options` y `Permissions-Policy` en todas las respuestas.
- El límite del chat ya no lee `X-Forwarded-For` directamente: usa la IP resuelta por uvicorn, que
  solo confía en proxies de redes privadas (`FORWARDED_ALLOW_IPS`).
- Las direcciones IPv6 se agrupan por red /64 en el límite del chat y se agrega un tope global
  (`CHAT_GLOBAL_LIMIT_PER_MIN`).
- El historial del chat solo acepta los roles `user` y `assistant`.
- El frontend no usa manejadores de eventos en línea y solo enlaza URLs `http(s)`.
- CI: auditoría de dependencias (`pip-audit`) y análisis estático con CodeQL.
- docker-compose: el contenedor de la app se ejecuta sin capacidades de Linux ni escalada de privilegios.

## [1.0.0] — 2026-10-27

### Agregado
- Catálogo completo de Pokémon TCG: 176 sets y más de 20.600 cartas, con imágenes.
- Explorador web con búsqueda y filtros por set, tipo, categoría, rareza, HP y formato estándar.
- Asistente con IA (RAG) que responde preguntas sobre cartas usando el catálogo.
- Precios de mercado en vivo (TCGPlayer y Cardmarket) con caché.
- API REST (`/api/cards`, `/api/sets`, `/api/chat`…).
- Despliegue con Docker y Caddy (HTTPS automático) y CI con pruebas.

### Corregido
- Reintentos con espera progresiva en la ingesta ante errores 5xx de la API.
