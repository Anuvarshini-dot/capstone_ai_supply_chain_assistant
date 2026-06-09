"""
Per-query evaluation runner for the supply chain risk assessment assistant.

Five metrics always run:
  retrieval_quality    – avg hybrid score                        (non-LLM)
  context_coverage     – distinct doc-type breadth               (non-LLM)
  answer_relevancy     – query ↔ final answer                    (DeepEval)
  faithfulness         – hallucination check vs retrieved context (DeepEval)
  contextual_relevancy – query ↔ retrieved context               (DeepEval)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Non-LLM helpers ───────────────────────────────────────────────────────────

def _retrieval_quality(retrieved_docs: list) -> dict:
    hybrid_scores   = [d.get("hybrid_score",  0) for d in retrieved_docs]
    semantic_scores = [d.get("semantic_score", 0) for d in retrieved_docs]
    avg_hybrid      = round(sum(hybrid_scores)   / len(hybrid_scores),   3)
    avg_semantic    = round(sum(semantic_scores) / len(semantic_scores), 3)
    top_hybrid      = round(max(hybrid_scores), 3)
    high_quality    = sum(1 for s in hybrid_scores if s > 0.5)

    return {
        "score":     avg_hybrid,
        "passed":    avg_hybrid > 0.3,
        "threshold": 0.3,
        "reason": (
            f"{len(retrieved_docs)} docs · avg hybrid {avg_hybrid} · "
            f"avg semantic {avg_semantic} · {high_quality} doc(s) above 0.5"
        ),
        "details": {
            "num_docs":          len(retrieved_docs),
            "avg_semantic":      avg_semantic,
            "top_hybrid_score":  top_hybrid,
            "high_quality_docs": high_quality,
        },
    }


def _sql_answer_consistency(sql_data: str, answer: str) -> dict:
    """Non-LLM: checks whether the number SQL returned appears in the final answer."""
    import re
    sql_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", sql_data)
    answer_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", answer)
    if not sql_numbers:
        return {
            "score": 1.0, "passed": True, "threshold": 0.5,
            "reason": "No numeric values in SQL output — consistency check skipped.",
            "details": {},
        }
    matched = [n for n in sql_numbers[:5] if n in answer_numbers]
    score   = round(len(matched) / len(sql_numbers[:5]), 3)
    return {
        "score":     score,
        "passed":    score >= 0.5,
        "threshold": 0.5,
        "reason": (
            f"{len(matched)}/{len(sql_numbers[:5])} SQL number(s) found in answer. "
            f"SQL had: {sql_numbers[:5]}"
        ),
        "details": {"sql_numbers": sql_numbers[:5], "matched": matched},
    }


def _zero_result_handling(sql_data: str, answer: str) -> dict:
    """Non-LLM: when SQL returns 0 or empty rows, checks the answer acknowledges it clearly."""
    import re
    has_zero    = bool(re.search(r"\b0\b", sql_data))
    no_rows     = any(phrase in sql_data.lower() for phrase in ["no rows", "no results", "empty", "[]"])
    is_zero_result = has_zero or no_rows
    if not is_zero_result:
        return {
            "score": 1.0, "passed": True, "threshold": 0.5,
            "reason": "SQL returned non-zero results — zero-result check not applicable.",
            "details": {},
        }
    # Answer should surface the zero and ideally explain why
    answer_lower = answer.lower()
    mentions_zero  = bool(re.search(r"\b0\b|no\s+(delayed|shipments?|records?|data|results?)", answer_lower))
    explains_gap   = any(w in answer_lower for w in [
        "no data", "not available", "outside", "date range", "no records",
        "period", "time range", "not found", "no shipments",
    ])
    if mentions_zero and explains_gap:
        score, reason = 1.0, "Answer correctly reports zero result and explains the data gap."
    elif mentions_zero:
        score, reason = 0.6, "Answer reports zero but does not explain why (e.g., date range gap)."
    else:
        score, reason = 0.0, "Answer does not acknowledge that SQL returned zero results."
    return {
        "score": score, "passed": score >= 0.5, "threshold": 0.5,
        "reason": reason, "details": {"sql_returned_zero": True},
    }


def _context_coverage(retrieved_docs: list) -> dict:
    doc_type_counts: dict = {}
    for d in retrieved_docs:
        dt = d.get("metadata", {}).get("doc_type", "shipment")
        doc_type_counts[dt] = doc_type_counts.get(dt, 0) + 1

    num_types      = len(doc_type_counts)
    coverage_score = round(num_types / 3, 3)
    display_types  = {k.replace("_profile", ""): v for k, v in doc_type_counts.items()}

    return {
        "score":     coverage_score,
        "passed":    num_types >= 1,
        "threshold": 0.33,
        "reason":    f"{num_types} distinct doc type(s): {', '.join(doc_type_counts.keys())}",
        "details":   display_types,
    }


# ── DeepEval pipeline metrics ─────────────────────────────────────────────────

def _deepeval_pipeline_metrics(query: str, answer: str, retrieved_docs: list, sql_data: str = "") -> dict:
    """
    Three LLM-based metrics using domain-aware criteria suited to a multi-agent
    supply chain assistant:
      - answer_relevancy   : GEval that accepts comprehensive answers with risk context
      - faithfulness       : FaithfulnessMetric (standard hallucination check)
      - contextual_relevancy: GEval that understands SQL results as primary context
    """
    try:
        from deepeval.test_case import LLMTestCase, LLMTestCaseParams
        from deepeval.metrics import GEval, FaithfulnessMetric
        from evaluation.deepeval.gateway_llm import GatewayLLM

        _llm      = GatewayLLM()
        doc_texts = [d.get("text", "")[:500] for d in retrieved_docs[:3]]
        context   = ([f"[SQL Results]\n{sql_data}"] + doc_texts) if sql_data else doc_texts

        tc = LLMTestCase(
            input=query,
            actual_output=answer,
            retrieval_context=context,
        )

        # 1 ── Answer Relevancy (GEval, domain-aware)
        m_ar = GEval(
            name="Answer Relevancy",
            criteria=(
                "Does the answer address the user's supply chain query? "
                "This assistant gives comprehensive answers that include the direct answer PLUS "
                "relevant risk context (supplier risk, inventory levels, shipment status) and "
                "actionable recommendations. "
                "Score HIGH (≥0.6) if: the answer directly addresses the main question AND provides "
                "useful supply chain context. "
                "Score LOW only if the answer completely ignores the question or is entirely off-topic. "
                "Do NOT penalise for including supplier risk, inventory data, or recommendations "
                "alongside the direct answer — that is expected and valuable."
            ),
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
            model=_llm,
            threshold=0.6,
            async_mode=False,
        )

        # 2 ── Faithfulness (standard — works well as-is)
        m_f = FaithfulnessMetric(
            threshold=0.7,
            model=_llm,
            async_mode=False,
            truths_extraction_limit=5,
        )

        # 3 ── Contextual Relevancy (GEval, domain-aware)
        m_cr = GEval(
            name="Contextual Relevancy",
            criteria=(
                "Is the retrieved context useful for answering the supply chain query? "
                "Context may include: warehouse profiles (stock levels, capacity, location), "
                "supplier profiles (risk tier, delivery performance, reliability score), "
                "shipment records (delays, routes, carriers), and SQL query results. "
                "Score HIGH (≥0.5) if the context contains data about entities mentioned in the "
                "query (warehouses, suppliers, products, shipments) even if it does not provide "
                "a direct comparison across all entities — partial context is still relevant. "
                "Score LOW only if the context is entirely unrelated to the query topic."
            ),
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.RETRIEVAL_CONTEXT],
            model=_llm,
            threshold=0.5,
            async_mode=False,
        )

        results = {}
        for metric, name, threshold in [
            (m_ar,  "answer_relevancy",     0.6),
            (m_f,   "faithfulness",         0.7),
            (m_cr,  "contextual_relevancy", 0.5),
        ]:
            metric.measure(tc)
            results[name] = {
                "score":     round(metric.score, 3),
                "passed":    metric.is_successful(),
                "threshold": threshold,
                "reason":    metric.reason or "",
                "details":   {},
            }
        return results

    except Exception as exc:
        fallback = {"score": None, "passed": None, "threshold": 0.0,
                    "reason": str(exc)[:300], "details": {}}
        return {
            "answer_relevancy":     fallback,
            "faithfulness":         fallback,
            "contextual_relevancy": fallback,
        }


# ── Per-agent evaluation ──────────────────────────────────────────────────────

_AGENT_EVAL_FN = {
    "supplier":  ("evaluation.deepeval.test_supplier_node",  "evaluate_supplier"),
    "shipment":  ("evaluation.deepeval.test_shipment_node",  "evaluate_shipment"),
    "inventory": ("evaluation.deepeval.test_inventory_node", "evaluate_inventory"),
    "nlsql":     ("evaluation.deepeval.test_nlsql_node",     "evaluate_nlsql"),
}


def _agent_evaluations(query: str, agent_findings: dict, agent_sub_queries: dict = None) -> dict:
    import importlib
    results = {}
    sub_queries = agent_sub_queries or {}
    for agent_name, findings in agent_findings.items():
        if not findings or agent_name not in _AGENT_EVAL_FN:
            continue
        module_path, fn_name = _AGENT_EVAL_FN[agent_name]
        # Use the agent's focused sub-question for relevance evaluation; fall back to full query
        sub_query = sub_queries.get(agent_name) or query
        try:
            mod = importlib.import_module(module_path)
            results[agent_name] = getattr(mod, fn_name)(query, findings, sub_query=sub_query)
        except Exception as exc:
            results[agent_name] = {"error": {"score": None, "passed": None,
                                             "threshold": 0, "reason": str(exc)[:200], "details": {}}}
    return results


def _summary_evaluation(query: str, answer: str, agent_findings: dict) -> dict:
    try:
        from evaluation.deepeval.test_summary_node import evaluate_summary
        return evaluate_summary(query, answer, agent_findings)
    except Exception as exc:
        fallback = {"score": None, "passed": None, "threshold": 0, "reason": str(exc)[:200], "details": {}}
        return {"answer_relevancy": fallback, "answer_completeness": fallback, "conciseness": fallback}


# ── Main evaluation function ──────────────────────────────────────────────────

def evaluate_query(
    query: str,
    answer: str,
    retrieved_docs: list,
    sql_data: str = "",
    agent_findings: dict = None,
    agent_sub_queries: dict = None,
) -> dict:
    """
    Run pipeline + per-agent evaluation metrics.
    Returns a dict with pipeline metrics at the top level and
    agent_evaluations / summary_evaluation nested keys.
    """
    results: dict = {}

    if retrieved_docs:
        results["retrieval_quality"] = _retrieval_quality(retrieved_docs)
        results["context_coverage"]  = _context_coverage(retrieved_docs)

    # SQL consistency checks — run whenever SQL was executed
    if sql_data:
        results["sql_answer_consistency"] = _sql_answer_consistency(sql_data, answer)
        results["zero_result_handling"]   = _zero_result_handling(sql_data, answer)

    pipeline = _deepeval_pipeline_metrics(query, answer, retrieved_docs, sql_data=sql_data)
    results.update(pipeline)

    if agent_findings:
        agent_evals = _agent_evaluations(query, agent_findings, agent_sub_queries)
        if agent_evals:
            results["agent_evaluations"] = agent_evals

        results["summary_evaluation"] = _summary_evaluation(query, answer, agent_findings)

    return results
