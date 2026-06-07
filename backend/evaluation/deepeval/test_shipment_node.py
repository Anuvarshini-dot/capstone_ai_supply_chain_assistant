import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import GEval, AnswerRelevancyMetric
from evaluation.deepeval.gateway_llm import GatewayLLM

_llm = GatewayLLM()


def _measure(metric, test_case):
    metric.measure(test_case)
    return {"score": round(metric.score, 3), "passed": metric.is_successful(), "reason": metric.reason or ""}


def evaluate_shipment(query: str, findings: dict) -> dict:
    summary      = findings.get("summary", "")
    risk_level   = findings.get("risk_level", "unknown")
    finding_list = findings.get("findings", [])

    tc_delay = LLMTestCase(
        input=query,
        actual_output=f"Risk level: {risk_level}. Summary: {summary}",
    )
    tc_findings = LLMTestCase(
        input=f"Analyse shipment delays and risks for: {query}",
        actual_output="; ".join(str(f) for f in finding_list[:4]) or summary,
    )

    m1 = GEval(
        name="Delay Analysis Quality",
        criteria=(
            "Does the shipment analysis correctly identify delay patterns, at-risk shipments, "
            "or route/carrier issues? "
            "Score high if it cites specific delay days, carriers, shipping modes, or routes. "
            "Score low if it is vague or fails to address actual shipment performance data."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_llm,
        threshold=0.6,
        async_mode=False,
    )
    m2 = AnswerRelevancyMetric(threshold=0.7, model=_llm, async_mode=False)

    return {
        "delay_analysis_quality": _measure(m1, tc_delay),
        "finding_relevance":      _measure(m2, tc_findings),
    }
