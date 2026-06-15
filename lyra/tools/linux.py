import sys
import shutil
import subprocess
from lyra.util.profile import load_profile


_KEYWORDS_MEMORY = {"ram", "memory", "memoria", "mem"}
_KEYWORDS_DISK   = {"disk", "disco", "storage", "almacenamiento", "space", "espacio"}
_KEYWORDS_CPU    = {"cpu", "processor", "procesador", "load", "carga", "core"}
_KEYWORDS_PROCS  = {"process", "proceso", "top", "running", "corriendo"}
_KEYWORDS_PACKAGES = {
    "install", "instalar", "package", "paquete", "software",
    "program", "programa", "app", "tool", "herramienta"
}


def build_system_ctx(query: str) -> str | None:
    if sys.platform != "linux":
        return None

    q = query.lower()
    parts = []
    profile = load_profile()

    if profile.get("package_manager"):
        parts.append(f"Package manager: {profile['package_manager']}")
    if profile.get("distro"):
        parts.append(f"Distro: {profile['distro']}")

    from lyra.knowledge.resolver import resolve, format_for_prompt
    resolved = resolve(query)
    knowledge = format_for_prompt(resolved)
    if knowledge:
        parts.append(knowledge)

    if any(k in q for k in _KEYWORDS_MEMORY):
        m = memory_info()
        parts.append(
            f"RAM: {m['used_mb']}MB used / {m['total_mb']}MB total "
            f"({m['percent']}%), {m['free_mb']}MB free"
        )
    if any(k in q for k in _KEYWORDS_DISK):
        d = disk_usage()
        parts.append(
            f"Disk (/): {d['used_gb']}GB used / {d['total_gb']}GB total "
            f"({d['percent']}%), {d['free_gb']}GB free"
        )
    if any(k in q for k in _KEYWORDS_CPU):
        c = cpu_info()
        parts.append(
            f"CPU: {c['cores']} cores, load avg {c['load_1m']} (1m) "
            f"{c['load_5m']} (5m) {c['load_15m']} (15m)"
        )
    if any(k in q for k in _KEYWORDS_PROCS):
        procs = top_processes(5)
        lines = "\n".join(
            f"  {p['pid']} cpu={p['cpu_pct']}% mem={p['mem_pct']}% {p['command']}"
            for p in procs
        )
        parts.append(f"Top processes:\n{lines}")

    return "\n\n".join(parts) if parts else None


def disk_usage(path: str = "/") -> dict:
    total, used, free = shutil.disk_usage(path)
    return {
        "total_gb": round(total / 1e9, 2),
        "used_gb": round(used / 1e9, 2),
        "free_gb": round(free / 1e9, 2),
        "percent": round(used / total * 100, 1),
    }


def memory_info() -> dict:
    with open("/proc/meminfo") as f:
        data = {}
        for line in f:
            if ":" in line:
                key, val = line.split(":", 1)
                data[key.strip()] = int(val.split()[0])
    total = data.get("MemTotal", 0)
    available = data.get("MemAvailable", 0)
    used = total - available
    return {
        "total_mb": round(total / 1024, 1),
        "used_mb": round(used / 1024, 1),
        "free_mb": round(available / 1024, 1),
        "percent": round(used / total * 100, 1) if total else 0,
    }


def cpu_info() -> dict:
    result = subprocess.run(
        ["grep", "-c", "^processor", "/proc/cpuinfo"],
        capture_output=True, text=True,
    )
    cores = int(result.stdout.strip()) if result.returncode == 0 else 0
    with open("/proc/loadavg") as f:
        parts = f.read().split()
    return {
        "cores": cores,
        "load_1m": float(parts[0]),
        "load_5m": float(parts[1]),
        "load_15m": float(parts[2]),
    }


def top_processes(limit: int = 5) -> list[dict]:
    result = subprocess.run(
        ["ps", "aux", "--sort=-%cpu"],
        capture_output=True, text=True,
    )
    rows = []
    for line in result.stdout.strip().splitlines()[1 : limit + 1]:
        parts = line.split(None, 10)
        if len(parts) >= 11:
            rows.append({
                "pid": parts[1],
                "cpu_pct": parts[2],
                "mem_pct": parts[3],
                "command": parts[10][:60],
            })
    return rows


def detect_package_manager() -> str | None:
    managers = ["pacman", "apt", "dnf", "zypper", "emerge", "xbps-install", "apk"]
    for mgr in managers:
        if shutil.which(mgr):
            return mgr
    return None
