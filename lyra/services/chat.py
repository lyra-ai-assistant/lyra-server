import time

from lyra.agents.GenerationAgent import GenerationAgent
from lyra.memory.semantic import store_exchange, retrieve_relevant
from lyra.context.manager import session_manager
from lyra.util.context_window import trim_history
from lyra.util.formatting import to_html
from lyra.knowledge.resolver import resolve, format_for_prompt
from lyra.util.profile import load_profile

_INSTALL_KEYWORDS = {
    "install", "instalar", "use", "usar", "get", "obtener",
    "need", "necesito", "want", "quiero", "puedo", "recomiendas",
    "recommend", "suggest", "sugiere",
}


def _try_direct_answer(query: str, resolved: dict, pkg_mgr: str) -> str | None:
    """
    If resolver found system packages for an install query, build the answer
    directly without the model to avoid hallucinations.
    """
    system_pkgs = resolved.get("system_packages", [])
    if not system_pkgs:
        return None

    q = query.lower()
    if not any(k in q for k in _INSTALL_KEYWORDS):
        return None

    installed = [p for p in system_pkgs if p.get("installed")]
    available = [p for p in system_pkgs if not p.get("installed")]

    parts = []
    if installed:
        parts.append("Already installed: " + ", ".join(p["name"] for p in installed))

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
