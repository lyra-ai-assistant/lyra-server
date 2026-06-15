from memory.chroma import client, embedding_fn

COLLECTION_NAME = "lyra_memory"
TOP_K = 3

_col = client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=embedding_fn,
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
