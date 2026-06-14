import sys
from pathlib import Path
from typing import Generator

from lyra.util.formatting import clean_response
from lyra.util.token_budget import compute_max_tokens
from lyra.agents.constants import MODELS_DIR, MODEL_FILE, _GENERATION_KWARGS


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
            n_ctx=8192,
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


    def _build_messages(self, text, history, semantic_ctx, system_ctx) -> list:
        from lyra.util.profile import load_profile
        profile = load_profile()

        pkg_mgr = profile.get("package_manager", "apt")
        distro = profile.get("distro", "Linux")
        ecosystems = profile.get("ecosystems", {})
        eco_lines = []

        if "python" in ecosystems:
            pkgs = ecosystems.get("python_packages", [])
            eco_lines.append(
                f"Python ({ecosystems['python']}) is installed"
                + (f" with packages: {', '.join(pkgs[:30])}" if pkgs else "")
            )
        if "node" in ecosystems:
            eco_lines.append(f"Node.js ({ecosystems['node']}) is installed")
        if "rust" in ecosystems:
            eco_lines.append(f"Rust ({ecosystems['rust']}) is installed")
        if "go" in ecosystems:
            eco_lines.append(f"Go is installed")
        if ecosystems.get("docker"):
            eco_lines.append("Docker is available")
        if ecosystems.get("flatpak"):
            eco_lines.append("Flatpak is available")

        system = (
            f"You are Lyra, a GNU/Linux terminal assistant running on {distro}. "
            f"STRICT RULES: "
            f"1. ALWAYS use '{pkg_mgr}' for ALL install commands. NEVER use apt, yum, brew, or any other package manager. "
            f"2. NEVER suggest Windows software, MSI installers, or non-Linux solutions. "
            f"3. Only suggest Linux-native open source software. "
            f"4. Keep responses concise — max 3 suggestions with a one-line description each. "
            f"5. When suggesting software, prefer solutions that reuse already installed ecosystems to minimize new dependencies. "
            f"6. Always show the exact install command using {pkg_mgr}. "
            "Use markdown for code blocks."
        )

        if eco_lines:
            system += "\n\nInstalled ecosystems on this machine:\n" + "\n".join(f"- {l}" for l in eco_lines)
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
