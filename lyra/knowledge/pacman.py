import subprocess


def search(query: str) -> list[dict]:
    """Busca paquetes en pacman por nombre y descripción."""
    result = subprocess.run(
        ["pacman", "-Ss", query],
        capture_output=True, text=True,
    )
    packages = []
    lines = result.stdout.splitlines()
    i = 0
    while i < len(lines) - 1:
        header = lines[i].strip()
        description = lines[i + 1].strip()
        if "/" in header:
            parts = header.split()
            name = parts[0].split("/")[-1]
            version = parts[1] if len(parts) > 1 else ""
            installed = "[installed]" in header
            packages.append({
                "name": name,
                "version": version,
                "description": description,
                "installed": installed,
            })
        i += 2
    return packages[:10]
