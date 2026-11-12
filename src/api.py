"""
API web + sitio estático.

Uso local:
    uvicorn src.api:app --reload
Producción: ver Dockerfile / docker-compose.yml
"""
from __future__ import annotations

import ipaddress
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from threading import Lock
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.agent import handle_query
from src.catalog import Catalog
from src.config import (
    BASE_DIR, CHAT_GLOBAL_LIMIT_PER_MIN, CHAT_RATE_LIMIT_PER_MIN, CORS_ORIGINS, EXPOSE_DOCS, IMAGE_BASE_URL,
    IMAGES_DIR, REMOTE_IMAGE_BASE, SITE_NAME,
)
from src.llm_client import llm_available, model_name, provider
from src.tools.price_api import get_card_price
from src.vector_store import VectorStore

WEB_DIR = BASE_DIR / "web"
state: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    catalog = Catalog()
    state["catalog"] = catalog
    state["filters"] = catalog.filter_options() if catalog.count() else {}
    try:
        store = VectorStore()
        state["store"] = store if store.count() else None
    except Exception as exc:  # sin base vectorial el sitio sigue funcionando (FTS)
        print(f"[startup] base vectorial no disponible: {exc}")
        state["store"] = None
    print(f"[startup] {catalog.count()} cartas | vectores: "
          f"{state['store'].count() if state['store'] else 0} | LLM: {provider()}")
    yield


app = FastAPI(
    title=f"{SITE_NAME} API",
    lifespan=lifespan,
    docs_url="/api/docs" if EXPOSE_DOCS else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if EXPOSE_DOCS else None,
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST"],
                   allow_headers=["*"])


def _content_security_policy() -> str:
    """El sitio solo carga sus propios scripts; estilos y fuentes propios o de Google Fonts,
    e imágenes propias o del CDN de cartas. Así, aunque un dato externo trajera HTML malicioso,
    el navegador no ejecutaría scripts ajenos ni enviaría datos a otros dominios."""
    image_sources = {"'self'", "data:", REMOTE_IMAGE_BASE}
    if IMAGE_BASE_URL.startswith(("http://", "https://")):
        parts = urlsplit(IMAGE_BASE_URL)
        image_sources.add(f"{parts.scheme}://{parts.netloc}")
    return "; ".join([
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src " + " ".join(sorted(image_sources)),
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ])


CSP = _content_security_policy()
# La documentación interactiva (Swagger UI) carga sus recursos desde un CDN, por eso queda fuera de la CSP.
_CSP_EXEMPT = ("/api/docs", "/api/openapi.json")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    if not request.url.path.startswith(_CSP_EXEMPT):
        response.headers.setdefault("Content-Security-Policy", CSP)
    if request.url.path.startswith("/api/") and request.method == "GET" and response.status_code == 200:
        response.headers.setdefault("Cache-Control", "public, max-age=300")
    return response


def catalog() -> Catalog:
    cat = state["catalog"]
    if cat.count() == 0:
        raise HTTPException(503, "El catálogo aún no se ha cargado. Ejecuta `python -m src.ingest`.")
    return cat


# --- rate limit simple en memoria (por IP + tope global) --------------------
_hits: dict[str, deque] = defaultdict(deque)
_global_hits: deque = deque()
_hits_lock = Lock()
_MAX_TRACKED_CLIENTS = 50_000
_WINDOW_SECONDS = 60


def client_ip(request: Request) -> str:
    """Identificador del cliente para el límite de consultas.

    Se usa la IP que entrega el servidor (uvicorn), que solo acepta X-Forwarded-For cuando la
    conexión viene de un proxy de confianza (FORWARDED_ALLOW_IPS, ver scripts/start.sh). La
    cabecera no se lee aquí: si la app queda expuesta sin proxy, un cliente podría inventarla
    para saltarse el límite. Las direcciones IPv6 se agrupan por su red /64, porque un mismo
    cliente dispone de millones de direcciones dentro de ella.
    """
    host = request.client.host if request.client else "?"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host
    if ip.version == 6:
        if ip.ipv4_mapped:
            return str(ip.ipv4_mapped)
        return f"{ipaddress.ip_network(f'{ip}/64', strict=False).network_address}/64"
    return str(ip)


def _too_many(message: str) -> HTTPException:
    return HTTPException(429, message, headers={"Retry-After": str(_WINDOW_SECONDS)})


