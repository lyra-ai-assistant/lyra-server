"""
CLI client: connects to the daemon via Unix socket to run a query.
If the daemon is not running, starts it first then retries.
"""

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from lyra.cli.daemon import SOCKET_PATH, is_running

_CONNECT_TIMEOUT = 10   # seconds to wait for daemon to be ready
_RECV_BUFFER = 65536


def _connect() -> socket.socket:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(str(SOCKET_PATH))
    return sock


def _wait_for_daemon(timeout: int = _CONNECT_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if SOCKET_PATH.exists():
            try:
                s = _connect()
                s.close()
                return True
            except (ConnectionRefusedError, OSError):
                pass
        time.sleep(0.3)
    return False


def _start_daemon() -> None:
    """Spawn daemon as a background process."""
    subprocess.Popen(
        ["lyra", "serve", "--daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def query(text: str) -> str:
    """
    Send a query to the daemon and return the plain-text response.
    Starts the daemon if it is not already running.
    """
    if not is_running():
        print("Starting lyra daemon...", file=sys.stderr)
        _start_daemon()
        if not _wait_for_daemon():
            print("ERROR: daemon did not start in time", file=sys.stderr)
            sys.exit(1)

    try:
        sock = _connect()
    except (ConnectionRefusedError, FileNotFoundError):
        print("ERROR: could not connect to lyra daemon", file=sys.stderr)
        sys.exit(1)

    payload = json.dumps({"query": text}).encode()
    sock.sendall(payload)
    sock.shutdown(socket.SHUT_WR)

    chunks = []
    while True:
        chunk = sock.recv(_RECV_BUFFER)
        if not chunk:
            break
        chunks.append(chunk)
    sock.close()

    return b"".join(chunks).decode()
