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


def evaluate_inventory(query: str, findings: dict, sub_query: str = "") -> dict:
    summary          = findings.get("summary", "")
    risk_level       = findings.get("risk_level", "unknown")
    finding_list     = findings.get("findings", [])
    top_items        = findings.get("top_fulfillment", [])
    low_items        = findings.get("low_fulfillment", [])
    at_risk_products = findings.get("at_risk_products", [])
    avg_rate         = findings.get("avg_fulfillment_rate", None)

    rate_str = f" Avg fulfillment rate: {round(avg_rate * 100)}%." if avg_rate else ""
    risk_str = (
        f" At-risk products: {', '.join(str(p) for p in at_risk_products[:3])}."
        if at_risk_products else ""
    )

    tc_analysis = LLMTestCase(
        input=query,
        actual_output=(
            f"Risk level: {risk_level}. {summary}"
            f" High fulfillment: {top_items[:3]}. Low fulfillment: {low_items[:3]}."
            f"{rate_str}{risk_str}"
        ),
    )
    tc_findings = LLMTestCase(
        input=sub_query or query,
        actual_output="; ".join(str(f) for f in finding_list[:4]) or summary,
    )

    m1 = GEval(
        name="Inventory Assessment Quality",
        criteria=(
            "Does the inventory assessment correctly identify stock levels, warehouse status, "
            "days of supply, fulfillment rates, or stockout risks? "
            "Score high if it names specific products or warehouses with concrete figures "
            "such as fulfillment rates, stock counts, or days of supply. "
            "Score low if it is generic or does not address actual inventory conditions."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_llm,
        threshold=0.6,
        async_mode=False,
    )
    m2 = GEval(
        name="Finding Relevance",
        criteria=(
            "Do the inventory findings help answer the user's query? "
            "This is a supply chain risk assistant — findings typically reference specific "
            "products, fulfillment rates, stockout status, cancellation patterns, or "
            "warehouse-level inventory data. "
            "Score HIGH if findings name actual products or warehouses with stock data, "
            "fulfillment rates, or at-risk inventory status. "
            "Score LOW only if findings are entirely vague or contain no inventory-specific data. "
            "Do NOT penalise for including risk context such as cancellation risk, "
            "low stock alerts, or supplier impact alongside the inventory findings."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_llm,
        threshold=0.6,
        async_mode=False,
    )

    m3 = GEval(
        name="Data Specificity",
        criteria=(
            "Do the inventory findings reference specific warehouse or product names AND at least "
            "one concrete metric such as stock count, days of supply, fulfillment rate, or "
            "stockout status? "
            "Score HIGH if findings name actual warehouses or products with real figures. "
            "Score LOW if findings are generic with no named locations or no inventory numbers."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_llm,
        threshold=0.6,
        async_mode=False,
    )

    return {
        "inventory_assessment_quality": _measure(m1, tc_analysis),
        "finding_relevance":            _measure(m2, tc_findings),
        "data_specificity":             _measure(m3, tc_findings),
    }
