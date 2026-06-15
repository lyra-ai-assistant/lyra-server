"""
Ingest Ubuntu Jammy package list into ChromaDB lyra_knowledge collection.

Downloads packages.ubuntu.com/jammy/allpackages?format=txt.gz, parses
each entry, and upserts them in batches into the knowledge collection so
the chat pipeline can retrieve relevant package information at query time.

Usage (from server/ with the venv active):
    python -m scripts.ingest_packages
    python -m scripts.ingest_packages --url https://packages.ubuntu.com/noble/allpackages?format=txt.gz
"""

import argparse
import gzip
import re
import sys
import urllib.request

# Allow running from the server/ directory without installing the package
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from memory.chroma import client, embedding_fn

COLLECTION_NAME = "lyra_knowledge"
DEFAULT_URL = "https://packages.ubuntu.com/jammy/allpackages?format=txt.gz"
BATCH_SIZE = 500

# Line format: "pkgname (version) [section]: description"
_LINE_RE = re.compile(r"^(\S+)\s+\(([^)]+)\)\s+\[([^\]]+)\]:\s+(.+)$")


def _get_collection():
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )


def _download_lines(url: str) -> list[str]:
    print(f"Downloading {url} ...")
    with urllib.request.urlopen(url) as resp:
        raw = resp.read()
    text = gzip.decompress(raw).decode("utf-8", errors="replace")
    return text.splitlines()


def _parse_lines(lines: list[str]) -> list[dict]:
    packages = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        name, version, section, description = m.groups()
        packages.append({
            "id": name,
            "document": f"Package: {name}\nVersion: {version}\nSection: {section}\nDescription: {description}",
            "metadata": {"name": name, "version": version, "section": section},
        })
    return packages


def _upsert(col, packages: list[dict]) -> None:
    total = len(packages)
    for start in range(0, total, BATCH_SIZE):
        batch = packages[start : start + BATCH_SIZE]
        col.upsert(
            ids=[p["id"] for p in batch],
            documents=[p["document"] for p in batch],
            metadatas=[p["metadata"] for p in batch],
        )
        end = min(start + BATCH_SIZE, total)
        print(f"  {end}/{total} packages ingested", end="\r")
    print()


def main():
    parser = argparse.ArgumentParser(description="Ingest Ubuntu packages into lyra_knowledge")
    parser.add_argument("--url", default=DEFAULT_URL, help="URL of allpackages?format=txt.gz")
    parser.add_argument("--reset", action="store_true", help="Delete existing collection before ingesting")
    args = parser.parse_args()

    if args.reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"Deleted existing '{COLLECTION_NAME}' collection.")
        except Exception:
            pass

    col = _get_collection()
    existing = col.count()
    if existing > 0 and not args.reset:
        print(f"Collection already has {existing} entries. Use --reset to re-ingest.")
        sys.exit(0)

    lines = _download_lines(args.url)
    packages = _parse_lines(lines)
    print(f"Parsed {len(packages)} packages. Embedding and storing (this takes a few minutes on CPU)...")
    _upsert(col, packages)
    print(f"Done. {col.count()} packages in '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    main()
