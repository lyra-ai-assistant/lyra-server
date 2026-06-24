"""
Knowledge resolver — orchestrates parallel searches across system repos,
ecosystem package registries, and distro wikis based on the user's profile.
"""

import shutil
from concurrent.futures import ThreadPoolExecutor

from lyra.util.profile import load_profile


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "que", "puedo", "como", "para", "instalar", "usar", "con",
    "un", "una", "el", "la", "los", "las", "en", "de", "a",
    "what", "can", "how", "to", "install", "use", "with", "the",
}

_DEV_KEYWORDS = {
    "library", "librería", "framework", "package", "module", "módulo",
    "api", "cli", "tool", "herramienta", "script", "bot", "server",
    "backend", "frontend", "web", "http", "json", "xml", "parse",
    "build", "compile", "test", "deploy",
}

_LIB_PREFIXES = ("python-", "perl-", "ruby-", "haskell-", "r-", "mingw-")

_LIB_SUFFIXES = ("-sdk", "-dev", "-devel", "-doc", "-debug", "-git")

_SKIP_DESC_WORDS = {
    "library", "libraries", "binding", "bindings",
    "driver", "drivers", "importer", "exporter",
    "header files", "development package",
    "filter for", "based on lib", "plugin for",
}


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _extract_keywords(query: str) -> list[str]:
    """Strip stopwords and short tokens from a query to get search terms."""
    words = [w.lower() for w in query.split() if len(w) > 2]
    return [w for w in words if w not in _STOPWORDS]


def _is_dev_query(query: str) -> bool:
    """Return True if the query is development-related (enables ecosystem searches)."""
    q = query.lower()
    return any(k in q for k in _DEV_KEYWORDS)


def _expand_search_terms(query: str) -> list[str]:
    """Use SLM to extract search terms from user's query."""
    try:
        from lyra.api.dependencies import generation_agent
        result = generation_agent._llm.create_chat_completion(
            messages=[{
                "role": "user",
                "content": (
                    f"Extract 2-3 short English search terms for finding Linux software "
                    f"that answers this query: '{query}'\n"
                    f"Reply with ONLY the terms separated by commas. No explanations."
                )
            }],
            max_tokens=20,
            temperature=0.1,
        )
        raw = result["choices"][0]["message"]["content"]
        terms = [t.strip().lower() for t in raw.split(",") if t.strip()]
        return terms[:3]
    except Exception:
        return _extract_keywords(query)


# ---------------------------------------------------------------------------
# Parallel execution
# ---------------------------------------------------------------------------

def _run_parallel(tasks: dict, timeout: int = 8) -> dict:
    """Run a dict of {key: callable} in parallel and return {key: result}."""
    results = {}
    with ThreadPoolExecutor(max_workers=max(len(tasks), 1)) as executor:
        futures = {key: executor.submit(fn) for key, fn in tasks.items()}
        for key, future in futures.items():
            try:
                results[key] = future.result(timeout=timeout)
            except Exception:
                results[key] = [] if key != "wiki" else None
    return results


# ---------------------------------------------------------------------------
# Per-source search wrappers
# ---------------------------------------------------------------------------

def _is_user_package(pkg: dict) -> bool:
    name = pkg["name"].lower()
    desc = pkg["description"].lower()

    if any(name.startswith(p) for p in _LIB_PREFIXES):
        return False
    if any(name.endswith(s) for s in _LIB_SUFFIXES):
        return False

    if (
        name.startswith("lib")
        and "-" in name
        and not name.startswith("libre")
    ):
        return False

    if any(phrase in desc for phrase in _SKIP_DESC_WORDS):
        return False

    return True


def _search_pacman_multi(terms: list[str]) -> list[dict]:
    from lyra.knowledge.pacman import search
    seen: set[str] = set()
    results = []
    for term in terms:
        for pkg in search(term):
            if pkg["name"] not in seen and _is_user_package(pkg):
                name_desc = (pkg["name"] + " " + pkg["description"]).lower()
                if any(t in name_desc for t in terms):
                    seen.add(pkg["name"])
                    results.append(pkg)
    return results[:8]


