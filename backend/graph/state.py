from typing import TypedDict, List, Optional


class SupplyChainState(TypedDict):
    # ── Input ────────────────────────────────────────────────────
    query:               str
    filters:             Optional[dict]
    top_k:               int

    # ── Guardrail ─────────────────────────────────────────────────
    validation_passed:   Optional[bool]  # set by input_guardrail_node; False short-circuits the graph

    # ── Routing ──────────────────────────────────────────────────
    routed_agents:       List[str]   # e.g. ["inventory", "supplier"] — ordered by classifier
    agent_sub_queries:   Optional[dict]  # e.g. {"inventory": "which warehouse...", "supplier": "who supplies LA Hub?"}

    # ── Agent outputs ─────────────────────────────────────────────
    agent_findings:      dict        # keyed by agent name
    retrieved_incidents: List[dict]  # collected from all agent findings
    sql_result:          Optional[str]
    sql_data:            Optional[str]   # raw tabular SQL output — used as faithfulness context
    sql_entities:        Optional[dict]  # entities extracted from SQL result for targeted ChromaDB retrieval

    # ── Final outputs ─────────────────────────────────────────────
    answer:              str
    recommendations:     List[dict]
    anomaly_correlations: List[dict]
    confidence_score:    float
    evaluation:          dict
    execution_log:       List[dict]
