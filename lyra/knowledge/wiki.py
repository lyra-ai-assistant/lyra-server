import requests

_ARCH_WIKI_API = "https://wiki.archlinux.org/api.php"
_GENTOO_WIKI_API = "https://wiki.gentoo.org/api.php"


def _search_mediawiki(api_url: str, query: str) -> str | None:
    try:
        # Buscar páginas relevantes
        search_resp = requests.get(
            api_url,
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": 1,
                "format": "json",
            },
            timeout=5,
        )
        results = search_resp.json().get("query", {}).get("search", [])
        if not results:
            return None

        title = results[0]["title"]

        # Obtener extracto de la página
        extract_resp = requests.get(
            api_url,
            params={
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "titles": title,
                "format": "json",
            },
            timeout=5,
        )
        pages = extract_resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            extract = page.get("extract", "")
            # Truncar a 500 chars para no saturar el contexto
            return f"[{title}]: {extract[:500]}"
    except Exception:
        pass
    return None


def search(query: str, distro: str | None = None) -> str | None:
    """Busca en la wiki apropiada según la distro."""
    distro_lower = (distro or "").lower()

    if "arch" in distro_lower or "cachy" in distro_lower or "manjaro" in distro_lower:
        return _search_mediawiki(_ARCH_WIKI_API, query)
    elif "gentoo" in distro_lower:
        return _search_mediawiki(_GENTOO_WIKI_API, query)
    else:
        # Arch Wiki es la más completa para Linux en general
        return _search_mediawiki(_ARCH_WIKI_API, query)
