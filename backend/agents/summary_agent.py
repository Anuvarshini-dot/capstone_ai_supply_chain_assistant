import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.base_agent import BaseAgent

SUMMARY_SYSTEM = """You are a supply chain intelligence analyst.
You receive a user query and findings from one or more specialized agents.
Write a concise 2-3 sentence summary that directly answers the user's question using the agent findings.
Match the tone to the query — if the user asked about top performers, summarise positively;
if they asked about risks or problems, summarise the risks. Be specific and factual.
Only answer what was actually asked — do not add information about topics not present in the query."""


class SummaryAgent(BaseAgent):
    name = "summary"

    def summarize(self, query: str, findings: dict) -> str:
        summaries = {k: v.get("summary", "") for k, v in findings.items()}
        return self._call_llm(
            SUMMARY_SYSTEM,
            f"Query: {query}\n\nAgent Summaries:\n{json.dumps(summaries, indent=2)}\n\nGenerate executive summary."
        )
