import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import GEval, AnswerRelevancyMetric
from evaluation.deepeval.gateway_llm import GatewayLLM

_llm = GatewayLLM()


def _measure(metric, test_case):
    metric.measure(test_case)
    return {"score": round(metric.score, 3), "passed": metric.is_successful(), "reason": metric.reason or ""}


def evaluate_inventory(query: str, findings: dict) -> dict:
    summary      = findings.get("summary", "")
    risk_level   = findings.get("risk_level", "unknown")
    finding_list = findings.get("findings", [])
    top_items    = findings.get("top_fulfillment", [])
    low_items    = findings.get("low_fulfillment", [])

    tc_analysis = LLMTestCase(
        input=query,
        actual_output=(
            f"Risk level: {risk_level}. Summary: {summary}. "
            f"High fulfillment: {top_items}. Low fulfillment: {low_items}."
        ),
    )
    tc_findings = LLMTestCase(
        input=f"Analyse inventory status for: {query}",
        actual_output="; ".join(str(f) for f in finding_list[:4]) or summary,
    )

    m1 = GEval(
        name="Inventory Assessment Quality",
        criteria=(
            "Does the inventory assessment correctly identify stock levels, warehouse status, "
            "days of supply, or stockout risks? "
            "Score high if it names specific products or warehouses with concrete figures. "
            "Score low if it is generic or does not address actual inventory conditions."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_llm,
        threshold=0.6,
        async_mode=False,
    )
    m2 = AnswerRelevancyMetric(threshold=0.7, model=_llm, async_mode=False)

    return {
        "inventory_assessment_quality": _measure(m1, tc_analysis),
        "finding_relevance":            _measure(m2, tc_findings),
    }
