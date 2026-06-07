import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import GEval, AnswerRelevancyMetric
from evaluation.deepeval.gateway_llm import GatewayLLM

_llm = GatewayLLM()


def _measure(metric, test_case):
    metric.measure(test_case)
    return {"score": round(metric.score, 3), "passed": metric.is_successful(), "reason": metric.reason or ""}


def evaluate_summary(query: str, answer: str, agent_findings: dict) -> dict:
    agents_used = [k for k in agent_findings if k not in ("nlsql",)]

    tc_relevancy = LLMTestCase(
        input=query,
        actual_output=answer,
    )
    tc_completeness = LLMTestCase(
        input=(
            f"Summarise findings from agents [{', '.join(agents_used)}] "
            f"for query: {query}"
        ),
        actual_output=answer[:600],
    )
    tc_conciseness = LLMTestCase(
        input=query,
        actual_output=answer,
    )

    m1 = AnswerRelevancyMetric(threshold=0.7, model=_llm, async_mode=False)

    m2 = GEval(
        name="Answer Completeness",
        criteria=(
            f"The answer should incorporate key insights from all agents that ran: "
            f"{', '.join(agents_used) or 'nlsql'}. "
            "Score high if the answer reflects findings from each agent (supplier risk, "
            "inventory status, shipment delays as applicable). "
            "Score low if important agent insights are missing or ignored."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_llm,
        threshold=0.6,
        async_mode=False,
    )

    m3 = GEval(
        name="Conciseness",
        criteria=(
            "Is the answer clear, well-structured, and free of unnecessary repetition? "
            "Score high for focused, actionable answers that directly address the query. "
            "Score low for verbose, repetitive, or padded responses."
        ),
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
        model=_llm,
        threshold=0.6,
        async_mode=False,
    )

    return {
        "answer_relevancy":   _measure(m1, tc_relevancy),
        "answer_completeness": _measure(m2, tc_completeness),
        "conciseness":         _measure(m3, tc_conciseness),
    }
