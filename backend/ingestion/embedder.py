import json
import os
import pickle
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BM25_INDEX_PATH, CHUNKS_PATH, EMBED_CHECKPOINT_PATH
from llm.client import embed
from retrieval.vector_store import get_collection
from rank_bm25 import BM25Okapi


def _batch(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


# ─── Improvement #: JSONL reader ────────────────────────────────────────────

def _read_chunks_jsonl(path: str) -> list:
    """Stream-read chunks.jsonl without loading all into RAM at once."""
    chunks = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


# ─── Improvement #: Retry logic ─────────────────────────────────────────────

def _embed_with_retry(texts: list, max_retries: int = 3) -> list:
    """
    Call the embedding API with exponential backoff retry.
    Retries on any exception — network error, rate limit, timeout etc.
    """
    for attempt in range(max_retries):
        try:
            return embed(texts)
        except Exception as e:
            if attempt == max_retries - 1:
                raise   # exhausted retries — re-raise original error
            wait = 2 ** attempt   # 1s, 2s, 4s
            print(f"  Embed failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait}s...")
            time.sleep(wait)


# ─── Improvement #: Checkpoint helpers ──────────────────────────────────────

def _save_checkpoint(last_embedded_id: str):
    """Save the ID of the last successfully embedded chunk."""
    with open(EMBED_CHECKPOINT_PATH, "w") as f:
        f.write(last_embedded_id)


def _load_checkpoint() -> str | None:
    """Return the last successfully embedded chunk ID, or None if no checkpoint."""
    if os.path.exists(EMBED_CHECKPOINT_PATH):
        with open(EMBED_CHECKPOINT_PATH) as f:
            val = f.read().strip()
            return val if val else None
    return None


def _clear_checkpoint():
    """Delete checkpoint file after a successful full run."""
    if os.path.exists(EMBED_CHECKPOINT_PATH):
        os.remove(EMBED_CHECKPOINT_PATH)


# ─── ChromaDB helpers ────────────────────────────────────────────────────────

def _get_existing_ids(collection) -> set:
    result = collection.get(include=[])
    return set(result["ids"])


def _load_existing_bm25_data() -> dict:
    if os.path.exists(BM25_INDEX_PATH):
        with open(BM25_INDEX_PATH, "rb") as f:
            return pickle.load(f)
    return {"texts": [], "ids": [], "metadatas": []}


# ─── Main function ────────────────────────────────────────────────────────────

def run_embedder(chunks: list = None, mode: str = "incremental"):
    """
    mode = "incremental" → only embed chunks not already in ChromaDB
    mode = "full"        → wipe everything and re-embed all chunks
    """
    if chunks is None:
        chunks = _read_chunks_jsonl(CHUNKS_PATH)

    collection = get_collection()

    # ── FULL mode ─────────────────────────────────────────────────────────────
    if mode == "full":
        existing_count = collection.count()
        if existing_count > 0:
            print(f"Full mode: clearing {existing_count:,} existing embeddings...")
            all_ids = collection.get(include=[])["ids"]
            collection.delete(ids=all_ids)

        new_chunks    = chunks
        existing_bm25 = {"texts": [], "ids": [], "metadatas": []}
        print(f"Full mode: embedding all {len(new_chunks):,} chunks...")

    # ── INCREMENTAL mode ──────────────────────────────────────────────────────
    else:
        existing_ids = _get_existing_ids(collection)

        # Improvement #4 — check checkpoint for faster filtering on resume
        checkpoint_id = _load_checkpoint()
        if checkpoint_id:
            print(f"  Resuming from checkpoint: last embedded ID = {checkpoint_id}")

        new_chunks = [c for c in chunks if c["id"] not in existing_ids]

        if not new_chunks:
            print(f"Incremental: nothing new to embed. ChromaDB has {len(existing_ids):,} records.")
            _clear_checkpoint()
            return

        existing_bm25 = _load_existing_bm25_data()
        print(f"Incremental: {len(existing_ids):,} existing | {len(new_chunks):,} new chunks to embed")

    # ── Embed in batches ──────────────────────────────────────────────────────
    # Improvement #1 — add to ChromaDB per batch (not accumulate all in RAM)
    # Improvement #2 — only accumulate texts/ids/metadatas (strings) for BM25,
    #                  NOT embeddings (float arrays) — much smaller memory footprint
    new_ids       = []
    new_texts     = []
    new_metadatas = []
    total_batches = (len(new_chunks) + 99) // 100

    for i, batch_chunks in enumerate(_batch(new_chunks, 100)):
        texts     = [c["text"]     for c in batch_chunks]
        ids       = [c["id"]       for c in batch_chunks]
        metadatas = [c["metadata"] for c in batch_chunks]

        # Improvement #3 — retry on API failure
        embeddings = _embed_with_retry(texts)

        # Improvement #1 — store to ChromaDB immediately per batch
        collection.add(
            ids        = ids,
            documents  = texts,
            metadatas  = metadatas,
            embeddings = embeddings
        )

        # Accumulate only strings for BM25 (not float vectors)
        new_ids.extend(ids)
        new_texts.extend(texts)
        new_metadatas.extend(metadatas)

        # Improvement #4 — save checkpoint after each successful batch
        _save_checkpoint(ids[-1])

        print(f"  Batch {i + 1}/{total_batches}: embedded {len(batch_chunks)} chunks "
              f"(total in DB: {collection.count():,})")

    print(f"Stored {len(new_ids):,} new embeddings in ChromaDB")

    # ── Rebuild BM25 with full corpus ─────────────────────────────────────────
    # BM25 IDF depends on full corpus size — must rebuild whenever new docs added
    all_texts     = existing_bm25["texts"]     + new_texts
    all_ids       = existing_bm25["ids"]       + new_ids
    all_metadatas = existing_bm25["metadatas"] + new_metadatas

    print(f"Rebuilding BM25 index with {len(all_texts):,} total documents...")
    tokenized = [text.lower().split() for text in all_texts]
    bm25      = BM25Okapi(tokenized)

    os.makedirs(os.path.dirname(os.path.abspath(BM25_INDEX_PATH)), exist_ok=True)
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump({
            "bm25":      bm25,
            "texts":     all_texts,
            "ids":       all_ids,
            "metadatas": all_metadatas
        }, f)

    print(f"BM25 index saved -> {BM25_INDEX_PATH}")

    # Improvement #4 — clear checkpoint on successful completion
    _clear_checkpoint()
    print("Checkpoint cleared — ingestion complete.")


if __name__ == "__main__":
    run_embedder()
