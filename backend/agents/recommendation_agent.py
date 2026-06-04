import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.base_agent import BaseAgent
from llm.client import chat
from config import JUDGE_SCORE_THRESHOLD

SYSTEM = """You are a supply chain risk mitigation expert.
You will receive findings from one or more agents. Findings may come from:
- Specialist agents (supplier, shipment, inventory) with risk analysis
- An NL-to-SQL agent (nlsql) with analytical query results

Your job: ALWAYS generate exactly 3 prioritized, actionable recommendations based on the findings.
- For risk findings: focus on improving low performers or fixing identified risks.
- For analytical/SQL findings: recommend actions to improve, monitor, or act on the data shown.
- Always be specific — reference actual numbers, warehouse names, or supplier names from the findings.

Return ONLY a valid JSON object:
{
  "recommendations": [
    {
      "title": "Short action title",
      "description": "2-3 sentences explaining what to do and why, referencing specific findings",
      "priority": 1,
      "category": "supplier|shipment|fulfillment|inventory|cross-functional",
      "evidence": "Which specific finding or metric supports this recommendation"
    }
  ]
}"""

JUDGE_SYSTEM = """You are a quality evaluator for supply chain recommendations.
Score the recommendation on three criteria (each 1-5):
1. Actionability: Can a supply chain team act on this immediately?
2. Evidence grounding: Is it clearly supported by the data?
3. Specificity: Is it specific rather than generic advice?

Return ONLY valid JSON:
{
  "actionability": 4,
  "evidence_grounding": 3,
  "specificity": 4,
  "total": 11,
  "rationale": "one sentence"
}"""


class RecommendationAgent(BaseAgent):
    name = "recommendation"

    def analyze(self, query: str, agent_findings: dict) -> dict:
        findings_text = json.dumps(
            {k: {kk: vv for kk, vv in v.items() if kk != "retrieved_incidents"}
             for k, v in agent_findings.items()},
            indent=2
        )

        response = self._call_llm(
            SYSTEM,
            f"Query: {query}\n\nAgent Findings:\n{findings_text}\n\nGenerate 3 mitigation recommendations as JSON."
        )

        parsed = self._parse_json(response, {"recommendations": []})
        recommendations = parsed.get("recommendations", [])

        validated = []
        for rec in recommendations:
            score = self._judge(rec, findings_text)
            rec["judge_scores"] = score
            if score.get("total", 0) >= JUDGE_SCORE_THRESHOLD * 3:
                validated.append(rec)

        return {"recommendations": validated if validated else recommendations}

    def _judge(self, recommendation: dict, context: str) -> dict:
        rec_text = json.dumps(recommendation)
        response = chat([
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": f"Recommendation:\n{rec_text}\n\nContext:\n{context[:1000]}\n\nScore as JSON."}
        ])
        return self._parse_json(response, {
            "actionability": 3,
            "evidence_grounding": 3,
            "specificity": 3,
            "total": 9,
            "rationale": "Default score"
        })
