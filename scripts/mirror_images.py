"""
Espeja las imágenes de cartas y sets en tu propio servidor (opcional).

Por defecto el sitio usa el CDN de images.pokemontcg.io. Si prefieres no
depender de él, descarga las imágenes y define IMAGE_BASE_URL=/images.

Tamaño aproximado: miniaturas ~1 GB · alta resolución ~12-15 GB.

Uso:
    python scripts/mirror_images.py                 # miniaturas + logos de sets
    python scripts/mirror_images.py --large         # también alta resolución
    python scripts/mirror_images.py --sets sv1,sv2  # solo algunos sets
    # con Docker:
    docker compose exec app python scripts/mirror_images.py
Es reanudable: omite los archivos que ya existen.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import CATALOG_DB_PATH, IMAGES_DIR, REMOTE_IMAGE_BASE  # noqa: E402


def collect_urls(large: bool, set_ids: list[str] | None) -> list[str]:
    conn = sqlite3.connect(CATALOG_DB_PATH)
    urls = []
    where = ""
    params: list = []
    if set_ids:
        where = f" WHERE set_id IN ({','.join('?' * len(set_ids))})"
        params = set_ids
    for small, big in conn.execute(f"SELECT image_small, image_large FROM cards{where}", params):
        urls.append(small)
        if large:
            urls.append(big)
    sets_where = where.replace("set_id", "id")
    for symbol, logo in conn.execute(f"SELECT symbol, logo FROM sets{sets_where}", params):
        urls += [symbol, logo]
    return [u for u in urls if u and u.startswith(REMOTE_IMAGE_BASE)]


def download(session: requests.Session, url: str) -> str:
    target = IMAGES_DIR / url.removeprefix(REMOTE_IMAGE_BASE).lstrip("/")
    if target.exists() and target.stat().st_size > 0:
        return "skip"
    target.parent.mkdir(parents=True, exist_ok=True)
    response = session.get(url, timeout=60)
    if response.status_code != 200:
        return f"error {response.status_code}"
    tmp = target.with_suffix(target.suffix + ".part")
    tmp.write_bytes(response.content)
    tmp.replace(target)
    return "ok"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--large", action="store_true", help="incluir imágenes en alta resolución")
    parser.add_argument("--sets", help="ids de sets separados por coma")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    urls = collect_urls(args.large, args.sets.split(",") if args.sets else None)
    print(f"{len(urls)} imágenes -> {IMAGES_DIR}")
    stats: dict[str, int] = {}
    with requests.Session() as session, ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(download, session, u) for u in urls]
        for i, future in enumerate(as_completed(futures), 1):
            try:
                result = future.result()
            except requests.RequestException as exc:
                result = f"error {type(exc).__name__}"
            stats[result] = stats.get(result, 0) + 1
            if i % 500 == 0:
                print(f"  {i}/{len(urls)} {json.dumps(stats)}", flush=True)
    print("Listo:", json.dumps(stats))
    print("Ahora define IMAGE_BASE_URL=/images y reinicia el servidor.")


if __name__ == "__main__":
    main()
