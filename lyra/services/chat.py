import time

from lyra.agents.GenerationAgent import GenerationAgent
from lyra.memory.semantic import store_exchange, retrieve_relevant
from lyra.context.manager import session_manager
from lyra.util.context_window import trim_history
from lyra.util.formatting import to_html
from lyra.knowledge.resolver import resolve, format_for_prompt
from lyra.util.profile import load_profile

_CHECK_KEYWORDS = {
    "instalado", "installed", "tenemos", "tienes", "tengo",
    "available", "disponible", "existe",
}

_INSTALL_KEYWORDS = {
    "install", "instalar", "use", "usar", "get", "obtener",
    "need", "necesito", "want", "quiero", "puedo", "recomiendas",
    "recommend", "suggest", "sugiere",
}


def _try_direct_answer(query: str, resolved: dict, pkg_mgr: str) -> str | None:
    """
    If resolver found system packages, build the answer directly without
    the model to avoid hallucinations.

    Handles two cases:
      - Install query  → return install command
      - Check query    → return yes/no + optional install command
    """
    system_pkgs = resolved.get("system_packages", [])
    if not system_pkgs:
        return None

    q = query.lower()
    is_check = any(k in q for k in _CHECK_KEYWORDS)
    is_install = any(k in q for k in _INSTALL_KEYWORDS)

    if not is_check and not is_install:
        return None

    installed = [p for p in system_pkgs if p.get("installed")]
    available = [p for p in system_pkgs if not p.get("installed")]

    if is_check and not is_install:
        if installed:
            names = ", ".join(p["name"] for p in installed)
            return f"Sí, tienes instalado: **{names}**"
        elif available:
            return (
                f"No está instalado. Puedes instalarlo con:\n"
                f"```bash\nsudo {pkg_mgr} -S {available[0]['name']}\n```"
            )
        return None

    parts = []
    if installed:
        parts.append("Ya instalado: " + ", ".join(p["name"] for p in installed))
    for pkg in available[:2]:
        parts.append(
            f"**{pkg['name']}** — {pkg['description']}\n"
            f"```bash\nsudo {pkg_mgr} -S {pkg['name']}\n```"
        )
    return "\n\n".join(parts)


def handle_chat(text: str, session_id: str | None, agent: GenerationAgent):
    session_id, history = session_manager.get_or_create(session_id)
    trimmed = trim_history(history)
    semantic_ctx = retrieve_relevant(text)

    profile = load_profile()
    pkg_mgr = profile.get("package_manager", "pacman")
    resolved = resolve(text)

    direct = _try_direct_answer(text, resolved, pkg_mgr)
    if direct:
        session_manager.add_messages(session_id, text, direct)
        store_exchange(session_id, text, direct, time.time())
        return direct, session_id

    system_ctx = format_for_prompt(resolved)
    response_text = agent.handle_request(text, trimmed, semantic_ctx, system_ctx or None)
    session_manager.add_messages(session_id, text, response_text)
    store_exchange(session_id, text, response_text, time.time())
    return to_html(response_text), session_id


def persist_stream(session_id: str, text: str, collected: list[str]):
    full_response = "".join(collected)
    session_manager.add_messages(session_id, text, full_response)
    store_exchange(session_id, text, full_response, time.time())
