import requests


def search(query: str) -> list[dict]:
    try:
        response = requests.get(
            "https://crates.io/api/v1/crates",
            params={"q": query, "per_page": 5},
            headers={"User-Agent": "lyra-assistant"},
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            return [
                {
                    "name": c["name"],
                    "version": c["newest_version"],
                    "description": c.get("description", ""),
                    "install": f"cargo install {c['name']}",
                }
                for c in data.get("crates", [])
            ]
    except Exception:
        pass
    return []
