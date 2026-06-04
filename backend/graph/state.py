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

    # ── Final outputs ─────────────────────────────────────────────
    answer:              str
    recommendations:     List[dict]
    anomaly_correlations: List[dict]
    confidence_score:    float
    evaluation:          dict
