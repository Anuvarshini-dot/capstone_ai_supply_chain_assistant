import pickle
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BM25_INDEX_PATH

_bm25_data = None


def load_bm25():
    global _bm25_data
    if _bm25_data is None:
        if not os.path.exists(BM25_INDEX_PATH):
            raise FileNotFoundError(
                f"BM25 index not found at {BM25_INDEX_PATH}. Run `python ingest.py` first."
            )
        with open(BM25_INDEX_PATH, "rb") as f:
            _bm25_data = pickle.load(f)
    return _bm25_data


def _matches_filter(meta: dict, filters: dict) -> bool:
    for key, value in filters.items():
        if isinstance(value, list):
            if str(meta.get(key, "")) not in [str(v) for v in value]:
                return False
        else:
            if str(meta.get(key, "")) != str(value):
                return False
    return True


def bm25_search(query: str, top_k: int = 20, metadata_filter: dict = None) -> list:
    data = load_bm25()
    bm25 = data["bm25"]
    texts = data["texts"]
    ids = data["ids"]
    metadatas = data["metadatas"]

    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

    hits = []
    for idx, score in ranked:
        if len(hits) >= top_k:
            break
        meta = metadatas[idx]
        if metadata_filter and not _matches_filter(meta, metadata_filter):
            continue
        hits.append({
            "id": ids[idx],
            "text": texts[idx],
            "metadata": meta,
            "bm25_score": float(score)
        })
    return hits
