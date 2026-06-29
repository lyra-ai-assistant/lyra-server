# Lyra Server

Backend daemon for Lyra — an open source AI assistant for GNU/Linux.

Exposes two simultaneous interfaces:
- **Unix socket** — used by the CLI and Electron UI, stateful via `session_id`
- **HTTP API on :4000** — REST with SSE streaming for external integrations

## Development

### Requirements

- Python 3.13+
- [`uv`](https://github.com/astral-sh/uv)
- GNU/Linux x86_64

### Installation

```bash
git clone https://github.com/lyra-ai-assistant/lyra-server
cd lyra-server
uv tool install . --force
lyra-install-backend
```

> `uv tool install . --force` must be run after every change to `lyra-server`.
> `lyra-install-backend` only needs to run once — it detects your GPU and downloads the AI model.

## Configuration

The server reads configuration from `~/.config/lyra/config.json`.  
**This file is created automatically** when you run `lyra-install-backend`, with these defaults:

```json
{
  "host": "127.0.0.1",
  "apiPort": 4000,
  "mode": "dev",
  "verbose": "0",
  "nodeEnv": "development"
}
```

| Key | Description |
|-----|-------------|
| `host` | Bind address |
| `apiPort` | HTTP API port |
| `mode` | `"dev"` or `"prod"` |
| `verbose` | `"0"` = minimal logging, `"1"` = debug logging |
| `nodeEnv` | Used by the UI, not by `lyra-server` |

To modify settings, edit this file or use the CLI:

```bash
lyra config get host
lyra config set apiPort 5000
lyra config list
```

### Usage

```bash
lyra serve              # foreground
lyra serve --daemon     # background
lyra stop
lyra status
lyra -q "how do I install neovim"
```

### CLI reference

| Command | Description |
|---------|-------------|
| `lyra serve` | Start the daemon in foreground |
| `lyra serve --daemon` | Start the daemon in background |
| `lyra stop` | Send SIGTERM to the daemon |
| `lyra status` | Show PID and socket path |
| `lyra -q "<text>"` | Send a query and print the response |
| `lyra config get <key>` | Get a config value |
| `lyra config set <key> <value>` | Set a config value |
| `lyra config list` | List all config values |
| `lyra profile show` | Show the current system profile |
| `lyra profile refresh` | Re-detect ecosystems and update profile |
| `lyra uninstall` | Remove all Lyra data and config |
| `lyra --version` | Show version |
| `lyra-install-backend` | Detect GPU, install llama-cpp-python, download model |

## Architecture

### File system

```
lyra-server
├── agents/         # LLM wrapper (llama-cpp-python)
├── api/            # FastAPI routers: /chat, /chat/stream, /health
├── cli/            # CLI entry point, daemon, Unix socket server
├── config/         # Environment variables
├── context/        # Session manager (SQLite WAL)
├── db/             # SQLite connection and schema
├── knowledge/      # Package resolvers: pacman, apt, PyPI, npm, crates.io, wiki
├── memory/         # Semantic memory (ChromaDB + ONNXMiniLM)
├── scripts/        # Backend installer
├── services/       # Chat handler, direct answer logic
├── templates/      # Default config
├── tools/          # System info: disk, memory, CPU, ecosystems, packages
└── util/           # Shared utilities: formatting, token budget, context window
```

### Runtime files

| Path | Description |
|------|-------------|
| `~/.config/lyra/config.json` | Host, port, mode, verbosity |
| `~/.config/lyra/profile.json` | Auto-detected system profile |
| `~/.local/share/lyra/models/` | GGUF model file |
| `~/.local/share/lyra/chroma/` | Persistent semantic memory |
| `~/.local/share/lyra/lyra.db` | Session and message history |
| `~/.local/share/lyra/lyra.sock` | Unix socket |
| `~/.local/share/lyra/lyra.log` | Daemon log |

### HTTP API

```
POST /chat
POST /chat/stream   # SSE streaming
DELETE /chat/{session_id}
GET  /health
```

### Stack

| Component | Technology |
|-----------|------------|
| Runtime | Python 3.13, uv |
| HTTP API | FastAPI + uvicorn |
| Inference | llama-cpp-python |
| Model | Qwen2.5-1.5B Instruct Q4_K_M (GGUF) |
| Embeddings | ONNXMiniLM L6 V2 via ChromaDB |
| Semantic memory | ChromaDB PersistentClient |
| Session history | SQLite WAL |

## License

(AGPL-3.0)[http://github.com/lyra-ai-assistant/lyra-server?tab=AGPL-3.0-1-ov-file]
