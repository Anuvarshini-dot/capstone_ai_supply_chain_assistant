"""
Per-query evaluation runner for the supply chain risk assessment assistant.

All three LLM-based metrics are implemented as fully custom prompts that call
the project's own gateway LLM directly — no DeepEval schema calls, no internal
multi-step chains, no JSON parsing failures.

Metrics:
  retrieval_quality    – avg hybrid score (non-LLM)
  context_coverage     – distinct doc-type breadth (non-LLM)
  answer_relevancy     – domain-aware: query ↔ answer (custom LLM)
  faithfulness         – hallucination check: context ↔ answer (custom LLM)
  contextual_relevancy – retrieval quality check: query ↔ context (custom LLM)
"""
import json as _json
import re as _re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm.client import chat


# ── Shared LLM call helper ────────────────────────────────────────────────────

def _llm_json(prompt: str) -> dict:
    """
    Call the project LLM and reliably extract a JSON object from the response.
    Handles markdown code-fences, leading/trailing text, and other formatting noise.
    """
    raw = chat([
        {"role": "system", "content": "Respond with ONLY a valid JSON object. No markdown, no code blocks, no extra text."},
        {"role": "user",   "content": prompt},
    ])
    # Strip markdown code fences
    cleaned = _re.sub(r"```(?:json)?\s*", "", raw)
    cleaned = _re.sub(r"```\s*", "", cleaned).strip()
    # Try direct parse first
    try:
        return _json.loads(cleaned)
    except Exception:
        pass
    # Find the first {...} block as fallback
    match = _re.search(r"\{.*\}", cleaned, _re.DOTALL)
    if match:
        try:
            return _json.loads(match.group())
        except Exception:
            pass
    raise ValueError(f"No valid JSON found in LLM response: {raw[:300]}")


def _score_result(data: dict, threshold: float, key_score="score", key_reason="reason") -> dict:
    score  = round(float(data[key_score]), 3)
    reason = str(data.get(key_reason, ""))
    return {
        "score":     score,
        "passed":    score >= threshold,
        "threshold": threshold,
        "reason":    reason,
        "details":   {},
    }


# ── Metric 3: Answer Relevancy (domain-aware) ─────────────────────────────────

_ANSWER_RELEVANCY_PROMPT = """\
You are an evaluator for a SUPPLY CHAIN RISK ASSESSMENT assistant.

The assistant's job is to help users understand supply chain risks:
  - Warehouse inventory, stockouts, days of supply
  - Supplier reliability, risk tiers, performance
  - Shipment delays, delivery status, modes
  - Overall supply chain health

USER QUESTION:
{query}

ASSISTANT ANSWER:
{answer}

Score the answer's relevancy (0.0–1.0) against BOTH:
  1. Does it address the specific question?
  2. Does it provide useful supply chain risk context?

IMPORTANT RULE: Risk signals like stockout warnings, delay risks, supplier risk tiers,
and inventory health are the CORE PURPOSE of this assistant. They MUST increase the
score, never decrease it. NEVER describe supply chain risk information as "irrelevant".
Only penalise content that has zero connection to supply chain (e.g. cooking, sports).

The "reason" field must:
  - Start with "The answer scores X because..."
  - Explain relevancy in supply chain risk terms
  - Never call stockout, delay, or inventory information "irrelevant" or "off-topic"

Respond with ONLY this JSON:
{{"score": <float 0.0-1.0>, "reason": "<one sentence starting with The answer scores X because>"}}"""


def _measure_answer_relevancy(query: str, answer: str, threshold: float = 0.5) -> dict:
    try:
        prompt = _ANSWER_RELEVANCY_PROMPT.format(query=query, answer=answer)
        data   = _llm_json(prompt)
        return _score_result(data, threshold)
    except Exception as exc:
        return {"score": None, "passed": None, "threshold": threshold,
                "reason": str(exc)[:300], "details": {}}


# ── Metric 4: Faithfulness (hallucination check) ──────────────────────────────

_FAITHFULNESS_PROMPT = """\
You are evaluating whether a supply chain assistant's answer is grounded in the
retrieved context (i.e. free of hallucinations).

RETRIEVED CONTEXT:
{context}

ASSISTANT ANSWER:
{answer}

Score how faithfully every factual claim in the answer is supported by the context (0.0–1.0):
  1.0 – every claim is directly supported by the context
  0.7 – most claims supported; minor extrapolations present
  0.5 – roughly half the claims are supported
  0.0 – the answer makes claims not present in the context (hallucination)

The "reason" must name specific claims that are or are not supported.

Respond with ONLY this JSON:
{{"score": <float 0.0-1.0>, "reason": "<one sentence>"}}"""