def _search_apt_multi(terms: list[str]) -> list[dict]:
    """Search apt-cache for each term, deduplicate, and filter by relevance."""
    from lyra.knowledge.apt import search
    seen: set[str] = set()
    results = []
    for term in terms:
        for pkg in search(term):
            if pkg["name"] not in seen:
                name_desc = (pkg["name"] + " " + pkg["description"]).lower()
                if any(t in name_desc for t in terms):
                    seen.add(pkg["name"])
                    results.append(pkg)
    return results[:8]


def _search_pypi(query: str) -> list[dict]:
    from lyra.knowledge.pypi import search
    return search(query)


def _search_cargo(query: str) -> list[dict]:
    from lyra.knowledge.cargo import search
    return search(query)


def _search_npm(query: str) -> list[dict]:
    from lyra.knowledge.npm import search
    return search(query)


def _search_wiki(query: str, distro: str | None) -> str | None:
    from lyra.knowledge.wiki import search
    return search(query, distro)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve(query: str, search_terms: list[str] | None = None) -> dict:
    """
    Resolve a user query into curated package and wiki knowledge.

    Searches are run in parallel. Ecosystem registries (PyPI, crates.io, npm)
    are only queried when the query appears development-related, to avoid
    irrelevant results for general software questions.

    Returns a dict with keys:
        system_packages  — list of dicts from pacman/apt
        pypi_packages    — list of dicts from PyPI
        cargo_crates     — list of dicts from crates.io
        npm_packages     — list of dicts from npm
        wiki             — str excerpt or None
    """
    profile = load_profile()
    ecosystems = profile.get("ecosystems", {})
    pkg_mgr = profile.get("package_manager")
    distro = profile.get("distro")

    if search_terms is None:
        search_terms = _extract_keywords(query)
        if not search_terms:
            search_terms = [query]

    is_dev = _is_dev_query(query)

    tasks: dict = {}

    if pkg_mgr == "pacman":
        tasks["system"] = lambda: _search_pacman_multi(search_terms)
    elif pkg_mgr == "apt":
        tasks["system"] = lambda: _search_apt_multi(search_terms)

    if is_dev:
        first_term = search_terms[0] if search_terms else query
        if "python" in ecosystems:
            tasks["pypi"] = lambda: _search_pypi(first_term)
        if "rust" in ecosystems:
            tasks["cargo"] = lambda: _search_cargo(first_term)
        if "node" in ecosystems:
            tasks["npm"] = lambda: _search_npm(first_term)

    tasks["wiki"] = lambda: _search_wiki(query, distro)

    results = _run_parallel(tasks)

    return {
        "system_packages": results.get("system", []),
        "pypi_packages": results.get("pypi", []),
        "cargo_crates": results.get("cargo", []),
        "npm_packages": results.get("npm", []),
        "wiki": results.get("wiki"),
    }


def format_for_prompt(resolved: dict) -> str:
    """
    Format resolver output into a compact string for injection into the system prompt.

    Prioritizes already-installed packages, then available system packages,
    then ecosystem alternatives, then wiki context.
    """
    parts = []

    if resolved.get("system_packages"):
        installed = [p for p in resolved["system_packages"] if p.get("installed")]
        available = [p for p in resolved["system_packages"] if not p.get("installed")]

        if installed:
            parts.append("Already installed: " + ", ".join(p["name"] for p in installed))

        if available:
            lines = [f"  - {p['name']}: {p['description']}" for p in available[:5]]
            parts.append("Available in system repos:\n" + "\n".join(lines))

    if resolved.get("pypi_packages"):
        lines = [f"  - {p['name']}: {p['description']}" for p in resolved["pypi_packages"][:3]]
        parts.append("Available on PyPI (pip):\n" + "\n".join(lines))

    if resolved.get("cargo_crates"):
        lines = [f"  - {p['name']}: {p['description']}" for p in resolved["cargo_crates"][:3]]
        parts.append("Available on crates.io (cargo):\n" + "\n".join(lines))

    if resolved.get("npm_packages"):
        lines = [f"  - {p['name']}: {p['description']}" for p in resolved["npm_packages"][:3]]
        parts.append("Available on npm:\n" + "\n".join(lines))

    if resolved.get("wiki"):
        parts.append(f"Wiki reference:\n{resolved['wiki']}")

    return "\n\n".join(parts)
