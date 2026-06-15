from pathlib import Path

MODELS_DIR = Path.home() / ".local" / "share" / "lyra" / "models"
MODEL_FILE = "qwen2.5-1.5b-instruct-q4_k_m.gguf"

_GENERATION_KWARGS = dict(
    temperature=0.7,
    top_k=50,
    top_p=0.95,
    repeat_penalty=1.1,
)
