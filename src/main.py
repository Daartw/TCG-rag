"""
Punto de entrada por consola del asistente.

Uso:
    python -m src.main
"""
from src.agent import handle_query
from src.vector_store import VectorStore


def main():
    print("Asistente Pokemon TCG - Evolving Skies")
    print("Escribe 'salir' para terminar.\n")

    store = VectorStore()

    while True:
        query = input("Tu consulta: ").strip()
        if query.lower() in {"salir", "exit", "quit"}:
            break
        if not query:
            continue

        respuesta = handle_query(query, store)
        print(f"\nAsistente: {respuesta}\n")


if __name__ == "__main__":
    main()
