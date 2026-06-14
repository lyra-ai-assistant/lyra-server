import sys
from pathlib import Path
from typing import Generator

from lyra.util.formatting import clean_response
from lyra.util.token_budget import compute_max_tokens
from lyra.agents.constants import MODELS_DIR, MODEL_FILE, _BASE_SYSTEM_PROMPT, _GENERATION_KWARGS


def _ensure_llama_cpp() -> None:
    try:
        import llama_cpp  # noqa
        return
    except ImportError:
        pass

    venv_site = (
        Path.home() / ".local" / "share" / "lyra" / "venv" /
        "lib" /
        f"python{sys.version_info.major}.{sys.version_info.minor}" /
        "site-packages"
    )
    if venv_site.exists():
        sys.path.insert(0, str(venv_site))
    else:
        raise ImportError(
            "llama-cpp-python not found. Run `lyra-install-backend` first."
        )


class GenerationAgent:
    def __init__(self):
        _ensure_llama_cpp()
        from llama_cpp import Llama

        model_path = MODELS_DIR / MODEL_FILE
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {model_path}. Run `lyra-install-backend` first."
            )

        self._llm = Llama(
            model_path=str(model_path),
            n_ctx=2048,
            n_gpu_layers=-1,
            verbose=False,
        )

    def warmup(self) -> None:
        self._llm.create_chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1,
        )

    def handle_request(
        self,
        text: str,
        history: list | None = None,
        semantic_ctx: list[str] | None = None,
        system_ctx: str | None = None,
    ) -> str:
        messages = self._build_messages(text, history, semantic_ctx, system_ctx)
        result = self._llm.create_chat_completion(
            messages=messages,
            max_tokens=compute_max_tokens(),
            **_GENERATION_KWARGS,
        )
        raw = result["choices"][0]["message"]["content"]
        return clean_response(raw)

    def stream_request(
        self,
        text: str,
        history: list | None = None,
        semantic_ctx: list[str] | None = None,
        system_ctx: str | None = None,
    ) -> Generator[str, None, None]:
        messages = self._build_messages(text, history, semantic_ctx, system_ctx)
        stream = self._llm.create_chat_completion(
            messages=messages,
            max_tokens=compute_max_tokens(),
            stream=True,
            **_GENERATION_KWARGS,
        )
        for chunk in stream:
            token = chunk["choices"][0]["delta"].get("content", "")
            if token:
                yield token

    # -- private --

    def _build_messages(
        self,
        text: str,
        history: list | None,
        semantic_ctx: list[str] | None,
        system_ctx: str | None,
    ) -> list:
        system = _BASE_SYSTEM_PROMPT
        if system_ctx:
            system += f"\n\nCurrent system state:\n{system_ctx}"
        if semantic_ctx:
            joined = "\n---\n".join(semantic_ctx)
            system += f"\n\nRelevant context from past conversations:\n{joined}"
        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": text})
        return messages
