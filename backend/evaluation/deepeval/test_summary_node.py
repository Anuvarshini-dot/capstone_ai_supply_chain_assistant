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

    m1 = GEval(
        name="Answer Relevancy",
        criteria=(
            "Does the answer address the user's supply chain query? "
            "This assistant produces comprehensive answers that combine the direct response "
            "WITH relevant risk context — supplier risk tiers, inventory levels, delay patterns, "
            "and actionable recommendations are all expected alongside the direct answer. "
            "Score HIGH if the answer directly addresses the query and provides useful supply "
            "chain context. "
            "Score LOW only if the answer completely ignores the question or is entirely off-topic. "
            "Do NOT penalise for including supplier risk, inventory data, or recommendations "
            "alongside the direct answer — that is expected and valuable."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_llm,
        threshold=0.6,
        async_mode=False,
    )

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

    results = {
        "answer_relevancy":    _measure(m1, tc_relevancy),
        "answer_completeness": _measure(m2, tc_completeness),
        "conciseness":         _measure(m3, tc_conciseness),
    }

    # SQL vs agent consistency — only evaluated when both SQL and specialist agents ran
    has_sql        = "nlsql" in agent_findings
    has_specialist = any(k in agent_findings for k in ("supplier", "shipment", "inventory"))
    if has_sql and has_specialist:
        sql_summary       = (agent_findings.get("nlsql") or {}).get("summary", "")
        specialist_summaries = " | ".join(
            (agent_findings.get(k) or {}).get("summary", "")
            for k in ("supplier", "shipment", "inventory")
            if k in agent_findings
        )
        tc_consistency = LLMTestCase(
            input=(
                f"SQL result: {sql_summary}\n"
                f"Specialist agent findings: {specialist_summaries}\n"
                f"Final answer for query: {query}"
            ),
            actual_output=answer[:600],
        )
        m4 = GEval(
            name="SQL Agent Consistency",
            criteria=(
                "When the SQL result and specialist agent findings report different numbers or "
                "conclusions, does the final answer acknowledge the discrepancy or reconcile them? "
                "Score HIGH if: the answer correctly synthesises both sources, OR clearly states "
                "which source is more reliable and why, OR notes a data gap (e.g. SQL covers a "
                "time period with no records while agents use historical vector data). "
                "Score LOW if the answer silently contradicts itself — e.g. SQL says 0 but the "
                "answer presents agent findings as if they are current without explanation."
            ),
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
            model=_llm,
            threshold=0.6,
            async_mode=False,
        )
        results["sql_agent_consistency"] = _measure(m4, tc_consistency)

    return results
