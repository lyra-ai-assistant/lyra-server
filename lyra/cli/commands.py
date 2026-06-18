"""
lyra CLI entry point.

Commands
--------
lyra                          → open Electron client or show --help
lyra serve                    → start API + socket server (foreground)
lyra serve --daemon           → start as background daemon
lyra stop                     → stop the daemon
lyra status                   → show daemon status
lyra -q "text"                → query the daemon, print plain-text response
lyra config list              → print all config keys
lyra config get <key>
lyra config set <key> <value>
lyra profile show             → show current profile
lyra profile refresh          → regenerate profile
lyra --version
"""

import argparse
import asyncio
import shutil
import subprocess
import sys

VERSION = "0.1.0"


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------

def _serve(daemon: bool) -> None:
    import os
    os.environ["GGML_VK_DISABLE"] = "1"

    from lyra.cli.daemon import daemonize, start_socket_server
    from lyra.api.dependencies import generation_agent
    from lyra.main import app, get_model_ready_event
    import uvicorn
    from lyra.config.env_vars import env_vars

    if daemon:
        daemonize()

    async def _run():
        config = uvicorn.Config(
            app,
            host=env_vars.host,
            port=env_vars.api_port,
            loop="none",
            log_level="warning",
        )
        server = uvicorn.Server(config)

        async def start_socket_when_ready():
            await get_model_ready_event().wait()
            print("[DEBUG] model ready, creating socket...", flush=True)
            try:
                socket_server = await start_socket_server(generation_agent)
                print("[DEBUG] socket created OK", flush=True)
                await socket_server.serve_forever()
            except Exception as e:
                import traceback
                print(f"[DEBUG] socket error: {e}", flush=True)
                traceback.print_exc()

        try:
            await asyncio.gather(
                server.serve(),
                start_socket_when_ready(),
            )
        except SystemExit as e:
            print(f"[lyra] uvicorn failed to start (port {env_vars.api_port} in use?)", flush=True)
            raise


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------


def _uninstall() -> None:
    import shutil
    from pathlib import Path

    dirs = [
        Path.home() / ".local" / "share" / "lyra",
        Path.home() / ".config" / "lyra",
    ]

    print("This will remove:")
    for d in dirs:
        if d.exists():
            print(f"  {d}")

    confirm = input("Continue? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted")
        return

    for d in dirs:
        if d.exists():
            shutil.rmtree(d)
            print(f"Removed {d}")

    print("Run 'uv tool uninstall lyra-server' to remove the package itself")


# ---------------------------------------------------------------------------
# stop / status
# ---------------------------------------------------------------------------

def _stop() -> None:
    from lyra.cli.daemon import stop
    stop()


def _status() -> None:
    from lyra.cli.daemon import status
    info = status()
    if info["running"]:
        print(f"lyra is running (pid {info['pid']})")
        print(f"socket: {info['socket']}")
    else:
        print("lyra is not running")


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------

def _query(text: str) -> None:
    from lyra.cli.client import query
    response = query(text)
    print(response)


# ---------------------------------------------------------------------------
# default (no args)
# ---------------------------------------------------------------------------

def _default() -> None:
    if shutil.which("lyra-client"):
        subprocess.Popen(["lyra-client"])
    else:
        _build_parser().print_help()


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lyra",
        description="Lyra AI assistant",
    )
    parser.add_argument("--version", action="version", version=f"lyra {VERSION}")
    parser.add_argument("-q", "--query", metavar="TEXT", help="Query the AI and print response")

    sub = parser.add_subparsers(dest="command")

    # serve
    serve_p = sub.add_parser("serve", help="Start the Lyra server")
    serve_p.add_argument("--daemon", action="store_true", help="Run as background daemon")

    # uninstall
    sub.add_parser("uninstall", help="Remove all Lyra data and models")

    # stop
    sub.add_parser("stop", help="Stop the daemon")

    # status
    sub.add_parser("status", help="Show daemon status")

    # config
    config_p = sub.add_parser("config", help="View or edit configuration")
    config_sub = config_p.add_subparsers(dest="config_cmd")
    config_sub.add_parser("list", help="List all config keys")
    get_p = config_sub.add_parser("get", help="Get a config value")
    get_p.add_argument("key")
    set_p = config_sub.add_parser("set", help="Set a config value")
    set_p.add_argument("key")
    set_p.add_argument("value")

    # profile
    profile_p = sub.add_parser("profile", help="Manage user profile")
    profile_sub = profile_p.add_subparsers(dest="profile_cmd")
    profile_sub.add_parser("show", help="Show current profile")
    profile_sub.add_parser("refresh", help="Regenerate profile")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.query:
        _query(args.query)
        return

    match args.command:
        case "serve":
            _serve(daemon=args.daemon)
        case "uninstall":
            _uninstall()
        case "stop":
            _stop()
        case "status":
            _status()
        case "config":
            from lyra.cli.config_cmd import run_config
            run_config(args)
        case "profile":
            import json
            from lyra.util.profile import load_profile, refresh_profile
            if args.profile_cmd == "refresh":
                profile = refresh_profile()
                print("Profile refreshed")
                print(json.dumps(profile, indent=2))
            elif args.profile_cmd == "show":
                print(json.dumps(load_profile(), indent=2))
            else:
                parser.print_help()
        case None:
            _default()
        case _:
            parser.print_help()


if __name__ == "__main__":
    main()
