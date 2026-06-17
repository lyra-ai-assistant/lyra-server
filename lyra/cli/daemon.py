"""
Daemon lifecycle: fork, PID file, Unix socket server.

The daemon exposes two interfaces:
  - Unix socket at SOCKET_PATH  →  used by the CLI client (lyra -q)
  - HTTP on host:port           →  used by Electron
"""

import asyncio
import json
import os
import signal
import sys
from pathlib import Path

RUNTIME_DIR = Path.home() / ".local" / "share" / "lyra"
PID_FILE = RUNTIME_DIR / "lyra.pid"
SOCKET_PATH = RUNTIME_DIR / "lyra.sock"
LOG_FILE = RUNTIME_DIR / "lyra.log"


# ---------------------------------------------------------------------------
# PID helpers
# ---------------------------------------------------------------------------

def _write_pid() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def _read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def _clear_pid() -> None:
    PID_FILE.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def is_running() -> bool:
    pid = _read_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        _clear_pid()
        return False
    except PermissionError:
        return True


def status() -> dict:
    pid = _read_pid()
    running = is_running()
    return {
        "running": running,
        "pid": pid if running else None,
        "socket": str(SOCKET_PATH) if running else None,
    }


# ---------------------------------------------------------------------------
# Daemon fork
# ---------------------------------------------------------------------------

def daemonize() -> None:
    """Double-fork to detach from the controlling terminal."""
    if is_running():
        print("lyra daemon is already running", file=sys.stderr)
        sys.exit(1)

    os.environ["GGML_VK_DISABLE"] = "1"
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    os.setsid()

    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    log_fd = open(LOG_FILE, "a")
    sys.stdout.flush()
    sys.stderr.flush()
    os.dup2(log_fd.fileno(), sys.stdout.fileno())
    os.dup2(log_fd.fileno(), sys.stderr.fileno())
    stdin = open(os.devnull, "r")
    os.dup2(stdin.fileno(), sys.stdin.fileno())

    _write_pid()

    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)


def _handle_sigterm(signum, frame) -> None:
    _clear_pid()
    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)


# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------

def stop() -> None:
    pid = _read_pid()
    if pid is None or not is_running():
        print("lyra is not running")
        return
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"lyra stopped (pid {pid})")
        _clear_pid()
    except ProcessLookupError:
        print("Process not found, cleaning up stale PID")
        _clear_pid()


# ---------------------------------------------------------------------------
# Unix socket server
# ---------------------------------------------------------------------------

async def _handle_socket_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    agent,
) -> None:
    try:
        raw = await reader.read(4096)
        if not raw:
            return
        payload = json.loads(raw.decode())
        query = payload.get("query", "")

        from lyra.knowledge.resolver import resolve, format_for_prompt
        from lyra.util.profile import load_profile
        from lyra.services.chat import _try_direct_answer
        from lyra.tools.linux import build_system_ctx

        profile = load_profile()
        pkg_mgr = profile.get("package_manager", "pacman")
        resolved = resolve(query)

        direct = _try_direct_answer(query, resolved, pkg_mgr)
        if direct:
            response = direct
        else:
            system_ctx = build_system_ctx(query)
            knowledge_ctx = format_for_prompt(resolved)
            combined = "\n\n".join(filter(None, [system_ctx, knowledge_ctx]))
            response = agent.handle_request(query, system_ctx=combined or None)

        writer.write(response.encode())
        await writer.drain()
    except Exception as e:
        writer.write(f"ERROR: {e}".encode())
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def start_socket_server(agent) -> asyncio.Server:
    """Start the Unix socket server."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()

    server = await asyncio.start_unix_server(
        lambda r, w: _handle_socket_client(r, w, agent),
        path=str(SOCKET_PATH),
    )
    SOCKET_PATH.chmod(0o600)
    return server
