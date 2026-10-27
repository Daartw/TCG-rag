"""
Catálogo estructurado de cartas en SQLite (con índice de texto completo FTS5).

Complementa a la base vectorial: SQLite resuelve filtros exactos (set, tipo,
HP, rareza, legalidad), búsquedas por nombre y la navegación paginada de la
web; Chroma resuelve la similitud semántica para el RAG.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import unicodedata
from pathlib import Path

from src.config import CATALOG_DB_PATH, IMAGE_BASE_URL, REMOTE_IMAGE_BASE

SCHEMA = """
CREATE TABLE IF NOT EXISTS sets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    series TEXT,
    printed_total INTEGER,
    total INTEGER,
    release_date TEXT,
    ptcgo_code TEXT,
    legal_standard INTEGER,
    legal_expanded INTEGER,
    symbol TEXT,
    logo TEXT
);
CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_norm TEXT NOT NULL,
    supertype TEXT,
    subtypes TEXT,
    hp INTEGER,
    types TEXT,
    set_id TEXT NOT NULL REFERENCES sets(id),
    number TEXT,
    number_sort INTEGER,
    rarity TEXT,
    artist TEXT,
    regulation_mark TEXT,
    legal_standard INTEGER,
    legal_expanded INTEGER,
    image_small TEXT,
    image_large TEXT,
    release_date TEXT,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cards_set ON cards(set_id);
CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name_norm);
CREATE INDEX IF NOT EXISTS idx_cards_release ON cards(release_date);
CREATE VIRTUAL TABLE IF NOT EXISTS cards_fts USING fts5(
    id UNINDEXED, name, body, set_name, artist,
    tokenize = 'unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

SORTS = {
    "newest": "c.release_date DESC, c.set_id, c.number_sort, c.number",
    "oldest": "c.release_date ASC, c.set_id, c.number_sort, c.number",
    "name": "c.name_norm ASC, c.release_date DESC",
    "hp": "c.hp DESC NULLS LAST, c.name_norm",
    "number": "c.number_sort, c.number",
}


def normalize(text: str) -> str:
    """minúsculas, sin tildes ni signos: 'Pokémon-ex' -> 'pokemon ex'."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = text.replace("’", "'")
    return re.sub(r"[^a-z0-9'&]+", " ", text).strip()


def card_body_text(card: dict) -> str:
    """Texto de reglas, habilidades y ataques (para FTS y embeddings)."""
    parts = []
    for ability in card.get("abilities") or []:
        parts.append(f"{ability.get('type', 'Ability')} {ability.get('name')}: {ability.get('text')}")
    for attack in card.get("attacks") or []:
        parts.append(f"{attack.get('name')} {attack.get('damage') or ''}: {attack.get('text') or ''}")
    parts.extend(card.get("rules") or [])
    if card.get("flavorText"):
        parts.append(card["flavorText"])
    return "\n".join(p for p in parts if p)


def _number_sort(number: str | None) -> int:
    match = re.search(r"\d+", number or "")
    return int(match.group()) if match else 99999


def _hp(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def rewrite_image(url: str | None) -> str | None:
    if url and IMAGE_BASE_URL != REMOTE_IMAGE_BASE:
        return url.replace(REMOTE_IMAGE_BASE, IMAGE_BASE_URL, 1)
    return url


def _fts_query(text: str) -> str | None:
    tokens = [t for t in normalize(text).replace("'", " ").split() if t]
    if not tokens:
        return None
    return " ".join(f'"{t}"*' for t in tokens[:12])


class Catalog:
    def __init__(self, path: Path | str = CATALOG_DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._names: dict[str, str] | None = None

    # -- conexión (una por hilo; FastAPI usa un pool de hilos) ---------------
    @property
    def conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.executescript(SCHEMA)
            self._local.conn = conn
        return conn

    # -- escritura ---------------------------------------------------------
    def rebuild(self, sets: list[dict], cards_by_set: dict[str, list[dict]]) -> int:
        conn = self.conn
        with conn:
            conn.execute("DELETE FROM cards_fts")
            conn.execute("DELETE FROM cards")
            conn.execute("DELETE FROM sets")
            set_index = {}
            for s in sets:
                if s["id"] not in cards_by_set:
                    continue
                set_index[s["id"]] = s
                legal = s.get("legalities") or {}
                conn.execute(
                    "INSERT INTO sets VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        s["id"], s["name"], s.get("series"), s.get("printedTotal"),
                        s.get("total"), (s.get("releaseDate") or "").replace("/", "-"),
                        s.get("ptcgoCode"), int(legal.get("standard") == "Legal"),
                        int(legal.get("expanded") == "Legal"),
                        (s.get("images") or {}).get("symbol"), (s.get("images") or {}).get("logo"),
                    ),
                )
            count = 0
            for set_id, cards in cards_by_set.items():
                s = set_index.get(set_id)
                if s is None:
                    continue
                release = (s.get("releaseDate") or "").replace("/", "-")
                for card in cards:
                    card = {**card, "set": {k: v for k, v in s.items() if k != "legalities"}}
                    legal = card.get("legalities") or {}
                    images = card.get("images") or {}
                    conn.execute(
                        "INSERT OR REPLACE INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            card["id"], card["name"], normalize(card["name"]),
                            card.get("supertype"), json.dumps(card.get("subtypes") or []),
                            _hp(card.get("hp")), json.dumps(card.get("types") or []),
                            set_id, card.get("number"), _number_sort(card.get("number")),
                            card.get("rarity"), card.get("artist"), card.get("regulationMark"),
                            int(legal.get("standard") == "Legal"),
                            int(legal.get("expanded") == "Legal"),
                            images.get("small"), images.get("large"), release,
                            json.dumps(card, ensure_ascii=False),
                        ),
                    )
                    conn.execute(
                        "INSERT INTO cards_fts VALUES (?,?,?,?,?)",
                        (card["id"], card["name"], card_body_text(card), s["name"], card.get("artist") or ""),
                    )
                    count += 1
            conn.execute("INSERT OR REPLACE INTO meta VALUES ('card_count', ?)", (str(count),))
        self._names = None
        return count

    def set_meta(self, key: str, value: str):
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    # -- lectura -----------------------------------------------------------
    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]

    @staticmethod
    def _summary(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "name": row["name"],
            "supertype": row["supertype"],
            "subtypes": json.loads(row["subtypes"] or "[]"),
            "hp": row["hp"],
            "types": json.loads(row["types"] or "[]"),
            "number": row["number"],
            "rarity": row["rarity"],
            "artist": row["artist"],
            "regulation_mark": row["regulation_mark"],
            "legal_standard": bool(row["legal_standard"]),
            "legal_expanded": bool(row["legal_expanded"]),
            "release_date": row["release_date"],
            "set": {"id": row["set_id"], "name": row["set_name"], "series": row["series"]},
            "images": {"small": rewrite_image(row["image_small"]), "large": rewrite_image(row["image_large"])},
        }

    _SELECT = (
        "SELECT c.*, s.name AS set_name, s.series AS series "
        "FROM cards c JOIN sets s ON s.id = c.set_id"
    )

    def get_card(self, card_id: str) -> dict | None:
        row = self.conn.execute(self._SELECT + " WHERE c.id = ?", (card_id,)).fetchone()
        if row is None:
            return None
        detail = self._summary(row)
        data = json.loads(row["data"])
        for key in ("abilities", "attacks", "weaknesses", "resistances", "retreatCost",
                    "rules", "flavorText", "evolvesFrom", "evolvesTo", "nationalPokedexNumbers",
                    "legalities", "ancientTrait"):
            if data.get(key):
                detail[key] = data[key]
        detail["set"] = {**detail["set"], **{
            k: data["set"].get(k) for k in ("printedTotal", "total", "releaseDate", "ptcgoCode", "images")
        }}
        return detail

    def get_cards(self, ids: list[str]) -> list[dict]:
        if not ids:
            return []
        marks = ",".join("?" * len(ids))
        rows = self.conn.execute(self._SELECT + f" WHERE c.id IN ({marks})", ids).fetchall()
        by_id = {r["id"]: self._summary(r) for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    def card_document(self, card_id: str) -> str | None:
        row = self.conn.execute("SELECT data FROM cards WHERE id = ?", (card_id,)).fetchone()
        return card_to_document(json.loads(row["data"])) if row else None

    def search(
        self,
        q: str | None = None,
        set_id: str | None = None,
        series: str | None = None,
        types: list[str] | None = None,
        supertype: str | None = None,
        subtype: str | None = None,
        rarity: str | None = None,
        min_hp: int | None = None,
        max_hp: int | None = None,
        standard: bool | None = None,
        name_exact: str | None = None,
        sort: str = "newest",
        page: int = 1,
        page_size: int = 36,
    ) -> tuple[list[dict], int]:
        where, params = [], []
        if q:
            fts = _fts_query(q)
            if fts:
                where.append("c.id IN (SELECT id FROM cards_fts WHERE cards_fts MATCH ?)")
                params.append(fts)
        if name_exact:
            where.append("c.name_norm = ?")
            params.append(normalize(name_exact))
        if set_id:
            where.append("c.set_id = ?")
            params.append(set_id)
        if series:
            where.append("s.series = ?")
            params.append(series)
        for t in types or []:
            where.append("c.types LIKE ?")
            params.append(f'%"{t}"%')
        if supertype:
            where.append("c.supertype = ?")
            params.append(supertype)
        if subtype:
            where.append("c.subtypes LIKE ?")
            params.append(f'%"{subtype}"%')
        if rarity:
            where.append("c.rarity = ?")
            params.append(rarity)
        if min_hp is not None:
            where.append("c.hp >= ?")
            params.append(min_hp)
        if max_hp is not None:
            where.append("c.hp <= ?")
            params.append(max_hp)
        if standard:
            where.append("c.legal_standard = 1")
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        base = "FROM cards c JOIN sets s ON s.id = c.set_id" + clause
        total = self.conn.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
        order = SORTS.get(sort, SORTS["newest"])
        page_size = max(1, min(page_size, 120))
        offset = (max(page, 1) - 1) * page_size
        rows = self.conn.execute(
            f"SELECT c.*, s.name AS set_name, s.series AS series {base} ORDER BY {order} LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()
        return [self._summary(r) for r in rows], total

    def list_sets(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT s.*, (SELECT COUNT(*) FROM cards c WHERE c.set_id = s.id) AS card_count "
            "FROM sets s ORDER BY s.release_date DESC"
        ).fetchall()
        return [
            {
                "id": r["id"], "name": r["name"], "series": r["series"],
                "printed_total": r["printed_total"], "total": r["total"],
                "card_count": r["card_count"], "release_date": r["release_date"],
                "ptcgo_code": r["ptcgo_code"], "legal_standard": bool(r["legal_standard"]),
                "legal_expanded": bool(r["legal_expanded"]),
                "images": {"symbol": rewrite_image(r["symbol"]), "logo": rewrite_image(r["logo"])},
            }
            for r in rows
        ]

    def filter_options(self) -> dict:
        def distinct(sql):
            return [r[0] for r in self.conn.execute(sql).fetchall() if r[0]]

        types, subtypes = set(), set()
        for row in self.conn.execute("SELECT DISTINCT types, subtypes FROM cards"):
            types.update(json.loads(row["types"] or "[]"))
            subtypes.update(json.loads(row["subtypes"] or "[]"))
        return {
            "types": sorted(types),
            "subtypes": sorted(subtypes),
            "supertypes": distinct("SELECT DISTINCT supertype FROM cards ORDER BY 1"),
            "rarities": distinct("SELECT DISTINCT rarity FROM cards ORDER BY 1"),
            "series": distinct("SELECT series FROM sets GROUP BY series ORDER BY MAX(release_date) DESC"),
        }

    def name_index(self) -> dict[str, str]:
        """{nombre normalizado: nombre original} de todas las cartas (para detectar nombres)."""
        if self._names is None:
            self._names = {
                r["name_norm"]: r["name"]
                for r in self.conn.execute("SELECT DISTINCT name_norm, name FROM cards")
            }
        return self._names

    def set_name_index(self) -> dict[str, str]:
        return {normalize(r["name"]): r["id"] for r in self.conn.execute("SELECT id, name FROM sets")}


def card_to_document(card: dict) -> str:
    """Convierte una carta en un documento de texto autocontenido (1 chunk = 1 carta)."""
    s = card.get("set") or {}
    lines = [
        f"Nombre: {card.get('name')}",
        f"Categoría: {card.get('supertype')} ({', '.join(card.get('subtypes') or []) or 'N/A'})",
        f"Set: {s.get('name')} ({s.get('series')}, {s.get('releaseDate')}) #{card.get('number')}",
        f"Rareza: {card.get('rarity', 'N/A')}",
    ]
    if card.get("types"):
        lines.append(f"Tipo(s): {', '.join(card['types'])}")
    if card.get("hp"):
        lines.append(f"HP: {card['hp']}")
    if card.get("evolvesFrom"):
        lines.append(f"Evoluciona de: {card['evolvesFrom']}")
    for ability in card.get("abilities") or []:
        lines.append(f"{ability.get('type', 'Habilidad')} ({ability.get('name')}): {ability.get('text')}")
    for attack in card.get("attacks") or []:
        cost = "".join(c[0] for c in attack.get("cost") or []) or "0"
        lines.append(
            f"Ataque ({attack.get('name')}, costo {cost}, daño {attack.get('damage') or '-'}): "
            f"{attack.get('text') or ''}".rstrip()
        )
    for rule in card.get("rules") or []:
        lines.append(f"Regla/Efecto: {rule}")
    if card.get("weaknesses"):
        lines.append("Debilidad: " + ", ".join(f"{w['type']} {w['value']}" for w in card["weaknesses"]))
    if card.get("resistances"):
        lines.append("Resistencia: " + ", ".join(f"{r['type']} {r['value']}" for r in card["resistances"]))
    if card.get("convertedRetreatCost") is not None:
        lines.append(f"Retirada: {card['convertedRetreatCost']}")
    legal = card.get("legalities") or {}
    if legal:
        lines.append("Legalidad: " + ", ".join(f"{k} {v}" for k, v in legal.items()))
    return "\n".join(lines)
