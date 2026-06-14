import subprocess


def search(query: str) -> list[dict]:
    result = subprocess.run(
        ["apt-cache", "search", query],
        capture_output=True, text=True,
    )
    packages = []
    for line in result.stdout.splitlines():
        if " - " in line:
            name, description = line.split(" - ", 1)
            packages.append({
                "name": name.strip(),
                "description": description.strip(),
                "installed": False,
            })
    return packages[:10]
