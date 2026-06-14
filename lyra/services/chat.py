import time
from lyra.agents.GenerationAgent import GenerationAgent
from lyra.memory.semantic import store_exchange, retrieve_relevant
from lyra.context.manager import session_manager
from lyra.util.context_window import trim_history
from lyra.util.formatting import to_html
from lyra.tools.linux import build_system_ctx


def handle_chat(text: str, session_id: str | None, agent: GenerationAgent):
    session_id, history = session_manager.get_or_create(session_id)
    trimmed = trim_history(history)
    semantic_ctx = retrieve_relevant(text)
    system_ctx = build_system_ctx(text)
    response_text = agent.handle_request(text, trimmed, semantic_ctx, system_ctx)
    session_manager.add_messages(session_id, text, response_text)
    store_exchange(session_id, text, response_text, time.time())
    return to_html(response_text), session_id


def persist_stream(session_id: str, text: str, collected: list[str]):
    full_response = "".join(collected)
    session_manager.add_messages(session_id, text, full_response)
    store_exchange(session_id, text, full_response, time.time())
