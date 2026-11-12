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
- Limita `CORS_ORIGINS` a tu dominio si no quieres que otros sitios consuman tu API desde el navegador.
- No definas `FORWARDED_ALLOW_IPS=*` si la app es accesible sin pasar por tu proxy: permitiría falsear la IP y saltarse el límite del chat.
- Mantén `WEB_CONCURRENCY=1`, o mueve el límite de consultas a un almacén compartido (Redis) si necesitas más procesos.

## Medidas implementadas

- **Content Security Policy**: el sitio solo ejecuta sus propios scripts; `X-Frame-Options`, `nosniff`, `Referrer-Policy` y `Permissions-Policy` en todas las respuestas, y HSTS en Caddy.
- **Límite de consultas** al asistente por visitante (IPv6 agrupado por red /64) y tope global.
- La IP del visitante solo se toma de `X-Forwarded-For` cuando la conexión viene de un proxy de confianza.
- Entrada validada (largo de mensajes e historial, roles permitidos) y consultas SQL parametrizadas.
- El frontend escapa todos los datos antes de insertarlos en la página, incluidas las respuestas del LLM.
- Contenedor sin privilegios de root, con *healthcheck*.
- Dependabot, `pip-audit` y CodeQL en la integración continua.
