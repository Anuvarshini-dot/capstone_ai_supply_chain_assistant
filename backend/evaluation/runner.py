"""
Per-query DeepEval evaluation runner.
Called after every query to produce live metrics shown in the Evaluation tab.

DeepEval metrics are configured with a custom LLM wrapper so they route through
the project's gateway (keygateway.arshnivlabs.com) instead of openai.com directly.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm.client import chat


# ── Custom LLM wrapper for DeepEval ──────────────────────────────────────────

def _make_project_llm():
    """
    Return a DeepEvalBaseLLM that routes through the project's gateway client.
    Imported lazily so deepeval import errors don't crash the whole module.
    """
    from deepeval.models.base_model import DeepEvalBaseLLM

    class ProjectGatewayLLM(DeepEvalBaseLLM):
        def load_model(self):
            return None

        def generate(self, prompt: str, schema=None):
            if schema is not None:
                # DeepEval needs structured JSON — force json_object mode
                response = chat(
                    [{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                )
                try:
                    import json
                    data = json.loads(response)
                    return schema(**data)
                except Exception:
                    return response
            return chat([{"role": "user", "content": prompt}])

        async def a_generate(self, prompt: str, schema=None):
            return self.generate(prompt, schema)

        def get_model_name(self) -> str:
            return "gpt-4o-mini"

    return ProjectGatewayLLM()


# ── Main evaluation function ──────────────────────────────────────────────────

def evaluate_query(query: str, answer: str, retrieved_docs: list) -> dict:
    """
    Run evaluation metrics for a single query/answer/context triple.
    Retrieval quality metrics never fail (no LLM needed).
    LLM-based metrics fail gracefully and include the error reason.
    """
    results = {}

    # ── Retrieval quality (no LLM) ────────────────────────────────────────────
    if retrieved_docs:
        hybrid_scores  = [d.get("hybrid_score", 0)  for d in retrieved_docs]
        semantic_scores = [d.get("semantic_score", 0) for d in retrieved_docs]
        avg_hybrid   = round(sum(hybrid_scores)   / len(hybrid_scores),   3)
        avg_semantic = round(sum(semantic_scores) / len(semantic_scores), 3)

        results["retrieval_quality"] = {
            "score":     avg_hybrid,
            "passed":    avg_hybrid > 0.3,
            "threshold": 0.3,
            "reason":    f"{len(retrieved_docs)} documents retrieved · avg hybrid score {avg_hybrid}",
            "details": {
                "num_docs":         len(retrieved_docs),
                "avg_semantic":     avg_semantic,
                "top_hybrid_score": round(max(hybrid_scores), 3),
            },
        }

    # ── DeepEval LLM-based metrics ─────────────────────────────────────────────
    try:
        from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
        from deepeval.test_case import LLMTestCase

        llm = _make_project_llm()
        retrieval_context = [d.get("text", "") for d in retrieved_docs[:5]]

        test_case = LLMTestCase(
            input=query,
            actual_output=answer,
            retrieval_context=retrieval_context,
        )

        llm_metrics = {
            "answer_relevancy": AnswerRelevancyMetric(threshold=0.5, model=llm),
            "faithfulness":     FaithfulnessMetric(threshold=0.5,     model=llm),
        }

        for name, metric in llm_metrics.items():
            try:
                metric.measure(test_case)
                score = metric.score
                # DeepEval uses .success or .is_successful() depending on version
                if hasattr(metric, "is_successful"):
                    passed = metric.is_successful()
                elif hasattr(metric, "success"):
                    passed = metric.success
                elif hasattr(metric, "passed"):
                    passed = metric.passed
                else:
                    passed = (score is not None and score >= metric.threshold)
                results[name] = {
                    "score":     round(float(score), 3) if score is not None else None,
                    "passed":    bool(passed) if passed is not None else None,
                    "threshold": metric.threshold,
                    "reason":    getattr(metric, "reason", None),
                    "details":   {},
                }
            except Exception as e:
                results[name] = {
                    "score":     None,
                    "passed":    None,
                    "threshold": 0.5,
                    "reason":    str(e)[:300],
                    "details":   {},
                }

    except ImportError:
        results["deepeval_unavailable"] = {
            "score":     None,
            "passed":    None,
            "threshold": None,
            "reason":    "deepeval not installed — run: pip install deepeval",
            "details":   {},
        }
    except Exception as e:
        results["deepeval_error"] = {
            "score":     None,
            "passed":    None,
            "threshold": None,
            "reason":    str(e)[:300],
            "details":   {},
        }

    return results
