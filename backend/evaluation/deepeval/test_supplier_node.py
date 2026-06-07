import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import GEval, AnswerRelevancyMetric
from evaluation.deepeval.gateway_llm import GatewayLLM

_llm = GatewayLLM()


def _measure(metric, test_case):
    metric.measure(test_case)
    return {"score": round(metric.score, 3), "passed": metric.is_successful(), "reason": metric.reason or ""}


def evaluate_supplier(query: str, findings: dict) -> dict:
    summary     = findings.get("summary", "")
    risk_level  = findings.get("risk_level", "unknown")
    confidence  = findings.get("confidence", 0)
    finding_list = findings.get("findings", [])

    tc_risk = LLMTestCase(
        input=query,
        actual_output=(
            f"Risk level: {risk_level}. Confidence: {round(confidence * 100)}%. "
            f"Summary: {summary}"
        ),
    )
    tc_findings = LLMTestCase(
        input=f"Analyse supplier risk for: {query}",
        actual_output="; ".join(str(f) for f in finding_list[:4]) or summary,
    )

    m1 = GEval(
        name="Risk Assessment Quality",
        criteria=(
            "Does the supplier risk assessment provide specific, data-backed analysis? "
            "Score high if it references concrete metrics such as on-time delivery rate, "
            "defect rate, reliability score, risk tier, or average lead time. "
            "Score low if the analysis is vague or does not cite any supplier-specific data."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_llm,
        threshold=0.6,
        async_mode=False,
    )
    m2 = AnswerRelevancyMetric(threshold=0.7, model=_llm, async_mode=False)

    return {
        "risk_assessment_quality": _measure(m1, tc_risk),
        "finding_relevance":       _measure(m2, tc_findings),
    }
