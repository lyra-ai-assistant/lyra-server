from typing import TYPE_CHECKING

# TinyLlama-1.1B context window is 2048 tokens.
# Reserve ~1024 for the response; use the rest for history + system prompt.
# Rough estimate: 1 token ≈ 4 chars.
_MAX_HISTORY_CHARS = 3500


def trim_history(history: list[dict], max_chars: int = _MAX_HISTORY_CHARS) -> list[dict]:
    """
    Keep the most recent messages that fit within max_chars.
    Always preserves the latest turn so the model has at least one exchange for context.
    """
    total = 0
    trimmed: list[dict] = []
    for msg in reversed(history):
        total += len(msg["content"])
        if total > max_chars and trimmed:
            break
        trimmed.insert(0, msg)
    return trimmed
