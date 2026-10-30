# API

Todas las respuestas son JSON. La documentación interactiva está en `/docs` (si `EXPOSE_DOCS=true`).

## `GET /api/health`
Estado del servicio: cantidad de cartas y vectores indexados, y proveedor de LLM activo.

## `GET /api/meta`
Nombre del sitio, cantidad de cartas y sets, opciones de filtros y último set publicado.

## `GET /api/sets`
Lista de sets, del más nuevo al más antiguo.

## `GET /api/cards`
Búsqueda paginada en el catálogo.

| Parámetro | Tipo | Descripción |
|---|---|---|
| `q` | texto (máx. 200) | Nombre, ataque, habilidad o artista |
| `set` | texto | Id del set (ej. `swsh7`) |
| `series` | texto | Serie (ej. `Sword & Shield`) |
| `type` | texto, repetible | Tipo de energía (ej. `type=Fire&type=Water`) |
| `supertype` | texto | `Pokémon`, `Trainer` o `Energy` |
| `subtype` | texto | Ej. `Supporter`, `Item`, `Stadium`, `VMAX` |
| `rarity` | texto | Rareza |
| `min_hp` / `max_hp` | entero 0–500 | Rango de HP |
| `standard` | booleano | Solo cartas legales en formato estándar |
| `sort` | texto | `newest` (por defecto), `oldest`, `name`, `hp`, `number` |
| `page` | entero ≥ 1 | Página |
| `page_size` | entero 1–120 | Resultados por página (36 por defecto) |

Respuesta: `{ "data": [...], "total": 123, "page": 1, "page_size": 36 }`

## `GET /api/cards/{id}`
Detalle de una carta (ej. `swsh7-215`) con sus otras impresiones en `printings`. `404` si no existe.

## `GET /api/cards/{id}/price`
Precios en vivo de TCGPlayer (USD) y Cardmarket (EUR). Si no hay datos: `{ "available": false }`.

## `POST /api/chat`
Pregunta al asistente.

```json
{ "message": "cartas de tipo Dragón con más de 300 HP", "history": [] }
```

- `message`: 1 a 600 caracteres. `history`: hasta 12 mensajes previos `{ "role", "content" }`.
- Respuesta: texto del asistente, cartas usadas como contexto y `intent` (`rag` o `price`).
- Límite por IP: `CHAT_RATE_LIMIT_PER_MIN` consultas por minuto (responde `429` al superarlo).
