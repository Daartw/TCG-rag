"""
Interpretación ligera de la consulta del usuario (español o inglés), sin LLM:

- detecta nombres de cartas conocidos ("Rayquaza VMAX", "Charizard ex"...)
- extrae filtros: tipo, HP mínimo/máximo, categoría, set, formato estándar
- detecta si la consulta pide un precio

Los filtros se aplican luego tanto a Chroma como a SQLite.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.catalog import Catalog, normalize

TYPE_WORDS = {
    "Fire": ["fuego", "fire", "llamas"],
    "Water": ["agua", "water"],
    "Grass": ["planta", "hierba", "grass", "bicho"],
    "Lightning": ["electrico", "electrica", "electricos", "rayo", "lightning", "electric"],
    "Psychic": ["psiquico", "psiquica", "psiquicos", "psychic"],
    "Fighting": ["lucha", "fighting", "luchador"],
    "Darkness": ["oscuro", "oscura", "siniestro", "siniestra", "darkness", "dark"],
    "Metal": ["metal", "acero", "steel"],
    "Dragon": ["dragon", "dragones"],
    "Fairy": ["hada", "fairy"],
    "Colorless": ["incoloro", "incolora", "colorless", "normal"],
}
_TYPE_LOOKUP = {w: t for t, words in TYPE_WORDS.items() for w in words}

PRICE_WORDS = [
    "precio", "precios", "cuesta", "cuestan", "vale", "valen", "valor", "cuanto",
    "cotiza", "price", "prices", "cost", "costs", "worth", "tcgplayer", "cardmarket",
]

STANDARD_WORDS = ["estandar", "standard", "formato estandar"]

SUBTYPE_WORDS = {
    "Supporter": ["partidario", "partidaria", "partidarios", "supporter", "supporters"],
    "Item": ["objeto", "objetos", "item", "items"],
    "Stadium": ["estadio", "estadios", "stadium", "stadiums"],
    "Pokémon Tool": ["herramienta", "herramientas", "tool", "tools"],
}

# Palabras comunes que coinciden con nombres de cartas pero casi nunca se
# refieren a la carta en sí.
NAME_STOPWORDS = {
    "carta", "cartas", "card", "cards", "pokemon", "energia", "energy", "tipo", "type",
    "ataque", "attack", "habilidad", "ability", "dano", "damage", "deck", "mazo",
    "best", "mejor", "mejores", "precio", "price", "trainer", "entrenador", "set",
    "rare", "rara", "basic", "basico", "stage", "fase", "heal", "draw", "search",
    "switch", "mega", "ex", "gx", "v", "vmax", "vstar", "the", "and", "with",
}

_HP_MIN = [
    r"(?:hp|ps|vida)\s*(?:mayor|mas|superior|sobre|de mas)\s*(?:a|de|que)?\s*(\d{2,3})",
    r"(?:mas|mayor|superior|over|more than|above)\s*(?:a|de|que|than)?\s*(\d{2,3})\s*(?:hp|ps)",
    r"(?:hp|ps)\s*(?:>=|>|=>)\s*(\d{2,3})",
    r"(?:al menos|minimo|at least)\s*(\d{2,3})\s*(?:hp|ps)",
    r"(\d{2,3})\s*(?:hp|ps)?\s*(?:o mas|or more|\+)",
]
_HP_MAX = [
    r"(?:hp|ps|vida)\s*(?:menor|menos|inferior|bajo|under)\s*(?:a|de|que|than)?\s*(\d{2,3})",
    r"(?:menos|menor|under|less than|below)\s*(?:a|de|que|than)?\s*(\d{2,3})\s*(?:hp|ps)",
    r"(?:hp|ps)\s*(?:<=|<|=<)\s*(\d{2,3})",
]


@dataclass
class ParsedQuery:
    text: str
    names: list[str] = field(default_factory=list)
    filters: dict = field(default_factory=dict)
    wants_price: bool = False

    @property
    def has_filters(self) -> bool:
        return any(v not in (None, [], False, "") for v in self.filters.values())


def _find_names(norm: str, names: dict[str, str]) -> list[str]:
    tokens = norm.split()
    found, used = [], set()
    # n-gramas de mayor a menor longitud: "rayquaza vmax" gana sobre "rayquaza"
    for size in range(6, 0, -1):
        for i in range(len(tokens) - size + 1):
            span = range(i, i + size)
            if any(j in used for j in span):
                continue
            gram = " ".join(tokens[i:i + size])
            if gram not in names:
                continue
            if size == 1 and (gram in NAME_STOPWORDS or len(gram) < 4 or gram.isdigit()):
                continue
            found.append(names[gram])
            used.update(span)
    return found


def parse_query(text: str, catalog: Catalog) -> ParsedQuery:
    norm = normalize(text)
    padded = f" {norm} "
    parsed = ParsedQuery(text=text)
    raw_lower = text.lower()

    parsed.wants_price = any(f" {w} " in padded for w in PRICE_WORDS) or "$" in text or "€" in text

    # Nombres de carta: primero lo que venga entre comillas, luego n-gramas
    quoted = re.findall(r'["“«]([^"”»]+)["”»]', text)
    names_index = catalog.name_index()
    for q in quoted:
        if normalize(q) in names_index:
            parsed.names.append(names_index[normalize(q)])
    for name in _find_names(norm, names_index):
        if name not in parsed.names:
            parsed.names.append(name)

    # Tipos (evitamos confundir con el nombre de la carta: "Dragonite" no es "dragon")
    types = []
    name_tokens = {tok for n in parsed.names for tok in normalize(n).split()}
    for token in norm.split():
        t = _TYPE_LOOKUP.get(token)
        if t and token not in name_tokens and t not in types:
            # "normal" solo cuenta como tipo si va precedido de "tipo"
            if token == "normal" and " tipo normal " not in padded:
                continue
            types.append(t)
    if types:
        parsed.filters["types"] = types

    hp_text = raw_to_ops(raw_lower, norm)
    for pattern in _HP_MIN:
        m = re.search(pattern, hp_text)
        if m:
            parsed.filters["min_hp"] = int(m.group(1))
            break
    for pattern in _HP_MAX:
        m = re.search(pattern, hp_text)
        if m:
            parsed.filters["max_hp"] = int(m.group(1))
            break

    if any(f" {w} " in padded for w in STANDARD_WORDS):
        parsed.filters["standard"] = True

    for subtype, words in SUBTYPE_WORDS.items():
        if any(f" {w} " in padded for w in words):
            parsed.filters["subtype"] = subtype
            parsed.filters["supertype"] = "Trainer"
            break
    if "supertype" not in parsed.filters:
        if re.search(r"\b(entrenador(es)?|trainers?)\b", norm):
            parsed.filters["supertype"] = "Trainer"
        elif re.search(r"\b(cartas? de energia|energy cards?)\b", norm):
            parsed.filters["supertype"] = "Energy"
        elif types or "min_hp" in parsed.filters or "max_hp" in parsed.filters:
            parsed.filters["supertype"] = "Pokémon"

    # Set mencionado por nombre ("Evolving Skies", "Paldea Evolved"...)
    best = None
    for set_norm, set_id in catalog.set_name_index().items():
        if set_norm.isdigit():
            # sets numéricos ("151"): que no sea un valor de HP
            if not re.search(rf"(?<!\d)\b{set_norm}\b(?!\s*(hp|ps))", norm) or re.search(
                    rf"(hp|ps|mas de|mayor a|menos de)\s*{set_norm}\b", norm):
                continue
        elif len(set_norm) < 6 or set_norm in _TYPE_LOOKUP or set_norm in NAME_STOPWORDS:
            continue
        if f" {set_norm} " in padded:
            if best is None or len(set_norm) > len(best[0]):
                best = (set_norm, set_id)
    if best:
        parsed.filters["set_id"] = best[1]
        # el nombre del set no es un nombre de carta
        parsed.names = [n for n in parsed.names if normalize(n) not in best[0]]

    return parsed


def raw_to_ops(raw_lower: str, norm: str) -> str:
    """normalize() elimina '>' y '<'; los reinsertamos para patrones como 'HP > 200'."""
    if any(op in raw_lower for op in (">", "<", "+")):
        text = raw_lower
        for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
            text = text.replace(a, b)
        text = re.sub(r"([<>]=?|=>|=<|\+)", r" \1 ", text)
        return re.sub(r"\s+", " ", text)
    return norm
