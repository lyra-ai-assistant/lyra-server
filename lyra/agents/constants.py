from pathlib import Path

MODELS_DIR = Path.home() / ".local" / "share" / "lyra" / "models"
MODEL_FILE = "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"

_BASE_SYSTEM_PROMPT = (
    "You are Lyra, a helpful GNU/Linux assistant. You provide accurate and relevant "
    "information, answer questions, and help with various Linux-related tasks. Keep "
    "responses concise for simple questions and detailed for complex ones. Use markdown "
    "for code blocks, JSON examples, and tables."
)

_GENERATION_KWARGS = dict(
    temperature=0.7,
    top_k=50,
    top_p=0.95,
    repeat_penalty=1.1,
)
