"""
Obtención del catálogo completo de cartas.

Fuente: https://github.com/PokemonTCG/pokemon-tcg-data, el volcado JSON oficial
del proyecto pokemontcg.io. Contiene todas las cartas en inglés de todos los
sets (Base Set → Mega Evolution), con ataques, habilidades, reglas,
legalidades y URLs de imágenes en baja y alta resolución.

Se prefiere el volcado de GitHub frente a paginar la API REST porque es
mucho más rápido (un único archivo) y no sufre límites de tasa ni errores 5xx.
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

import requests

from src.config import CARD_DATA_BRANCH, CARD_DATA_DIR, CARD_DATA_REPO, DATA_DIR

DEFAULT_SOURCE_DIR = DATA_DIR / "source" / "pokemon-tcg-data"


def _looks_valid(path: Path) -> bool:
    return (path / "sets" / "en.json").is_file() and (path / "cards" / "en").is_dir()


def _git_clone(dest: Path) -> bool:
    if shutil.which("git") is None:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Clonando {CARD_DATA_REPO} ...")
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", CARD_DATA_BRANCH, CARD_DATA_REPO, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  git clone falló: {result.stderr.strip()[:300]}")
        return False
    return _looks_valid(dest)


def _download_tarball(dest: Path) -> bool:
    repo_path = CARD_DATA_REPO.rstrip("/").removeprefix("https://github.com/")
    url = f"https://codeload.github.com/{repo_path}/tar.gz/refs/heads/{CARD_DATA_BRANCH}"
    print(f"Descargando {url} ...")
    try:
        response = requests.get(url, timeout=300)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"  Descarga falló: {exc}")
        return False

    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as tar:
        for member in tar.getmembers():
            # Quita el primer componente ("pokemon-tcg-data-master/") y evita rutas raras
            parts = Path(member.name).parts[1:]
            if not parts or ".." in parts or not member.isfile():
                continue
            if parts[0] not in {"sets", "cards"}:
                continue
            target = dest.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            extracted = tar.extractfile(member)
            if extracted:
                target.write_bytes(extracted.read())
    return _looks_valid(dest)


def ensure_source_dir(refresh: bool = False) -> Path:
    """Devuelve la carpeta con el volcado de datos, descargándolo si hace falta."""
    if CARD_DATA_DIR:
        path = Path(CARD_DATA_DIR)
        if not _looks_valid(path):
            raise RuntimeError(f"CARD_DATA_DIR={path} no contiene sets/en.json y cards/en/")
        return path

    dest = DEFAULT_SOURCE_DIR
    if refresh and dest.exists():
        shutil.rmtree(dest)
    if _looks_valid(dest):
        return dest
    if dest.exists():
        shutil.rmtree(dest)

    if _git_clone(dest) or _download_tarball(dest):
        return dest
    raise RuntimeError(
        "No se pudo obtener el catálogo de cartas. Clona manualmente "
        f"{CARD_DATA_REPO} y define CARD_DATA_DIR con su ruta."
    )


def load_sets(source: Path) -> list[dict]:
    sets = json.loads((source / "sets" / "en.json").read_text(encoding="utf-8"))
    sets.sort(key=lambda s: s.get("releaseDate", ""))
    return sets


def load_cards(source: Path, set_ids: list[str] | None = None) -> dict[str, list[dict]]:
    """Devuelve {set_id: [cartas]} leyendo cards/en/<set_id>.json."""
    result: dict[str, list[dict]] = {}
    for path in sorted((source / "cards" / "en").glob("*.json")):
        set_id = path.stem
        if set_ids and set_id not in set_ids:
            continue
        result[set_id] = json.loads(path.read_text(encoding="utf-8"))
    return result
