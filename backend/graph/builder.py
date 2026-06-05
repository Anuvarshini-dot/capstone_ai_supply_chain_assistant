"""
Builds and compiles the LangGraph StateGraph for the supply chain query pipeline.

Flow:
  START
    → classify_node
        → general_node → END
        → nlsql_node (pure SQL or SQL-first hybrid)
            → recommendation_node → END          (pure nlsql)
            → retrieve_node                      (hybrid: specialists run after SQL)
                → supplier_node  (if needed)
                → shipment_node  (if needed)
                → inventory_node (if needed)
                    → summary_node → recommendation_node → END
        → retrieve_node (specialist-only, no nlsql)
            → supplier_node  (if needed)
            → shipment_node  (if needed)
            → inventory_node (if needed)
                → summary_node → recommendation_node → END
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, END, START

from graph.state import SupplyChainState
from graph.nodes import (
    classify_node, retrieve_node,
    supplier_node, shipment_node, inventory_node,
    nlsql_node, summary_node, recommendation_node, general_node,
    route_after_classify, route_after_retrieve,
    route_after_supplier, route_after_shipment,
    route_after_inventory, route_after_nlsql,
)


def build_graph():
    g = StateGraph(SupplyChainState)

    # ── Register nodes ────────────────────────────────────────────
    g.add_node("classify_node",        classify_node)
    g.add_node("retrieve_node",        retrieve_node)
    g.add_node("supplier_node",        supplier_node)
    g.add_node("shipment_node",        shipment_node)
    g.add_node("inventory_node",       inventory_node)
    g.add_node("nlsql_node",           nlsql_node)
    g.add_node("summary_node",         summary_node)
    g.add_node("recommendation_node",  recommendation_node)
    g.add_node("general_node",         general_node)

    # ── Entry point ───────────────────────────────────────────────
    g.add_edge(START, "classify_node")

    # ── classify → route ──────────────────────────────────────────
    # Pure nlsql → nlsql_node
    # Specialist (±nlsql) → retrieve_node first; nlsql chains after
    g.add_conditional_edges(
        "classify_node",
        route_after_classify,
        {
            "general_node":  "general_node",
            "nlsql_node":    "nlsql_node",
            "retrieve_node": "retrieve_node",
        }
    )

    # ── retrieve → first specialist ───────────────────────────────
    g.add_conditional_edges(
        "retrieve_node",
        route_after_retrieve,
        {
            "supplier_node":  "supplier_node",
            "shipment_node":  "shipment_node",
            "inventory_node": "inventory_node",
            "summary_node":   "summary_node",
        }
    )

    # ── supplier → next specialist, nlsql, or summary ─────────────
    g.add_conditional_edges(
        "supplier_node",
        route_after_supplier,
        {
            "shipment_node":  "shipment_node",
            "inventory_node": "inventory_node",
            "nlsql_node":     "nlsql_node",
            "summary_node":   "summary_node",
        }
    )

    # ── shipment → inventory, nlsql, or summary ───────────────────
    g.add_conditional_edges(
        "shipment_node",
        route_after_shipment,
        {
            "inventory_node": "inventory_node",
            "nlsql_node":     "nlsql_node",
            "summary_node":   "summary_node",
        }
    )

    # ── inventory → nlsql (hybrid) or summary ─────────────────────
    g.add_conditional_edges(
        "inventory_node",
        route_after_inventory,
        {
            "nlsql_node":   "nlsql_node",
            "summary_node": "summary_node",
        }
    )

    # ── nlsql → retrieve (hybrid: specialists run after SQL) or recommendation (pure) ──
    g.add_conditional_edges(
        "nlsql_node",
        route_after_nlsql,
        {
            "retrieve_node":       "retrieve_node",
            "recommendation_node": "recommendation_node",
        }
    )

    # ── summary → recommendation → END ────────────────────────────
    g.add_edge("summary_node",        "recommendation_node")
    g.add_edge("recommendation_node", END)

    # ── general → END ─────────────────────────────────────────────
    g.add_edge("general_node", END)

    return g.compile()


# Compiled once at import time, reused across all requests
graph = build_graph()
