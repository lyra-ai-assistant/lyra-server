import requests


def search(query: str) -> list[dict]:
    try:
        response = requests.get(
            "https://registry.npmjs.org/-/v1/search",
            params={"text": query, "size": 5},
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            return [
                {
                    "name": obj["package"]["name"],
                    "version": obj["package"]["version"],
                    "description": obj["package"].get("description", ""),
                    "install": f"npm install -g {obj['package']['name']}",
                }
                for obj in data.get("objects", [])
            ]
    except Exception:
        pass
    return []
