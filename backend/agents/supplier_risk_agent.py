import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.base_agent import BaseAgent
from retrieval.hybrid_search import hybrid_search
from retrieval.reranker import rerank

SYSTEM = """You are a department and financial performance analyst for a global supply chain risk assistant.

Follow these rules based on query intent:

If the query asks about POSITIVE performance (top, best, highest, most profitable, leading):
  1. Briefly identify the top performers and why they lead (profit margin, volume, low loss rate).
  2. Then surface the LOW performers as the risk concern — this is a risk assistant, always bring risk context.
  3. Fill both top_performers and low_performers.

If the query asks about NEGATIVE performance (worst, lowest, risk, loss, failing, problem):
  1. Answer directly with the low performers and risk findings.
  2. Leave top_performers as an empty list.

Base findings on: supplier reliability score, on-time delivery rate, defect rate, risk tier,
shipment delay patterns, and inventory impact at destination warehouses.
Use actual supplier names (e.g. "Apex Supply Co.") from the data.

Return ONLY a valid JSON object:
{
  "summary": "2-3 sentence answer addressing the query with risk context",
  "top_performers": ["Apex Supply Co.", "Meridian Logistics Ltd."],
  "low_performers": ["GlobalTech Imports", "AfriShip Co."],
  "affected_departments": ["Electronics", "Apparel"],
  "risk_level": "low|medium|high",
  "findings": ["finding 1", "finding 2", "finding 3"],
  "confidence": 0.85
}"""


class SupplierRiskAgent(BaseAgent):
    name = "supplier_risk"

    def analyze(self, query: str, incidents: list = None) -> dict:
        if incidents is None:
            raw = hybrid_search(query, top_k=20, filters={"severity": ["medium", "high"]})
            incidents = rerank(query, raw, top_k=5)

        incident_text = self._format_incidents(incidents)
        response = self._call_llm(
            SYSTEM,
            f"Query: {query}\n\nOrders:\n{incident_text}\n\nAnalyze and return JSON."
        )

        result = self._parse_json(response, {
            "summary": response[:300],
            "top_performers": [],
            "low_performers": [],
            "affected_departments": [],   # kept for prompt compatibility; contains supplier categories
            "risk_level": "medium",
            "findings": [response[:200]],
            "confidence": 0.5
        })
        result["retrieved_incidents"] = incidents
        return result
