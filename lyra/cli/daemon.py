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
import socket
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
        return True  # exists but owned by another user


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
    """
    Double-fork to detach from the controlling terminal.
    Redirects stdout/stderr to LOG_FILE.
    """
    if is_running():
        print("lyra daemon is already running", file=sys.stderr)
        sys.exit(1)

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    # First fork
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    os.setsid()

    # Second fork
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # Redirect stdio to log
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
# Unix socket server (for CLI client queries)
# ---------------------------------------------------------------------------

async def _handle_socket_client(reader, writer, agent) -> None:
    try:
        raw = await reader.read(4096)
        if not raw:
            return
        payload = json.loads(raw.decode())
        query = payload.get("query", "")
        from lyra.tools.linux import build_system_ctx
        system_ctx = build_system_ctx(query)
        response = agent.handle_request(query, system_ctx=system_ctx)
        writer.write(response.encode())
        await writer.drain()
    except Exception as e:
        writer.write(f"ERROR: {e}".encode())
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def start_socket_server(agent) -> asyncio.Server:
    """Start the Unix socket server. Returns the server object."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()

    server = await asyncio.start_unix_server(
        lambda r, w: _handle_socket_client(r, w, agent),
        path=str(SOCKET_PATH),
    )
    SOCKET_PATH.chmod(0o600)
    return server
