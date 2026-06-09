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


def evaluate_shipment(query: str, findings: dict, sub_query: str = "") -> dict:
    summary      = findings.get("summary", "")
    risk_level   = findings.get("risk_level", "unknown")
    finding_list = findings.get("findings", [])
    best_routes  = findings.get("best_routes", [])
    worst_routes = findings.get("worst_routes", [])

    route_context = ""
    if best_routes:
        route_context += f" Best routes: {', '.join(str(r) for r in best_routes[:3])}."
    if worst_routes:
        route_context += f" Problem routes: {', '.join(str(r) for r in worst_routes[:3])}."

    tc_delay = LLMTestCase(
        input=query,
        actual_output=f"Risk level: {risk_level}. {summary}{route_context}",
    )
    tc_findings = LLMTestCase(
        input=sub_query or query,
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
    m2 = GEval(
        name="Finding Relevance",
        criteria=(
            "Do the shipment findings help answer the user's query? "
            "This is a supply chain risk assistant — findings are expected to reference "
            "specific routes, carriers, shipping modes, delay days, or affected regions. "
            "Score HIGH if findings name specific routes or carriers with concrete delay or "
            "performance data. "
            "Score LOW only if findings are entirely vague or contain no logistics-specific data. "
            "Do NOT penalise for including inventory impact, risk context, or route comparisons "
            "alongside the delay findings — that is correct behaviour for this assistant."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_llm,
        threshold=0.6,
        async_mode=False,
    )

    m3 = GEval(
        name="Data Specificity",
        criteria=(
            "Do the shipment findings reference specific routes, carriers, or warehouses AND at "
            "least one concrete metric such as delay days, number of delayed shipments, on-time "
            "rate, or risk score? "
            "Score HIGH if findings name actual routes or carriers with real delay figures. "
            "Score LOW if findings are generic with no named routes, carriers, or delay numbers."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_llm,
        threshold=0.6,
        async_mode=False,
    )

    return {
        "delay_analysis_quality": _measure(m1, tc_delay),
        "finding_relevance":      _measure(m2, tc_findings),
        "data_specificity":       _measure(m3, tc_findings),
    }
