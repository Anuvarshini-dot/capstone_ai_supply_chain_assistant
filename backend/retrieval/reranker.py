def rerank(query: str, hits: list, top_k: int = 5) -> list:
    """
    Score-based reranker that combines hybrid score with query-term overlap
    and severity boost. Drop-in replacement for a cross-encoder.
    """
    query_terms = set(query.lower().split())

    for hit in hits:
        text_lower = hit["text"].lower()
        term_overlap = sum(1 for t in query_terms if t in text_lower)
        overlap_score = term_overlap / max(len(query_terms), 1)

        severity_boost = {"high": 0.1, "medium": 0.05, "low": 0.0}.get(
            str(hit["metadata"].get("severity", "low")), 0.0
        )

        hit["rerank_score"] = round(
            0.7 * hit.get("hybrid_score", 0)
            + 0.2 * overlap_score
            + 0.1 * severity_boost,
            4
        )

    return sorted(hits, key=lambda x: x["rerank_score"], reverse=True)[:top_k]
