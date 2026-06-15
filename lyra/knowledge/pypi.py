import requests


def search(query: str) -> list[dict]:
    """Busca en PyPI por descripción usando la API de búsqueda."""
    try:
        response = requests.get(
            "https://pypi.org/search/",
            params={"q": query},
            headers={"Accept": "application/json"},
            timeout=5,
        )
        # PyPI no tiene API JSON de búsqueda oficial, usamos simple API
        response = requests.get(
            f"https://pypi.org/pypi/{query}/json",
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            info = data["info"]
            return [{
                "name": info["name"],
                "version": info["version"],
                "description": info["summary"],
                "install": f"pip install {info['name']}",
            }]
    except Exception:
        pass
    return []


def search_many(queries: list[str]) -> list[dict]:
    results = []
    for q in queries:
        results.extend(search(q))
    return results
