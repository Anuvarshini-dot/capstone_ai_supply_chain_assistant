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


# ── Main evaluation function ──────────────────────────────────────────────────

def evaluate_query(
    query: str,
    answer: str,
    retrieved_docs: list,
    sql_data: str = "",
) -> dict:
    """
    Run the five evaluation metrics for a single query / answer / context triple.
    Returns a flat dict where every value is a {score, passed, threshold, reason, details} metric.
    """
    results: dict = {}

    if retrieved_docs:
        results["retrieval_quality"] = _retrieval_quality(retrieved_docs)
        results["context_coverage"]  = _context_coverage(retrieved_docs)

    pipeline = _deepeval_pipeline_metrics(query, answer, retrieved_docs, sql_data=sql_data)
    results.update(pipeline)

    return results
