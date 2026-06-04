import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.base_agent import BaseAgent
from retrieval.hybrid_search import hybrid_search
from retrieval.reranker import rerank

SYSTEM = """You are a shipment and logistics analyst for a global supply chain risk assistant.

Follow these rules based on query intent:

If the query asks about POSITIVE performance (best, fastest, on-time, reliable, top routes):
  1. Briefly identify the best-performing routes, shipping modes, or regions.
  2. Then surface the WORST performers as the risk concern — this is a risk assistant, always bring risk context.
  3. Fill both best_routes and worst_routes.

If the query asks about NEGATIVE performance (delayed, late, worst, canceled, risk, problem):
  1. Answer directly with the problem routes/modes/regions.
  2. Leave best_routes as an empty list.

Base findings on: delivery delay, late delivery risk, shipment status, shipping mode, and delivery city/region.

Return ONLY a valid JSON object:
{
  "summary": "2-3 sentence answer addressing the query with risk context",
  "best_routes": ["Europe First Class", "USCA Same Day"],
  "worst_routes": ["LATAM Standard Class", "Africa Second Class"],
  "affected_routes": ["LATAM Standard Class", "Africa Second Class"],
  "risk_level": "low|medium|high",
  "findings": ["finding 1", "finding 2", "finding 3"],
  "confidence": 0.85
}"""


class ShipmentAgent(BaseAgent):
    name = "shipment"

    def analyze(self, query: str, incidents: list = None) -> dict:
        if incidents is None:
            raw = hybrid_search(
                query, top_k=20,
                filters={"shipment_status": ["late_delivery", "shipping_canceled"]}
            )
            incidents = rerank(query, raw, top_k=5)

        incident_text = self._format_incidents(incidents)
        response = self._call_llm(
            SYSTEM,
            f"Query: {query}\n\nOrders:\n{incident_text}\n\nAnalyze and return JSON."
        )

        result = self._parse_json(response, {
            "summary": response[:300],
            "best_routes": [],
            "worst_routes": [],
            "affected_routes": [],
            "risk_level": "medium",
            "findings": [response[:200]],
            "confidence": 0.5
        })
        result["retrieved_incidents"] = incidents
        return result
