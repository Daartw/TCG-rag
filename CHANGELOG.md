# Historial de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

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
