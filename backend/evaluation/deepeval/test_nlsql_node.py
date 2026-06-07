import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import GEval, AnswerRelevancyMetric
from evaluation.deepeval.gateway_llm import GatewayLLM

_llm = GatewayLLM()


def _measure(metric, test_case):
    metric.measure(test_case)
    return {"score": round(metric.score, 3), "passed": metric.is_successful(), "reason": metric.reason or ""}


def evaluate_nlsql(query: str, findings: dict) -> dict:
    answer      = findings.get("answer") or findings.get("summary", "")
    sql_queries = findings.get("sql_queries", [])

    tc_relevancy = LLMTestCase(
        input=query,
        actual_output=answer,
    )
    tc_data = LLMTestCase(
        input=f"SQL queries executed to answer: {query}",
        actual_output=f"{len(sql_queries)} SQL query/queries run. Result: {answer[:400]}",
    )

    m1 = AnswerRelevancyMetric(threshold=0.7, model=_llm, async_mode=False)
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

    return {
        "answer_relevancy":  _measure(m1, tc_relevancy),
        "sql_data_accuracy": _measure(m2, tc_data),
    }
