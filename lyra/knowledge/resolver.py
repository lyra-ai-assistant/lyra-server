import asyncio
import shutil
from concurrent.futures import ThreadPoolExecutor

from lyra.util.profile import load_profile


def resolve(query: str) -> dict:
    """
    Orquesta búsqueda en paralelo en todas las fuentes relevantes
    según el perfil del usuario.
    """
    profile = load_profile()
    ecosystems = profile.get("ecosystems", {})
    pkg_mgr = profile.get("package_manager")
    distro = profile.get("distro")

    tasks = {}

    # Sistema de paquetes
    if pkg_mgr == "pacman":
        tasks["system"] = lambda: _search_pacman(query)
    elif pkg_mgr == "apt":
        tasks["system"] = lambda: _search_apt(query)

    # Ecosistemas instalados
    if "python" in ecosystems:
        tasks["pypi"] = lambda: _search_pypi(query)
    if "rust" in ecosystems:
        tasks["cargo"] = lambda: _search_cargo(query)
    if "node" in ecosystems:
        tasks["npm"] = lambda: _search_npm(query)

    # Wiki
    tasks["wiki"] = lambda: _search_wiki(query, distro)

    # Ejecutar en paralelo
    results = _run_parallel(tasks)

    return {
        "system_packages": results.get("system", []),
        "pypi_packages": results.get("pypi", []),
        "cargo_crates": results.get("cargo", []),
        "npm_packages": results.get("npm", []),
        "wiki": results.get("wiki"),
    }


def format_for_prompt(resolved: dict) -> str:
    """Formatea el resultado del resolver para inyectar en el system prompt."""
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


def _run_parallel(tasks: dict) -> dict:
    results = {}
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {key: executor.submit(fn) for key, fn in tasks.items()}
        for key, future in futures.items():
            try:
                results[key] = future.result(timeout=8)
            except Exception:
                results[key] = [] if key != "wiki" else None
    return results


def _search_pacman(query: str):
    from lyra.knowledge.pacman import search
    return search(query)


def _search_apt(query: str):
    from lyra.knowledge.apt import search
    return search(query)


def _search_pypi(query: str):
    from lyra.knowledge.pypi import search
    return search(query)


def _search_cargo(query: str):
    from lyra.knowledge.cargo import search
    return search(query)


def _search_npm(query: str):
    from lyra.knowledge.npm import search
    return search(query)


def _search_wiki(query: str, distro: str | None):
    from lyra.knowledge.wiki import search
    return search(query, distro)
