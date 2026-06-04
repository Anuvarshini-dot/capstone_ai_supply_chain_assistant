import os
from dotenv import load_dotenv

load_dotenv()

# All relative paths are resolved from this file's directory (backend/)
# so the pipeline works regardless of which directory you run scripts from.
_BASE = os.path.dirname(os.path.abspath(__file__))
def _p(*parts): return os.path.join(_BASE, *parts)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "learner013")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://keygateway.arshnivlabs.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

CHROMA_PERSIST_DIR     = os.getenv("CHROMA_PERSIST_DIR",  _p("data", "chroma_db"))
CHROMA_COLLECTION_NAME = "supply_chain_incidents"

BM25_INDEX_PATH     = os.getenv("BM25_INDEX_PATH",     _p("data", "processed", "bm25_index.pkl"))

RAW_DATA_DIR        = os.getenv("RAW_DATA_DIR",        _p("data", "raw"))
SUPPLIERS_PATH      = os.path.join(RAW_DATA_DIR, "suppliers.csv")
PRODUCTS_PATH       = os.path.join(RAW_DATA_DIR, "products.csv")
WAREHOUSES_PATH     = os.path.join(RAW_DATA_DIR, "warehouses.csv")
INVENTORY_PATH      = os.path.join(RAW_DATA_DIR, "inventory.csv")
SHIPMENTS_PATH      = os.path.join(RAW_DATA_DIR, "shipments.csv")

PROCESSED_DATA_PATH   = os.getenv("PROCESSED_DATA_PATH",  _p("data", "processed"))
CLEANED_RECORDS_PATH  = os.path.join(PROCESSED_DATA_PATH, "cleaned_records.jsonl")
CHUNKS_PATH           = os.path.join(PROCESSED_DATA_PATH, "chunks.jsonl")
EMBED_CHECKPOINT_PATH = os.path.join(PROCESSED_DATA_PATH, "embed_checkpoint.txt")
SQLITE_DB_PATH        = os.getenv("SQLITE_DB_PATH",       _p("data", "supply_chain.db"))

BM25_WEIGHT = float(os.getenv("BM25_WEIGHT", "0.4"))
SEMANTIC_WEIGHT = float(os.getenv("SEMANTIC_WEIGHT", "0.6"))

DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "5"))
RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", "20"))

SEVERITY_LOW_THRESHOLD = float(os.getenv("SEVERITY_LOW_THRESHOLD", "2.0"))
SEVERITY_HIGH_THRESHOLD = float(os.getenv("SEVERITY_HIGH_THRESHOLD", "5.0"))

JUDGE_SCORE_THRESHOLD = int(os.getenv("JUDGE_SCORE_THRESHOLD", "3"))

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
