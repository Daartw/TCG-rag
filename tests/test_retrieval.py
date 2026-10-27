"""Pruebas del catálogo, la interpretación de consultas y la recuperación."""
from src.query_parser import parse_query
from src.rag_pipeline import retrieve


def test_catalog_loaded(catalog, store):
    assert catalog.count() == 35
    assert store.count() == 35
    assert {s["id"] for s in catalog.list_sets()} == {"swsh7", "sv3pt5"}


def test_card_has_images_and_details(catalog):
    card = catalog.get_card("swsh7-215")
    assert card["name"] == "Umbreon VMAX"
    assert card["images"]["small"].endswith("/swsh7/215.png")
    assert card["attacks"] and card["set"]["name"] == "Evolving Skies"


def test_search_filters(catalog):
    items, total = catalog.search(types=["Dragon"], min_hp=300)
    assert total > 0
    assert all("Dragon" in c["types"] and c["hp"] >= 300 for c in items)
    items, _ = catalog.search(q="rayquaza")
    assert all("Rayquaza" in c["name"] for c in items)


def test_vector_search_respects_top_k_and_filters(store):
    hits = store.search("Rayquaza VMAX", top_k=2)
    assert 0 < len(hits) <= 2
    hits = store.search("dragón", top_k=10, filters={"types": ["Dragon"], "min_hp": 200})
    assert hits and all(h["metadata"]["hp"] >= 200 and h["metadata"].get("type_Dragon") for h in hits)


def test_parse_query_spanish(catalog):
    p = parse_query("Busco una carta de tipo Dragón con HP mayor a 200 que tenga una habilidad de curación", catalog)
    assert p.filters["types"] == ["Dragon"]
    assert p.filters["min_hp"] == 200
    assert not p.wants_price

    p = parse_query("¿Cuál es el precio actual de Umbreon VMAX Alt Art?", catalog)
    assert p.wants_price and p.names[0] == "Umbreon VMAX"

    p = parse_query("cartas de fuego de Evolving Skies", catalog)
    assert p.filters["set_id"] == "swsh7" and p.filters["types"] == ["Fire"]

    p = parse_query("Charizard ex de 151", catalog)
    assert p.filters["set_id"] == "sv3pt5" and p.names == ["Charizard ex"]


def test_retrieve_includes_named_card(catalog, store):
    p = parse_query("Recomiéndame 3 cartas que complementen a Rayquaza VMAX", catalog)
    ids = retrieve(p, catalog, store)
    names = [c["name"] for c in catalog.get_cards(ids)]
    assert names[0] == "Rayquaza VMAX"
    assert len(ids) == len(set(ids))
