from memory.chroma import client, embedding_fn

COLLECTION_NAME = "lyra_knowledge"
TOP_K = 3

_col = client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=embedding_fn,
)


def retrieve_knowledge(query: str, top_k: int = TOP_K) -> list[str]:
    count = _col.count()
    if count == 0:
        return []
    results = _col.query(
        query_texts=[query],
        n_results=min(top_k, count),
    )
    return results["documents"][0] if results["documents"] else []
