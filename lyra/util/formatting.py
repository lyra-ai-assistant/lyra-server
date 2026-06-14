import re
import markdown as md

_CHAT_TOKENS = re.compile(r"<\|(system|user|assistant)\|>|</s>|<s>|\[INST\]|\[/INST\]")


def clean_response(text: str) -> str:
    """Strip chat-template tokens left over in the raw model output."""
    return _CHAT_TOKENS.sub("", text).strip()


def to_html(text: str) -> str:
    """Convert markdown text to HTML for the frontend."""
    return md.markdown(text, extensions=["fenced_code", "tables"])
