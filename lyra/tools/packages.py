import shutil
import subprocess


def get_installed_packages() -> list[str]:
    if shutil.which("pacman"):
        result = subprocess.run(["pacman", "-Qq"], capture_output=True, text=True)
    elif shutil.which("apt"):
        result = subprocess.run(["apt", "list", "--installed"], capture_output=True, text=True)
    elif shutil.which("dnf"):
        result = subprocess.run(["dnf", "list", "installed"], capture_output=True, text=True)
    else:
        return []
    return [l.strip() for l in result.stdout.splitlines() if l.strip()]


def get_relevant_packages(keywords: list[str]) -> list[str]:
    installed = get_installed_packages()
    keywords_lower = [k.lower() for k in keywords]
    return [
        pkg for pkg in installed
        if any(k in pkg.lower() for k in keywords_lower)
    ]
