# CLAUDE.md — server/

This is the FastAPI backend for Lyra, a local GNU/Linux desktop assistant running TinyLlama-1.1B-Chat-v1.0. It has no cloud dependencies — all storage is local SQLite + ChromaDB.

## Quick start

```bash
python -m venv env
source env/bin/activate          # Linux
env\Scripts\activate             # Windows
pip install -r dev-requirements.txt
uvicorn main:app --reload
```

First run downloads TinyLlama (~2 GB). The lifespan handler runs a warm-up inference before the server accepts requests — expect ~30 s delay on startup.

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/chat` | Stateful chat, returns HTML response |
| POST | `/chat/stream` | SSE streaming chat |
| DELETE | `/chat/{session_id}` | Clear a session |
| GET | `/health` | Status, model readiness, disk/memory/cpu metrics |

`/chat` and `/chat/stream` both accept `{"text": "...", "session_id": "..."}`. `session_id` is optional on the first turn; the server creates one and returns it. Pass it back on subsequent turns.

## Architecture

### Context pipeline (per chat turn)

```
user message
    ↓
retrieve_knowledge(text)   → top-3 Ubuntu packages from lyra_knowledge (ChromaDB)
retrieve_relevant(text)    → top-3 past exchanges from lyra_memory (ChromaDB)
trim_history(history)      → last N messages fitting within 3500 chars
    ↓
system prompt (templates/system_prompt.txt)
+ package knowledge
+ conversation memory
+ trimmed history
+ user message
    ↓
TinyLlama → response → stored in SQLite + ChromaDB
```

### Storage layout

| Store | Path | What it holds |
|---|---|---|
| SQLite | `~/.local/share/lyra/lyra.db` | Sessions and full message history |
| ChromaDB lyra_memory | `~/.local/share/lyra/chroma` | Semantic embeddings of conversation exchanges |
| ChromaDB lyra_knowledge | `~/.local/share/lyra/chroma` | Ubuntu package index (requires ingest) |

### Module map

```
main.py                  — FastAPI app, lifespan warm-up, all endpoints
agents/GenerationAgent.py — TinyLlama pipeline, prompt building, streaming
context/manager.py        — SQLite-backed session manager (TTL 30 min)
db/connection.py          — SQLite WAL mode, schema, connection factory
memory/chroma.py          — Shared ChromaDB PersistentClient + embedding fn (singleton)
memory/semantic.py        — lyra_memory collection: store/retrieve conversation exchanges
memory/knowledge.py       — lyra_knowledge collection: retrieve Ubuntu package info
tools/linux.py            — /proc-based system metrics (Linux only)
util/context_window.py    — trim_history: keeps newest messages within char budget
util/formatting.py        — markdown → HTML (used before returning /chat responses)
util/gpu.py               — CUDA detection, returns device/dtype/device_map config
templates/system_prompt.txt — Lyra persona prompt, edit without touching code
scripts/ingest_packages.py  — One-time script to populate lyra_knowledge
```

## Key design decisions

**No LangChain/LangGraph.** ChromaDB + sentence-transformers (all-MiniLM-L6-v2) handle RAG directly. Adding LangChain would wrap the same primitives with heavy transitive dependencies and no benefit.

**Single ChromaDB client.** `memory/chroma.py` exports one `PersistentClient` instance shared by `semantic.py` and `knowledge.py`. Two clients pointing to the same path can cause locking conflicts in ChromaDB.

**SSE streaming uses asyncio.Queue bridge.** `TextIteratorStreamer` is a sync generator; FastAPI streaming is async. The bridge pattern (`asyncio.run_coroutine_threadsafe` + daemon thread) avoids `run_until_complete` deadlocks that would occur inside an already-running event loop.

**HTML conversion happens server-side.** `to_html()` converts markdown before returning `/chat` responses. This is intentional — the Electron client expects HTML. Do not change this without updating the frontend.

**`/health` has a platform guard.** `memory_info()` and `cpu_info()` read `/proc` files that don't exist on Windows. They return `null` on non-Linux hosts. `disk_usage()` uses `shutil` and always runs.

**DispatcherAgent and AnalysisAgent were removed.** The original backend had a zero-shot classifier routing to a separate DistilBERT sentiment agent. Both were removed — they loaded ~500 MB of models for functionality the UI never used. The only agent now is `GenerationAgent`.

## Populating the knowledge base

Run once after installing dependencies:

```bash
python -m scripts.ingest_packages
# other Ubuntu releases:
python -m scripts.ingest_packages --url https://packages.ubuntu.com/noble/allpackages?format=txt.gz
# re-ingest from scratch:
python -m scripts.ingest_packages --reset
```

Downloads `allpackages?format=txt.gz` (~31k packages), embeds with all-MiniLM-L6-v2, stores in ChromaDB. Takes ~5-10 min on CPU. Persists across server restarts. If the collection is empty, `/chat` works normally — knowledge context is silently omitted.

## Commit format

Every commit must follow:

```
Title(type of change)

4-5 line summary paragraph explaining what changed and why.

Change log:
- bullet point per file/change
- ...

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

All changes go through a PR on a feature branch. Never commit directly to main.

## Python version

Python 3.13 compatible. `numpy>=2.0.0` and `tokenizers>=0.20.3` are required — earlier pins lack cp313 wheels and fail to install without a C/Rust compiler.
