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

MODEL_REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
MODEL_FILE = "qwen2.5-1.5b-instruct-q4_k_m.gguf"



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


def _has_amd_discrete_gpu() -> bool:
    """Devuelve True solo si hay una GPU AMD discreta (no integrada Vega 6/8)."""
    # PIDs de GPUs integradas AMD Ryzen conocidas por crashear con Vulkan
    INTEGRATED_PIDS = {
        "15d8",  # Vega 8 (Ryzen 3000)
        "15dd",  # Vega 8 (Ryzen 2000)
        "15d9",  # Vega 10
        "164c",  # Vega 6 (Ryzen 4000)
        "1636",  # Vega 7 (Ryzen 5000)
        "15bf",  # Vega 8 (Ryzen 7000)
    }
    try:
        result = subprocess.run(
            ["vulkaninfo", "--summary"],
            capture_output=True,
            text=True,
        )
        output = result.stdout.lower()
        for pid in INTEGRATED_PIDS:
            if pid in output:
                return False
        return "amd" in output or "radv" in output
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
        if _has_amd_discrete_gpu():
            print("AMD discrete GPU with Vulkan detected")
            cmake_args = "-DGGML_VULKAN=on"
        else:
            print("AMD integrated GPU detected (Vega), Vulkan unstable — using CPU")
            cmake_args = None
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
