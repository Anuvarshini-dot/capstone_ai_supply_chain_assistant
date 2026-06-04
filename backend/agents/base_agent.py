import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm.client import chat

GENERAL_SYSTEM = """You are a helpful general-purpose assistant.
The user has asked a question that is not related to supply chain management.
Answer it clearly and concisely using your general knowledge."""


class BaseAgent:
    name: str = "base"

    def analyze(self, query: str, incidents: list) -> dict:
        raise NotImplementedError

    def answer_general(self, query: str) -> dict:
        """Handle questions that are not related to supply chain at all."""
        response = self._call_llm(
            GENERAL_SYSTEM,
            f"Question: {query}"
        )
        return {"answer": response, "confidence": 0.8}

    def _format_incidents(self, incidents: list) -> str:
        if not incidents:
            return "No relevant incidents found."
        lines = []
        for i, inc in enumerate(incidents, 1):
            meta = inc.get("metadata", {})
            lines.append(
                f"{i}. [{str(meta.get('severity', '')).upper()}] "
                f"Supplier: {meta.get('supplier_name', 'N/A')} ({meta.get('risk_tier', 'N/A')} risk) | "
                f"Product: {meta.get('product_name', 'N/A')} | "
                f"Status: {meta.get('shipment_status', 'N/A')} | "
                f"Delay: {meta.get('delay_days', 'N/A')}d | "
                f"Warehouse: {meta.get('warehouse_name', 'N/A')} | "
                f"Inventory: {meta.get('inventory_status', 'N/A')} "
                f"({meta.get('stock_level_units', 'N/A')} units, "
                f"{meta.get('days_of_supply', 'N/A')} days supply)\n"
                f"   {inc.get('text', '')}"
            )
        return "\n\n".join(lines)

    def _call_llm(self, system: str, user: str) -> str:
        return chat([
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ])

    def _parse_json(self, response: str, fallback: dict) -> dict:
        import re

        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        cleaned = re.sub(r'```[a-zA-Z]*', '', response)
        cleaned = cleaned.replace('```', '').strip()

        # Strategy 1: parse the cleaned string directly
        try:
            return json.loads(cleaned)
        except Exception as e1:
            print(f"[_parse_json] Strategy 1 failed: {e1}")
            print(f"[_parse_json] cleaned[:200]: {repr(cleaned[:200])}")

        # Strategy 2: extract first { ... } block
        try:
            start = cleaned.find("{")
            end   = cleaned.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(cleaned[start:end])
        except Exception as e2:
            print(f"[_parse_json] Strategy 2 failed: {e2}")
            print(f"[_parse_json] extracted[:200]: {repr(cleaned[start:end][:200])}")

        print(f"[_parse_json] ALL strategies failed. Raw response[:300]: {repr(response[:300])}")
        fallback["raw_response"] = response
        return fallback
