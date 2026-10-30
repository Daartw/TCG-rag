"""Pruebas del intérprete de consultas (sin LLM): nombres, tipos, HP, sets y precios."""
import pytest

from src.query_parser import parse_query


@pytest.mark.parametrize(
    "query, expected",
    [
        ("cartas de tipo fuego con más de 200 HP", {"types": ["Fire"], "min_hp": 200, "supertype": "Pokémon"}),
        ("Pokémon de agua con HP < 100", {"types": ["Water"], "max_hp": 100, "supertype": "Pokémon"}),
        ("partidarios del formato estándar", {"standard": True, "subtype": "Supporter", "supertype": "Trainer"}),
        ("cartas dragón de Evolving Skies", {"types": ["Dragon"], "supertype": "Pokémon", "set_id": "swsh7"}),
        ("cartas del set 151 con 60 hp o más", {"min_hp": 60, "supertype": "Pokémon", "set_id": "sv3pt5"}),
        ("entrenadores", {"supertype": "Trainer"}),
        ("cartas de energía", {"supertype": "Energy"}),
    ],
)
def test_filters(catalog, query, expected):
    assert parse_query(query, catalog).filters == expected


def test_card_names_prefer_longest_match(catalog):
    assert parse_query("Rayquaza VMAX", catalog).names == ["Rayquaza VMAX"]
    assert parse_query('"Umbreon V" precio', catalog).names == ["Umbreon V"]


def test_pokemon_name_is_not_mistaken_for_a_type(catalog):
    parsed = parse_query("Dragonite V", catalog)
    assert parsed.names == ["Dragonite V"]
    assert "types" not in parsed.filters


def test_normal_only_counts_as_type_after_tipo(catalog):
    assert parse_query("tipo normal", catalog).filters["types"] == ["Colorless"]
    assert parse_query("carta normal", catalog).filters == {}


@pytest.mark.parametrize("query", ["¿cuánto vale Umbreon VMAX?", "precio de Pikachu", "Charizard ex price", "Pikachu $"])
def test_detects_price_questions(catalog, query):
    assert parse_query(query, catalog).wants_price


def test_plain_search_is_not_a_price_question(catalog):
    assert not parse_query("cartas de tipo planta", catalog).wants_price
