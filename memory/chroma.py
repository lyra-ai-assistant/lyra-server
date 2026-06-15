import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from pathlib import Path

CHROMA_PATH = Path.home() / ".local" / "share" / "lyra" / "chroma"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
client = chromadb.PersistentClient(path=str(CHROMA_PATH))
