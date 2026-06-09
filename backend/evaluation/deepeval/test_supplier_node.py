import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import GEval
from evaluation.deepeval.gateway_llm import GatewayLLM

_llm = GatewayLLM()


def _measure(metric, test_case):
    metric.measure(test_case)
    return {
        "score":     round(metric.score, 3),
        "passed":    metric.is_successful(),
        "threshold": metric.threshold,
        "reason":    metric.reason or "",
        "details":   {},
    }


def evaluate_supplier(query: str, findings: dict, sub_query: str = "") -> dict:
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
        input=sub_query or query,
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
    m2 = GEval(
        name="Finding Relevance",
        criteria=(
            "Do the supplier findings help answer the user's query? "
            "This is a supply chain risk assistant — each finding typically covers ONE aspect "
            "of a supplier: delay rate, defect rate, inventory impact, risk tier, or reliability. "
            "Score HIGH if the findings name specific suppliers and cite at least one concrete "
            "metric or risk factor per finding. "
            "Score LOW only if findings are entirely vague, contain no supplier names, "
            "or are completely unrelated to the query. "
            "Do NOT require every finding to cover all dimensions — partial, specific findings "
            "are correct and expected."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_llm,
        threshold=0.6,
        async_mode=False,
    )

    m3 = GEval(
        name="Data Specificity",
        criteria=(
            "Do the supplier findings reference specific supplier names AND at least one concrete "
            "metric such as on-time delivery rate, defect rate, delay days, reliability score, "
            "risk tier, or lead time? "
            "Score HIGH if findings name actual suppliers with real numbers or risk labels. "
            "Score LOW if findings are generic statements with no named suppliers or no figures."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_llm,
        threshold=0.6,
        async_mode=False,
    )

    return {
        "risk_assessment_quality": _measure(m1, tc_risk),
        "finding_relevance":       _measure(m2, tc_findings),
        "data_specificity":        _measure(m3, tc_findings),
    }
