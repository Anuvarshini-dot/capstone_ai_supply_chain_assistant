# AI-Powered Supply Chain Risk Intelligence Assistant

An AI system for supply chain risk analysis using hybrid RAG, NL-to-SQL, multi-agent orchestration, and LLM-based evaluation.

---

## Project Structure

```
capstone_ai_supply_chain_assistant/
├── backend/
│   ├── agents/              # Specialist agents (supplier, shipment, inventory, nlsql, summary, recommendation)
│   ├── api/                 # FastAPI routes and schemas
│   ├── data/                # SQLite database + ChromaDB vector store + BM25 index
│   ├── evaluation/          # DeepEval metrics pipeline
│   ├── graph/               # LangGraph nodes, state, and builder
│   ├── guardrails/          # Input validation
│   ├── llm/                 # OpenAI client with retry logic
│   ├── retrieval/           # Hybrid search, BM25, vector store, reranker
│   └── ingest.py            # One-time data ingestion script
└── frontend/                # React app
```

---

## Prerequisites

- Python 3.10+
- Node.js 18+
- `supply_chain_data.csv` placed in `backend/data/raw/`

---

## Backend Setup

```bash
cd backend
pip install -r requirements.txt
```

Configure `backend/.env`:
```
OPENAI_API_KEY=learner013
OPENAI_BASE_URL=https://keygateway.arshnivlabs.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

### Step 1 — Ingest the Dataset

```bash
cd backend
python ingest.py
```

This will:
1. Clean and normalize the CSV
2. Convert each row into structured text chunks (supplier profiles, warehouse profiles, shipment events)
3. Embed all chunks via `text-embedding-3-small` and store in ChromaDB
4. Build and persist a BM25 keyword index
5. Populate `supply_chain.db` (SQLite) with structured tables

### Step 2 — Start the API

```bash
cd backend
uvicorn api.main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

---

## Frontend Setup

```bash
cd frontend
npm install
npm start
```

Runs at: `http://localhost:3000`

---

## Architecture

```
User Query
    │
    ▼
Input Validator (guardrail — blocks off-topic queries)
    │
    ▼
NL→SQL Agent  ──────────────────────────────────────────┐
(executes SQL on supply_chain.db, extracts entities)    │
    │                                                    │
    ▼                                                    │
Classify Node                                           │
(assigns specialist agents + focused sub-questions)     │
    │                        │                          │
    │ agents assigned        │ SQL sufficient           │
    ▼                        ▼                          │
Orchestrator Node     Recommendation Node              │
  ┌──────────────────────────────────┐                 │
  │ For each agent in order:         │                 │
  │  1. _targeted_docs() — hybrid    │                 │
  │     search filtered by entities  │                 │
  │  2. Rerank docs                  │                 │
  │  3. Run specialist agent         │                 │
  │  4. Accumulate findings          │                 │
  └──────────────────────────────────┘                 │
  Supplier Agent │ Inventory Agent │ Shipment Agent    │
    │                                                  │
    ▼                                                  │
Summary Node ─────────────────────────────────────────┘
(synthesises all findings + anomaly correlation)
    │
    ▼
Recommendation Node (LLM-as-judge scoring)
    │
    ▼
DeepEval Evaluation Pipeline
    │
    ▼
FastAPI JSON Response → React Frontend
```

---

## Retrieval Pipeline

### Hybrid Search
Combines two independent search methods and fuses their scores:

```
hybrid_score = 0.4 × BM25_score + 0.6 × semantic_score
```

- **BM25** (weight 0.4): keyword matching — good for exact supplier names, product codes
- **Semantic** (weight 0.6): ChromaDB cosine similarity — good for meaning-based queries
- Each search fetches `RERANK_TOP_N = 20` candidates before fusion

### Reranker
Score-based reranker applied after hybrid search:

```
rerank_score = 0.7 × hybrid_score + 0.2 × term_overlap + 0.1 × severity_boost
```

- `term_overlap`: fraction of query words found in the document text
- `severity_boost`: +0.1 for high-severity incidents, +0.05 for medium

### Document Merge (8-slot)
For each agent, up to 8 documents are assembled:
- Profile docs (supplier/warehouse) fill first — guaranteed slots
- Reranked shipment events fill remaining slots (minimum 2 guaranteed)

---

## Models & Configuration

