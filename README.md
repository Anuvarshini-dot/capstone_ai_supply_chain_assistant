# AI-Powered Supply Chain Risk Intelligence Assistant

An AI-powered system for supply chain risk analysis using hybrid RAG, multi-agent orchestration, and explainable recommendations.

---

## Project Structure

```
capstone_ai_supply_chain_assistant/
├── backend/          # FastAPI + Python
└── frontend/         # React app
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

Configure `backend/.env` (already pre-filled with gateway credentials):
```
OPENAI_API_KEY=learner013
OPENAI_BASE_URL=https://keygateway.arshnivlabs.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

### Step 1 — Ingest the Dataset

Place `supply_chain_data.csv` in `backend/data/raw/`, then run:

```bash
cd backend
python ingest.py
```

This will:
1. Clean and normalize the CSV
2. Convert each row into a structured text chunk
3. Embed all chunks via the OpenAI gateway
4. Store embeddings in ChromaDB
5. Build and save a BM25 keyword index

### Step 2 — Start the API

```bash
cd backend
uvicorn api.main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

---

## Frontend Setup

```bash
cd frontend
npm install
npm start
```

Runs at: `http://localhost:3000`

---

## API Usage Examples

### Natural Language Query
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Supplier delivery delays are increasing for critical components",
    "top_k": 5
  }'
```

### Query with Filters
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "warehouse inventory approaching stockout",
    "filters": {
      "severity": "high",
      "warehouse_location": "Chicago"
    },
    "top_k": 5
  }'
```

### List Incidents
```bash
curl "http://localhost:8000/api/incidents?severity=high&limit=20"
```

### Get Similar Incidents
```bash
curl -X POST http://localhost:8000/api/incidents/similar \
  -H "Content-Type: application/json" \
  -d '{
    "incident_text": "Supplier delayed shipment causing warehouse shortage",
    "top_k": 5
  }'
```

### Get Recommendations
```bash
curl -X POST http://localhost:8000/api/recommendations \
  -H "Content-Type: application/json" \
  -d '{"query": "how to reduce supplier delivery delays"}'
```

### Health Check
```bash
curl http://localhost:8000/api/health
```

---

## Sample Query & Response

**Query:** "Supplier delivery delays are increasing for critical components"

**Response:**
```json
{
  "answer": "Multiple suppliers are experiencing significant delivery delays averaging 6.2 days...",
  "retrieved_incidents": [...],
  "agent_findings": {
    "supplier": { "risk_level": "high", "findings": [...] },
    "shipment": { "risk_level": "medium", "findings": [...] },
    "inventory": { "risk_level": "high", "findings": [...] }
  },
  "recommendations": [
    {
      "title": "Activate Alternate Supplier Contracts",
      "description": "Engage pre-qualified backup suppliers for critical components...",
      "priority": 1,
      "category": "supplier",
      "evidence": "Supplier risk agent identified 4 high-severity delay incidents",
      "judge_scores": { "actionability": 5, "evidence_grounding": 4, "specificity": 4, "total": 13 }
    }
  ],
  "anomaly_correlations": [
    {
      "type": "supplier_inventory_cascade",
      "description": "Supplier delays correlating with inventory depletion...",
      "severity": "high"
    }
  ],
  "confidence_score": 0.81
}
```

---

## Run DeepEval Evaluation

```bash
cd backend
python -m evaluation.deepeval_tests
```

---

## Architecture

```
CSV Data → Ingestion Pipeline → ChromaDB + BM25 Index
                                        ↓
User Query → Input Validator → Hybrid Search (BM25 + Semantic)
                                        ↓
                                   Reranker
                                        ↓
                            Multi-Agent Orchestrator
                     ↙              ↓              ↘
            Supplier Agent   Shipment Agent   Inventory Agent
                     ↘              ↓              ↙
                         Recommendation Agent
                           (LLM-as-Judge)
                                   ↓
                         FastAPI JSON Response
                                   ↓
                           React Frontend
```

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Vector DB | ChromaDB | Easy local setup, persistent storage |
| Keyword Search | BM25 (rank-bm25) | Exact match for supplier IDs, status codes |
| Hybrid Weights | 0.4 BM25 + 0.6 Semantic | Balanced keyword recall with semantic understanding |
| LLM | gpt-4o-mini via gateway | Cost-efficient, strong reasoning |
| Agent Pattern | Sequential with shared context | Consistent incident set across all agents |
| Validation | LLM-as-judge (3-criterion scoring) | Filters hallucinated or vague recommendations |
