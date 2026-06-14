"""
Detects the current available hardware to install a llama-cpp-python variant that
matches the user's hardware, also it downloads a GGUF model to ~/.local/share/lyra/models/.
"""
import os
import subprocess
import sys
import shutil
from pathlib import Path

MODELS_DIR = Path.home() / ".local" / "share" / "lyra" / "models"
LYRA_VENV = Path.home() / ".local" / "share" / "lyra" / "venv"

MODEL_REPO = "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"
MODEL_FILE = "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"


def _get_installer() -> list[str]:
    LYRA_VENV.mkdir(parents=True, exist_ok=True)

    # Crear el venv si no existe
    if not (LYRA_VENV / "bin" / "python").exists():
        print(f"Creating lyra venv at {LYRA_VENV}")
        if shutil.which("uv"):
            subprocess.run(["uv", "venv", str(LYRA_VENV)], check=True)
        else:
            subprocess.run([sys.executable, "-m", "venv", str(LYRA_VENV)], check=True)

    pip = LYRA_VENV / "bin" / "pip"
    if pip.exists():
        return [str(pip), "install"]

    # uv puede instalar en un venv específico
    if shutil.which("uv"):
        return ["uv", "pip", "install", "--python", str(LYRA_VENV / "bin" / "python")]

    raise RuntimeError(f"Could not find pip in {LYRA_VENV}")


def _has_amd_vulkan() -> bool:
    try:
        result = subprocess.run(
            ["vulkaninfo", "--summary"],
            capture_output=True,
            text=True,
        )
        return "AMD" in result.stdout or "RADV" in result.stdout
    except Exception:
        return False


def _compile_and_install() -> None:
    if shutil.which("nvidia-smi"):
        print("NVIDIA GPU detected")
        cmake_args = "-DGGML_CUDA=on"
    elif shutil.which("rocminfo"):
        print("AMD ROCm GPU detected")
        cmake_args = "-DGGML_HIPBLAS=on"
    elif shutil.which("vulkaninfo") and _has_amd_vulkan():
        print("AMD GPU with Vulkan detected")
        cmake_args = "-DGGML_VULKAN=on"
    elif shutil.which("sycl-ls") or shutil.which("icpx"):
        print("Intel GPU detected")
        cmake_args = "-DGGML_SYCL=on"
    else:
        print("No GPU detected, using CPU")
        cmake_args = None

    env = {**os.environ}
    if cmake_args:
        env["CMAKE_ARGS"] = cmake_args

    installer = _get_installer()
    subprocess.run(
        [*installer, "llama-cpp-python", "--no-cache-dir"],
        env=env,
        check=True,
    )


def _download_model() -> None:
    model_path = MODELS_DIR / MODEL_FILE
    if model_path.exists():
        print(f"Model already exists at {model_path}")
        return

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {MODEL_FILE}...")

    from huggingface_hub import hf_hub_download
    hf_hub_download(
        repo_id=MODEL_REPO,
        filename=MODEL_FILE,
        local_dir=str(MODELS_DIR),
    )
    print(f"Model saved to {MODELS_DIR / MODEL_FILE}")


def detect_and_install() -> None:
    _compile_and_install()
    _download_model()


if __name__ == "__main__":
    detect_and_install()
