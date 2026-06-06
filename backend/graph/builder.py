"""
Builds and compiles the LangGraph StateGraph for the supply chain query pipeline.

Flow:
  START
    → general_check_node
        → general_node → END                          (off-topic query)
        → nlsql_node                                  (all supply-chain queries)
            → classify_node                           (decide which specialists + execution order)
                → recommendation_node → END           (SQL answer sufficient, no specialists needed)
                → retrieve_node                       (specialists needed)
                    → orchestrator_node               (runs agents in classifier-determined order)
                        → summary_node → recommendation_node → END
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, END, START

from graph.state import SupplyChainState
from graph.nodes import (
    general_check_node, classify_node, retrieve_node,
    orchestrator_node, nlsql_node, summary_node,
    recommendation_node, general_node,
    route_after_general_check, route_after_classify,
)


def build_graph():
    g = StateGraph(SupplyChainState)

    # ── Register nodes ────────────────────────────────────────────
    g.add_node("general_check_node",  general_check_node)
    g.add_node("nlsql_node",          nlsql_node)
    g.add_node("classify_node",       classify_node)
    g.add_node("retrieve_node",       retrieve_node)
    g.add_node("orchestrator_node",   orchestrator_node)
    g.add_node("summary_node",        summary_node)
    g.add_node("recommendation_node", recommendation_node)
    g.add_node("general_node",        general_node)

    # ── Entry point ───────────────────────────────────────────────
    g.add_edge(START, "general_check_node")

    # ── general_check → general QA or nlsql ──────────────────────
    g.add_conditional_edges(
        "general_check_node",
        route_after_general_check,
        {
            "general_node": "general_node",
            "nlsql_node":   "nlsql_node",
        }
    )

    # ── nlsql → classify ─────────────────────────────────────────
    g.add_edge("nlsql_node", "classify_node")

    # ── classify → retrieve (specialists needed) or recommendation ─
    g.add_conditional_edges(
        "classify_node",
        route_after_classify,
        {
            "retrieve_node":       "retrieve_node",
            "recommendation_node": "recommendation_node",
        }
    )

    # ── retrieve → orchestrator → summary ────────────────────────
    g.add_edge("retrieve_node",    "orchestrator_node")
    g.add_edge("orchestrator_node", "summary_node")

    # ── summary → recommendation → END ───────────────────────────
    g.add_edge("summary_node",        "recommendation_node")
    g.add_edge("recommendation_node", END)

    # ── general → END ─────────────────────────────────────────────
    g.add_edge("general_node", END)

    return g.compile()


# Compiled once at import time, reused across all requests
graph = build_graph()
