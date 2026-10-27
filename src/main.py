"""
Punto de entrada por consola del asistente.

Uso:
    python -m src.main
"""
from src.agent import handle_query
from src.catalog import Catalog
from src.vector_store import VectorStore


def main():
    print("Asistente Pokémon TCG — catálogo completo")
    print("Escribe 'salir' para terminar.\n")

    catalog = Catalog()
    if catalog.count() == 0:
        print("El catálogo está vacío. Ejecuta primero: python -m src.ingest")
        return
    store = VectorStore()
    history: list[dict] = []

    while True:
        query = input("Tu consulta: ").strip()
        if query.lower() in {"salir", "exit", "quit"}:
            break
        if not query:
            continue

        result = handle_query(query, catalog, store, history=history)
        print(f"\nAsistente: {result['answer']}\n")
        history += [{"role": "user", "content": query}, {"role": "assistant", "content": result["answer"]}]


if __name__ == "__main__":
    main()
