import shutil
import subprocess
from pathlib import Path


def detect_ecosystems() -> dict:
    """Detecta runtimes y package managers de ecosistemas instalados."""
    result = {}

    # Python
    if shutil.which("python") or shutil.which("python3"):
        result["python"] = _python_version()
        result["python_packages"] = _pip_packages()

    # Node
    if shutil.which("node"):
        result["node"] = _cmd_version(["node", "--version"])
        result["node_packages"] = _npm_global_packages()

    # Rust
    if shutil.which("cargo"):
        result["rust"] = _cmd_version(["rustc", "--version"])

    # Go
    if shutil.which("go"):
        result["go"] = _cmd_version(["go", "version"])

    # Java
    if shutil.which("java"):
        result["java"] = _cmd_version(["java", "-version"])

    # Docker
    if shutil.which("docker"):
        result["docker"] = True

    # Flatpak
    if shutil.which("flatpak"):
        result["flatpak"] = True

    # Snap
    if shutil.which("snap"):
        result["snap"] = True

    return result


def _cmd_version(cmd: list[str]) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        return (r.stdout or r.stderr).strip().splitlines()[0]
    except Exception:
        return None


def _python_version() -> str | None:
    return _cmd_version(["python3", "--version"])


def _pip_packages() -> list[str]:
    try:
        r = subprocess.run(
            ["pip", "list", "--format=freeze"],
            capture_output=True, text=True,
        )
        return [l.split("==")[0].lower() for l in r.stdout.splitlines() if l]
    except Exception:
        return []


def _npm_global_packages() -> list[str]:
    try:
        r = subprocess.run(
            ["npm", "list", "-g", "--depth=0", "--parseable"],
            capture_output=True, text=True,
        )
        return [Path(l).name for l in r.stdout.splitlines() if l]
    except Exception:
        return []
