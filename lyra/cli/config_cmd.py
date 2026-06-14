"""
lyra config get <key>
lyra config set <key> <value>
lyra config list
"""

import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "lyra" / "config.json"

_ALLOWED_KEYS = {
    "host",
    "apiPort",
    "mode",
    "verbose",
}


def _load() -> dict:
    if not CONFIG_PATH.exists():
        print(f"Config not found at {CONFIG_PATH}")
        raise SystemExit(1)
    with CONFIG_PATH.open() as f:
        return json.load(f)


def _save(config: dict) -> None:
    with CONFIG_PATH.open("w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def cmd_get(key: str) -> None:
    config = _load()
    if key not in config:
        print(f"Unknown key: {key}")
        raise SystemExit(1)
    print(config[key])


def cmd_set(key: str, value: str) -> None:
    if key not in _ALLOWED_KEYS:
        print(f"Unknown key '{key}'. Allowed: {', '.join(sorted(_ALLOWED_KEYS))}")
        raise SystemExit(1)

    config = _load()

    # Coerce value to match existing type
    existing = config.get(key)
    if isinstance(existing, bool):
        value = value.lower() in ("1", "true", "yes")
    elif isinstance(existing, int):
        try:
            value = int(value)
        except ValueError:
            print(f"Key '{key}' expects an integer")
            raise SystemExit(1)

    config[key] = value
    _save(config)
    print(f"{key} = {value}")


def cmd_list() -> None:
    config = _load()
    for k, v in config.items():
        print(f"{k} = {v}")


def run_config(args) -> None:
    """Entry point called from commands.py with the parsed namespace."""
    sub = args.config_cmd
    if sub == "get":
        cmd_get(args.key)
    elif sub == "set":
        cmd_set(args.key, args.value)
    elif sub == "list":
        cmd_list()
    else:
        print("Usage: lyra config <get|set|list> [key] [value]")
        raise SystemExit(1)
