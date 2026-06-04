"""
Builds and compiles the LangGraph StateGraph for the supply chain query pipeline.

Flow:
  START
    → classify_node
        → general_node → END
        → nlsql_node → recommendation_node → END
        → retrieve_node
            → supplier_node  (if needed)
            → shipment_node  (if needed)
            → inventory_node (if needed)
            → summary_node
            → recommendation_node
            → END
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
)


def build_graph():
    g = StateGraph(SupplyChainState)

    # ── Register nodes ───────────────────────────────────────────
    g.add_node("classify_node",        classify_node)
    g.add_node("retrieve_node",        retrieve_node)
    g.add_node("supplier_node",        supplier_node)
    g.add_node("shipment_node",        shipment_node)
    g.add_node("inventory_node",       inventory_node)
    g.add_node("nlsql_node",           nlsql_node)
    g.add_node("summary_node",         summary_node)
    g.add_node("recommendation_node",  recommendation_node)
    g.add_node("general_node",         general_node)

    # ── Entry point ──────────────────────────────────────────────
    g.add_edge(START, "classify_node")

    # ── classify → route ─────────────────────────────────────────
    g.add_conditional_edges(
        "classify_node",
        route_after_classify,
        {
            "general_node":  "general_node",
            "nlsql_node":    "nlsql_node",
            "retrieve_node": "retrieve_node",
        }
    )

    # ── retrieve → first specialist ──────────────────────────────
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

    # ── supplier → next specialist or summary ────────────────────
    g.add_conditional_edges(
        "supplier_node",
        route_after_supplier,
        {
            "shipment_node":  "shipment_node",
            "inventory_node": "inventory_node",
            "summary_node":   "summary_node",
        }
    )

    # ── shipment → inventory or summary ──────────────────────────
    g.add_conditional_edges(
        "shipment_node",
        route_after_shipment,
        {
            "inventory_node": "inventory_node",
            "summary_node":   "summary_node",
        }
    )

    # ── inventory always goes to summary ─────────────────────────
    g.add_edge("inventory_node", "summary_node")

    # ── specialist path: summary → recommendation → END ─────────
    g.add_edge("summary_node",        "recommendation_node")
    g.add_edge("recommendation_node", END)

    # ── nlsql path: nlsql → recommendation → END ─────────────────
    g.add_edge("nlsql_node", "recommendation_node")

    # ── general path: general → END ──────────────────────────────
    g.add_edge("general_node", END)

    return g.compile()


# Compile once at import time so the graph is reused across requests
graph = build_graph()