def _measure_faithfulness(answer: str, retrieval_context: list, sql_data: str = "", threshold: float = 0.5) -> dict:
    try:
        # SQL query results are the primary ground truth — prepend them so the
        # faithfulness check can verify numeric claims that come from the database
        # rather than from the ChromaDB vector store.
        sql_block = f"[SQL Query Results]\n{sql_data}" if sql_data else ""
        parts = ([sql_block] if sql_block else []) + retrieval_context[:5]
        context_text = "\n---\n".join(parts) if parts else "(none)"
        prompt = _FAITHFULNESS_PROMPT.format(context=context_text, answer=answer)
        data   = _llm_json(prompt)
        return _score_result(data, threshold)
    except Exception as exc:
        return {"score": None, "passed": None, "threshold": threshold,
                "reason": str(exc)[:300], "details": {}}


# ── Metric 5: Contextual Relevancy (retrieval quality) ────────────────────────

_CONTEXTUAL_RELEVANCY_PROMPT = """\
You are evaluating whether the right documents were retrieved to answer a supply chain
risk assessment question.

USER QUESTION:
{query}

RETRIEVED CONTEXT (documents given to the assistant):
{context}

Score how relevant the retrieved documents are to the question (0.0–1.0):
  1.0 – the context contains exactly the data needed to answer this question
  0.7 – most documents are relevant; a few are tangential
  0.5 – roughly half the context is relevant
  0.0 – the context is unrelated to the question

Consider: suppliers, warehouses, shipments, inventory data are all fair context for
supply chain questions — do not penalise domain-adjacent information.

The "reason" must say which documents or doc types were helpful or missing.

Respond with ONLY this JSON:
{{"score": <float 0.0-1.0>, "reason": "<one sentence>"}}"""


def _measure_contextual_relevancy(query: str, retrieval_context: list, threshold: float = 0.5) -> dict:
    try:
        context_text = "\n---\n".join(retrieval_context[:5]) if retrieval_context else "(none)"
        prompt = _CONTEXTUAL_RELEVANCY_PROMPT.format(query=query, context=context_text)
        data   = _llm_json(prompt)
        return _score_result(data, threshold)
    except Exception as exc:
        return {"score": None, "passed": None, "threshold": threshold,
                "reason": str(exc)[:300], "details": {}}


# ── Main evaluation function ──────────────────────────────────────────────────

def evaluate_query(query: str, answer: str, retrieved_docs: list, sql_data: str = "") -> dict:
    """
    Run all five evaluation metrics for a single query / answer / context triple.

    Non-LLM metrics (retrieval_quality, context_coverage) always succeed.
    LLM-based metrics (answer_relevancy, faithfulness, contextual_relevancy)
    use direct gateway calls with simple JSON output — no DeepEval schema calls.
    """
    results = {}

    # ── 1. Retrieval Quality (non-LLM) ───────────────────────────────────────
    if retrieved_docs:
        hybrid_scores   = [d.get("hybrid_score",  0) for d in retrieved_docs]
        semantic_scores = [d.get("semantic_score", 0) for d in retrieved_docs]
        avg_hybrid      = round(sum(hybrid_scores)   / len(hybrid_scores),   3)
        avg_semantic    = round(sum(semantic_scores) / len(semantic_scores), 3)
        top_hybrid      = round(max(hybrid_scores), 3)
        high_quality    = sum(1 for s in hybrid_scores if s > 0.5)

        results["retrieval_quality"] = {
            "score":     avg_hybrid,
            "passed":    avg_hybrid > 0.3,
            "threshold": 0.3,
            "reason":    (
                f"{len(retrieved_docs)} docs retrieved · "
                f"avg hybrid {avg_hybrid} · avg semantic {avg_semantic} · "
                f"{high_quality} doc(s) above 0.5 quality threshold"
            ),
            "details": {
                "num_docs":          len(retrieved_docs),
                "avg_semantic":      avg_semantic,
                "top_hybrid_score":  top_hybrid,
                "high_quality_docs": high_quality,
            },
        }

        # ── 2. Context Coverage (non-LLM) ─────────────────────────────────────
        doc_type_counts: dict = {}
        for d in retrieved_docs:
            dt = d.get("metadata", {}).get("doc_type", "shipment")
            doc_type_counts[dt] = doc_type_counts.get(dt, 0) + 1

        num_types      = len(doc_type_counts)
        coverage_score = round(num_types / 3, 3)
        display_types  = {k.replace("_profile", ""): v for k, v in doc_type_counts.items()}

        results["context_coverage"] = {
            "score":     coverage_score,
            "passed":    num_types >= 1,
            "threshold": 0.33,
            "reason":    (
                f"{num_types} distinct document type(s) in context: "
                f"{', '.join(doc_type_counts.keys())}"
            ),
            "details":   display_types,
        }

    # ── 3–5. LLM-based metrics (fully custom — no DeepEval schema calls) ─────
    retrieval_context = [d.get("text", "") for d in retrieved_docs[:5]]

    results["answer_relevancy"]    = _measure_answer_relevancy(query, answer)
    results["faithfulness"]        = _measure_faithfulness(answer, retrieval_context, sql_data=sql_data)
    results["contextual_relevancy"] = _measure_contextual_relevancy(query, retrieval_context)

    return results
