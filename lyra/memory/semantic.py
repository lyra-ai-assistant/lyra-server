import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
from pathlib import Path

CHROMA_PATH = Path.home() / ".local" / "share" / "lyra" / "chroma"
COLLECTION_NAME = "lyra_memory"
TOP_K = 3

_embedding_fn = ONNXMiniLM_L6_V2()  # mismo modelo, sin torch
_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
_col = _client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=_embedding_fn,
)


def store_exchange(session_id: str, user_text: str, assistant_text: str, timestamp: float) -> None:
    _col.add(
        ids=[f"{session_id}_{timestamp}"],
        documents=[f"User: {user_text}\nAssistant: {assistant_text}"],
        metadatas=[{"session_id": session_id, "timestamp": timestamp}],
    )


def retrieve_relevant(query: str, top_k: int = TOP_K) -> list[str]:
    count = _col.count()
    if count == 0:
        return []
    results = _col.query(
        query_texts=[query],
        n_results=min(top_k, count),
    )
    return results["documents"][0] if results["documents"] else []
