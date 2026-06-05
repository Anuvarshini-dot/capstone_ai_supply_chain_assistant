from typing import TypedDict, List, Optional


class SupplyChainState(TypedDict):
    # ── Input ────────────────────────────────────────────────────
    query:               str
    filters:             Optional[dict]
    top_k:               int

    # ── Routing ──────────────────────────────────────────────────
    routed_agents:       List[str]   # e.g. ["supplier", "shipment"] or ["nlsql"] or ["general"]

    # ── Retrieval ─────────────────────────────────────────────────
    retrieved_incidents: List[dict]

    # ── Agent outputs ─────────────────────────────────────────────
    agent_findings:      dict        # keyed by agent name
    sql_result:          Optional[str]
    sql_entities:        Optional[dict]  # entities extracted from SQL result for targeted ChromaDB retrieval

    # ── Final outputs ─────────────────────────────────────────────
    answer:              str
    recommendations:     List[dict]
    anomaly_correlations: List[dict]
    confidence_score:    float
    evaluation:          dict
    execution_log:       List[dict]
