import json
import platform
import shutil
from pathlib import Path

PROFILE_PATH = Path.home() / ".config" / "lyra" / "profile.json"

_PACKAGE_MANAGERS = [
    "pacman", "apt", "dnf", "zypper", "emerge", "xbps-install", "apk"
]


def _detect() -> dict:
    pkg_mgr = next((m for m in _PACKAGE_MANAGERS if shutil.which(m)), None)
    return {
        "os": platform.system(),
        "distro": _read_distro(),
        "package_manager": pkg_mgr,
        "arch": platform.machine(),
    }


def _read_distro() -> str | None:
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except FileNotFoundError:
        pass
    return None


def _build_profile() -> dict:
    from lyra.tools.ecosystem import detect_ecosystems
    profile = _detect()
    profile["ecosystems"] = detect_ecosystems()
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROFILE_PATH.open("w") as f:
        json.dump(profile, f, indent=2)
    return profile


def load_profile() -> dict:
    if PROFILE_PATH.exists():
        with PROFILE_PATH.open() as f:
            return json.load(f)
    return _build_profile()


def refresh_profile() -> dict:
    if PROFILE_PATH.exists():
        PROFILE_PATH.unlink()
    return _build_profile()


def update_profile(key: str, value) -> None:
    profile = load_profile()
    profile[key] = value
    with PROFILE_PATH.open("w") as f:
        json.dump(profile, f, indent=2)
