import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chromadb
from config import CHROMA_PERSIST_DIR, CHROMA_COLLECTION_NAME

_client = None
_collection = None


def get_client():
    global _client
    if _client is None:
        os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    return _client


def get_collection():
    global _collection
    if _collection is None:
        client = get_client()
        _collection = client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
    return _collection


def semantic_search(query_embedding: list, top_k: int = 20, where: dict = None) -> list:
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return []

    kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": min(top_k, count),
        "include": ["documents", "metadatas", "distances"]
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    hits = []
    for i, doc_id in enumerate(results["ids"][0]):
        hits.append({
            "id": doc_id,
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "semantic_score": round(1 - results["distances"][0][i], 4)
        })
    return hits
