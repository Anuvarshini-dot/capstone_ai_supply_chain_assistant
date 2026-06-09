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


def evaluate_nlsql(query: str, findings: dict, sub_query: str = "") -> dict:
    answer       = findings.get("answer") or findings.get("summary", "")
    sql_queries  = findings.get("sql_queries", [])
    finding_list = findings.get("findings", [])

    # Build a rich output that includes entity names and numbers from the findings list
    data_lines = "; ".join(str(f) for f in finding_list[:8])
    data_output = f"{answer} | {data_lines}" if data_lines else answer

    tc_relevancy = LLMTestCase(
        input=sub_query or query,
        actual_output=data_output[:600],
    )
    tc_data = LLMTestCase(
        input=f"SQL queries executed to answer: {query}",
        actual_output=f"{len(sql_queries)} SQL query/queries run. {data_output[:600]}",
    )

    m1 = GEval(
        name="Answer Relevancy",
        criteria=(
            "Does the SQL result answer address the supply chain query? "
            "Score HIGH if it names specific entities (suppliers, products, warehouses) "
            "with concrete figures (rates, scores, counts). "
            "Score LOW only if entirely vague or off-topic."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_llm,
        threshold=0.6,
        async_mode=False,
    )
    m2 = GEval(
        name="SQL Data Accuracy",
        criteria=(
            "Does the answer include specific supply chain data — entity names, numbers, "
            "percentages, or counts — that would come from a real database query? "
            "Score high if it contains concrete figures and named entities. "
            "Score low if the answer is vague, generic, or missing specific data."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_llm,
        threshold=0.6,
        async_mode=False,
    )

    # Zero-result handling — evaluated when the answer reports 0 or no data
    import re as _re
    answer_lower = answer.lower()
    reports_zero = bool(_re.search(r"\b0\b|no (delayed|shipments?|records?|data|results?)", answer_lower))

    results = {
        "answer_relevancy":  _measure(m1, tc_relevancy),
        "sql_data_accuracy": _measure(m2, tc_data),
    }

    if reports_zero:
        tc_zero = LLMTestCase(
            input=query,
            actual_output=answer,
        )
        m3 = GEval(
            name="Zero Result Handling",
            criteria=(
                "The SQL query returned 0 results or no data. Does the answer handle this correctly? "
                "Score HIGH if the answer: (1) clearly states that no records were found, AND "
                "(2) provides context — e.g. the time period queried may be outside the available "
                "data range, or no shipments matched the filter criteria. "
                "Score LOW if the answer simply states '0' with no explanation, or presents the "
                "zero result as if the situation is normal without noting potential data limitations."
            ),
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
            model=_llm,
            threshold=0.6,
            async_mode=False,
        )
        results["zero_result_handling"] = _measure(m3, tc_zero)

    return results
