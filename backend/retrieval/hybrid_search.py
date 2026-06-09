import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BM25_WEIGHT, SEMANTIC_WEIGHT, RERANK_TOP_N
from retrieval.bm25_index import bm25_search
from retrieval.vector_store import semantic_search
from llm.client import embed


def _build_chroma_where(filters: dict):
    if not filters:
        return None
    conditions = []
    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, list):
            conditions.append({key: {"$in": [str(v) for v in value]}})
        else:
            conditions.append({key: {"$eq": str(value)}})
    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def hybrid_search(query: str, top_k: int = 5, filters: dict = None) -> list:
    query_embedding = embed([query])[0]
    chroma_where = _build_chroma_where(filters)

    semantic_hits = semantic_search(query_embedding, top_k=RERANK_TOP_N, where=chroma_where)
    bm25_hits = bm25_search(query, top_k=RERANK_TOP_N, metadata_filter=filters)
    # normalise the BM25 scores to 0-1 range based on the max score in the current hits
    raw_bm25 = {h["id"]: h["bm25_score"] for h in bm25_hits}
    max_bm25 = max(raw_bm25.values(), default=1) or 1
    norm_bm25 = {k: v / max_bm25 for k, v in raw_bm25.items()}

    combined = {}
    for hit in semantic_hits:
        combined[hit["id"]] = {
            "id": hit["id"],
            "text": hit["text"],
            "metadata": hit["metadata"],
            "semantic_score": hit["semantic_score"],
            "bm25_score": norm_bm25.get(hit["id"], 0.0)
        }
    for hit in bm25_hits:
        if hit["id"] not in combined:
            combined[hit["id"]] = {
                "id": hit["id"],
                "text": hit["text"],
                "metadata": hit["metadata"],
                "semantic_score": 0.0,
                "bm25_score": norm_bm25.get(hit["id"], 0.0)
            }

    for doc in combined.values():
        doc["hybrid_score"] = round(
            BM25_WEIGHT * doc["bm25_score"] + SEMANTIC_WEIGHT * doc["semantic_score"], 4
        )

    ranked = sorted(combined.values(), key=lambda x: x["hybrid_score"], reverse=True)
    return ranked[:top_k]
