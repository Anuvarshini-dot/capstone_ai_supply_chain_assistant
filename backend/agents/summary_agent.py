import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.base_agent import BaseAgent

SUMMARY_SYSTEM = """You are a supply chain intelligence analyst.
You receive a user query and findings from one or more specialized agents.
Write a concise 2-3 sentence summary that directly answers the user's question using the agent findings.

CONSISTENCY RULES — follow these strictly:
- When multiple agents mention different sets of entities (e.g. different supplier lists), pick ONE consistent set for the summary. Do NOT mix entity names from different agent lists into a single combined list that was never stated together.
- If a "nlsql" agent is present, treat its entity names and numbers as the primary ground truth (it ran a direct database query). Use the risk agent's findings to add context (risk tier, delay rate) for those same entities only.
- Never introduce an entity in the summary unless it was present in the data the agents actually retrieved.
- If the agents genuinely disagree on which entities rank highest, acknowledge the primary SQL-derived result and note the risk agent's perspective separately in one clause.

TONE RULES:
- Match the tone to the query — risks/problems → surface risks; top performers → summarise positively then note risks.
- Be specific and factual with numbers (days, %, counts).
- Only answer what was actually asked — do not add topics not present in the query."""


class SummaryAgent(BaseAgent):
    name = "summary"

    def summarize(self, query: str, findings: dict) -> str:
        agent_context = {}
        for k, v in findings.items():
            entry = {"summary": v.get("summary", "")}
            if v.get("findings"):
                entry["key_findings"] = v["findings"][:4]
            if k == "nlsql" and v.get("raw_result"):
                entry["sql_data"] = v["raw_result"][:400]
            agent_context[k] = entry

        return self._call_llm(
            SUMMARY_SYSTEM,
            f"Query: {query}\n\nAgent Findings:\n{json.dumps(agent_context, indent=2)}\n\nGenerate a consistent executive summary."
        )
