import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.base_agent import BaseAgent
from retrieval.hybrid_search import hybrid_search
from retrieval.reranker import rerank

SYSTEM = """You are an order fulfillment analyst for a global supply chain risk assistant.

Follow these rules based on query intent:

If the query asks about POSITIVE performance (best, highest fulfillment, top completing, most reliable):
  1. Briefly identify the best-completing products or regions.
  2. Then surface the LOW-FULFILLMENT products/regions as the risk concern — this is a risk assistant.
  3. Fill both top_fulfillment and low_fulfillment.

If the query asks about NEGATIVE performance (worst, lowest, failing, canceled, risk, problem):
  1. Answer directly with the low-fulfillment products/regions.
  2. Leave top_fulfillment as an empty list.

Base findings on: product fulfillment rate, order status (COMPLETE vs PENDING vs CANCELED), and cancellation patterns by product or region.

Use ONLY product names from the provided orders data — never invent or use placeholder names.

Return ONLY a valid JSON object:
{
  "summary": "2-3 sentence answer addressing the query with risk context",
  "top_fulfillment": ["<actual product name from data>"],
  "low_fulfillment": ["<actual product name from data>"],
  "at_risk_products": ["<actual product name from data>"],
  "risk_level": "low|medium|high",
  "findings": ["finding 1", "finding 2", "finding 3"],
  "avg_fulfillment_rate": 0.85,
  "confidence": 0.85
}"""


class InventoryAgent(BaseAgent):
    name = "inventory"

    def analyze(self, query: str, incidents: list = None) -> dict:
        if incidents is None:
            raw = hybrid_search(query, top_k=20)
            # Filter for records with low/critical/stockout inventory status or low days of supply
            at_risk = [
                h for h in raw
                if h["metadata"].get("inventory_status") in ("low", "critical", "stockout")
                or float(h["metadata"].get("days_of_supply", 99)) < 14
            ]
            incidents = rerank(query, at_risk if at_risk else raw, top_k=5)

        incident_text = self._format_incidents(incidents)
        response = self._call_llm(
            SYSTEM,
            f"Query: {query}\n\nOrders:\n{incident_text}\n\nAnalyze and return JSON."
        )

        result = self._parse_json(response, {
            "summary": response[:300],
            "top_fulfillment": [],
            "low_fulfillment": [],
            "at_risk_products": [],
            "risk_level": "medium",
            "findings": [response[:200]],
            "avg_fulfillment_rate": 0.5,
            "confidence": 0.5
        })
        result["retrieved_incidents"] = incidents
        return result