def check_rate_limit(request: Request):
    if CHAT_RATE_LIMIT_PER_MIN <= 0 and CHAT_GLOBAL_LIMIT_PER_MIN <= 0:
        return
    ip, now = client_ip(request), time.time()
    with _hits_lock:
        if CHAT_RATE_LIMIT_PER_MIN > 0:
            if len(_hits) > _MAX_TRACKED_CLIENTS:
                # acota la memoria: descarta los clientes sin consultas recientes
                for key in [k for k, v in _hits.items() if not v or now - v[-1] > _WINDOW_SECONDS]:
                    del _hits[key]
            q = _hits[ip]
            while q and now - q[0] > _WINDOW_SECONDS:
                q.popleft()
            if len(q) >= CHAT_RATE_LIMIT_PER_MIN:
                raise _too_many("Demasiadas consultas seguidas. Espera un minuto e inténtalo de nuevo.")
        if CHAT_GLOBAL_LIMIT_PER_MIN > 0:
            # tope total del asistente: protege la cuota del LLM aunque el abuso venga de muchas IP
            while _global_hits and now - _global_hits[0] > _WINDOW_SECONDS:
                _global_hits.popleft()
            if len(_global_hits) >= CHAT_GLOBAL_LIMIT_PER_MIN:
                raise _too_many("El asistente está recibiendo muchas consultas. Inténtalo de nuevo en un minuto.")
            _global_hits.append(now)
        if CHAT_RATE_LIMIT_PER_MIN > 0:
            _hits[ip].append(now)


# --- endpoints -------------------------------------------------------------
@app.get("/api/health")
def health():
    cat: Catalog = state["catalog"]
    store = state.get("store")
    return {
        "status": "ok",
        "cards": cat.count(),
        "vectors": store.count() if store else 0,
        "llm": {"provider": provider(), "model": model_name() if llm_available() else None},
        "image_base": IMAGE_BASE_URL,
    }


@app.get("/api/meta")
def meta():
    cat = catalog()
    sets = cat.list_sets()
    return {"site_name": SITE_NAME, "card_count": cat.count(), "set_count": len(sets),
            "filters": state.get("filters") or cat.filter_options(), "llm": llm_available(),
            "latest_set": sets[0] if sets else None}


@app.get("/api/sets")
def sets():
    return {"data": catalog().list_sets()}


@app.get("/api/cards")
def cards(
    q: str | None = Query(None, max_length=200),
    set: str | None = Query(None, alias="set"),
    series: str | None = None,
    type: list[str] = Query(default=[]),
    supertype: str | None = None,
    subtype: str | None = None,
    rarity: str | None = None,
    min_hp: int | None = Query(None, ge=0, le=500),
    max_hp: int | None = Query(None, ge=0, le=500),
    standard: bool = False,
    sort: str = "newest",
    page: int = Query(1, ge=1, le=2000),
    page_size: int = Query(36, ge=1, le=120),
):
    items, total = catalog().search(
        q=q, set_id=set, series=series, types=type, supertype=supertype, subtype=subtype,
        rarity=rarity, min_hp=min_hp, max_hp=max_hp, standard=standard or None,
        sort=sort, page=page, page_size=page_size,
    )
    return {"data": items, "total": total, "page": page, "page_size": page_size}


@app.get("/api/cards/{card_id}")
def card_detail(card_id: str):
    card = catalog().get_card(card_id)
    if not card:
        raise HTTPException(404, "Carta no encontrada")
    others, _ = catalog().search(name_exact=card["name"], sort="newest", page_size=24)
    card["printings"] = [o for o in others if o["id"] != card_id]
    return card


@app.get("/api/cards/{card_id}/price")
def card_price(card_id: str):
    if not catalog().get_card(card_id):
        raise HTTPException(404, "Carta no encontrada")
    price = get_card_price(card_id)
    if price is None:
        return JSONResponse({"available": False}, headers={"Cache-Control": "no-store"})
    return {"available": True, **price}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=600)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)


@app.post("/api/chat")
def chat(body: ChatRequest, request: Request):
    check_rate_limit(request)
    history = [m.model_dump() for m in body.history]
    return handle_query(body.message.strip(), catalog(), state.get("store"), history=history)


# --- sitio estático ----------------------------------------------------------
if IMAGES_DIR.is_dir():
    app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
@app.get("/carta/{_card_id}", include_in_schema=False)
@app.get("/set/", include_in_schema=False)
@app.get("/set/{_set_id}", include_in_schema=False)
@app.get("/asistente", include_in_schema=False)
def index(_card_id: str | None = None, _set_id: str | None = None):
    return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/favicon.svg", include_in_schema=False)
def favicon():
    return FileResponse(WEB_DIR / "favicon.svg")


@app.get("/robots.txt", include_in_schema=False)
def robots():
    return FileResponse(WEB_DIR / "robots.txt")