| Parameter | Value |
|---|---|
| Chat model | `gpt-4o-mini` |
| Embedding model | `text-embedding-3-small` |
| Temperature (agents) | `0.3` |
| Temperature (tool calls) | `0.1` |
| Max tokens (gateway limit) | `500` |
| BM25 weight | `0.4` |
| Semantic weight | `0.6` |
| RERANK_TOP_N | `20` |
| DEFAULT_TOP_K | `5` |
| Severity high threshold | `> 5.0` delay days |
| Severity low threshold | `< 2.0` delay days |

---

## Dataset

- **Date range**: 2022-01-01 to 2024-12-31
- **Structured store**: SQLite (`supply_chain.db`) — suppliers, products, warehouses, inventory, shipments tables
- **Vector store**: ChromaDB — supplier profiles, warehouse profiles, shipment event documents
- **Total delayed shipments**: 1,047 across the full dataset

> Note: Queries filtered to "last month" or dates after 2024 will return 0 results from SQL — the dataset does not include 2025/2026 data.

---

## Sample Queries

### Multi-agent (all 3 specialists)
```
"Which suppliers are at risk and how is it affecting our inventory and shipments?"
"Give me a full supply chain health check"
"What are the biggest risks in our supply chain right now?"
```

### SQL-only (no specialists needed)
```
"How many shipments were delayed in 2024?"
"What is the average delivery delay across all suppliers?"
```

### Single specialist
```
"Which warehouses have critical inventory levels?"         # inventory
"Which shipping routes are causing the most delays?"       # shipment
"Which suppliers have the highest defect rates?"           # supplier
```

### Guardrail test
```
"What is the weather today?"    # blocked as off-topic
```

---

## API Usage

### Natural Language Query
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Which suppliers are at risk?", "top_k": 5}'
```

### Query with Filters
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "warehouse inventory approaching stockout",
    "filters": {"severity": "high"},
    "top_k": 5
  }'
```

### Health Check
```bash
curl http://localhost:8000/api/health
```

---

## Evaluation Framework

Evaluation runs automatically on every query. Metrics are returned in the `evaluation` field of the response.

### Pipeline Metrics (always run)
| Metric | Method | Threshold |
|---|---|---|
| `retrieval_quality` | Avg hybrid score of retrieved docs | > 0.3 |
| `context_coverage` | Distinct doc types retrieved | ≥ 1 type |
| `sql_answer_consistency` | SQL numbers present in final answer | ≥ 0.5 |
| `zero_result_handling` | Zero results explained with context | ≥ 0.5 |
| `answer_relevancy` | GEval (LLM-based) | > 0.6 |
| `faithfulness` | FaithfulnessMetric — hallucination check | > 0.7 |
| `contextual_relevancy` | GEval (LLM-based) | > 0.5 |

### Per-Agent Metrics
| Agent | Metrics |
|---|---|
| Supplier | `risk_assessment_quality`, `finding_relevance`, `data_specificity` |
| Inventory | `inventory_assessment_quality`, `finding_relevance`, `data_specificity` |
| Shipment | `delay_analysis_quality`, `finding_relevance`, `data_specificity` |
| NL→SQL | `answer_relevancy`, `sql_data_accuracy`, `zero_result_handling` (when applicable) |

### Summary Metrics
| Metric | What it checks |
|---|---|
| `answer_relevancy` | Does the answer address the query? |
| `answer_completeness` | Are all agent insights reflected? |
| `conciseness` | Is the answer free of repetition? |
| `sql_agent_consistency` | When SQL and agents disagree, is the discrepancy acknowledged? (runs only when both SQL and specialists ran) |

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Vector DB | ChromaDB | Local persistent storage, no external service |
| Keyword search | BM25 (rank-bm25) | Exact match for supplier names, product codes |
| Hybrid weights | 0.4 BM25 + 0.6 semantic | Supply chain queries are natural language — semantic wins |
| Reranker | Score-based heuristic | Domain-specific severity boost; no extra API cost |
| Chat model | gpt-4o-mini | Cost-efficient, fast, strong reasoning for structured JSON outputs |
| Embedding model | text-embedding-3-small | 1536 dimensions, good quality, low cost per call |
| Structured data | SQLite | Lightweight, file-based, sufficient for supply chain tables |
| SQL loop | 3-iteration max, 25 row preview | Prevents gateway 413 (request too large) errors |
| Retry logic | 2 retries + 1.5s backoff | Handles transient gateway timeouts and 500 errors |
| Agent ordering | Sequential with accumulated findings | Each agent sees prior agents' results — richer analysis |
| Sub-questions | Per-agent focused query from classify node | Each agent retrieves and evaluates for its own scope |
