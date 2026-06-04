"""
Ingestion pipeline — builds ChromaDB + BM25 index + SQLite DB from the 5 raw CSVs.

Documents stored in ChromaDB (3065 total):
  - 3000 shipment event chunks    (doc_type: shipment)
  -   50 supplier profile chunks  (doc_type: supplier_profile)
  -   15 warehouse profile chunks (doc_type: warehouse_profile)

SQLite DB (supply_chain.db):
  - 5 tables: suppliers, products, warehouses, inventory, shipments
  - Used by the NL-to-SQL agent for precise analytical queries

Usage:
    python ingest.py                # incremental — only new shipment rows
    python ingest.py --mode full    # wipe everything and rebuild from scratch
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingestion.loader          import load_and_clean
from ingestion.chunker         import build_chunks
from ingestion.profile_builder import build_supplier_profiles, build_warehouse_profiles
from ingestion.db_builder      import build_sqlite_db
from ingestion.embedder        import run_embedder
from retrieval.vector_store    import get_collection


def get_mode() -> str:
    if "--mode" in sys.argv:
        idx = sys.argv.index("--mode")
        if idx + 1 < len(sys.argv):
            mode = sys.argv[idx + 1].lower()
            if mode in ("full", "incremental"):
                return mode
            print(f"Unknown mode '{mode}'. Defaulting to incremental.")
    return "incremental"


if __name__ == "__main__":
    mode = get_mode()

    print("=" * 55)
    print(f"Supply Chain Ingestion Pipeline  [mode: {mode}]")
    print("=" * 55)

    # ── Step 1: Flat shipment records ────────────────────────────
    print("\nStep 1: Loading and joining CSVs...")
    new_records = load_and_clean(mode=mode)

    if not new_records and mode == "incremental":
        print("\nNo new shipment rows to process.")
    else:
        # ── Step 2: Shipment event chunks ────────────────────────
        print(f"\nStep 2: Building shipment chunks ({len(new_records):,} records)...")
        shipment_chunks = build_chunks(new_records, mode=mode)

        # ── Step 3: Supplier profiles (always full rebuild) ──────
        print("\nStep 3: Building supplier profiles...")
        supplier_chunks = build_supplier_profiles()

        # ── Step 4: Warehouse profiles (always full rebuild) ─────
        print("\nStep 4: Building warehouse profiles...")
        warehouse_chunks = build_warehouse_profiles()

        # ── Step 5: Embed all into ChromaDB + BM25 ───────────────
        # Profiles must always be refreshed (they aggregate from new shipments too).
        # In incremental mode, delete stale profile docs before re-embedding.
        if mode == "incremental":
            profile_ids = [c["id"] for c in supplier_chunks + warehouse_chunks]
            collection  = get_collection()
            existing    = collection.get(ids=profile_ids, include=[])["ids"]
            if existing:
                collection.delete(ids=existing)
                print(f"  Removed {len(existing)} stale profile documents for refresh")

        all_chunks = shipment_chunks + supplier_chunks + warehouse_chunks
        print(f"\nStep 5: Embedding {len(all_chunks):,} total chunks "
              f"({len(shipment_chunks)} shipments + "
              f"{len(supplier_chunks)} supplier profiles + "
              f"{len(warehouse_chunks)} warehouse profiles)...")
        run_embedder(all_chunks, mode=mode)

    # ── Step 6: SQLite DB (always rebuilt) ───────────────────────
    print("\nStep 6: Building SQLite database for NL-to-SQL agent...")
    build_sqlite_db()

    print("\nIngestion complete. System is ready to query.")
