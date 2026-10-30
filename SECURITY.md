# Política de seguridad

## Reportar una vulnerabilidad

Si encuentras un problema de seguridad, **no abras un issue público**. Escríbeme a
**danie.arayar@duocuc.cl** con:

- Descripción del problema y su impacto.
- Pasos para reproducirlo.
- Versión o commit afectado.

Responderé dentro de 7 días y te mantendré informado hasta que se publique la corrección.

## Buenas prácticas al desplegar

- Mantén las API keys del LLM solo en el archivo `.env` del servidor (nunca en el repositorio).
- Despliega detrás de Caddy (incluido en `docker-compose.yml`) para tener HTTPS automático.
- Ajusta `CHAT_RATE_LIMIT_PER_MIN` para limitar el gasto de tu API key.
- Pon `EXPOSE_DOCS=false` si no quieres publicar la documentación interactiva de la API.
