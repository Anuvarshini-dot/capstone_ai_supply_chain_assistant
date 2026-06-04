"""
LangGraph node functions for the supply chain query pipeline.
Each node receives the full state, does its work, and returns a partial state update.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph.state import SupplyChainState
from agents.base_agent import BaseAgent
from agents.supplier_risk_agent import SupplierRiskAgent
from agents.shipment_agent import ShipmentAgent
from agents.inventory_agent import InventoryAgent
from agents.recommendation_agent import RecommendationAgent
from agents.summary_agent import SummaryAgent
from retrieval.hybrid_search import hybrid_search
from retrieval.reranker import rerank
from llm.client import chat
from config import SQLITE_DB_PATH


# ── Classifier ────────────────────────────────────────────────────────────────

CLASSIFIER_SYSTEM = """You are a supply chain query classifier.
Classify the user query into one or more of these routing targets:

- supplier  : questions about specific suppliers, their performance, reliability, risk
- shipment  : questions about delivery routes, delays, shipping modes, carriers
- inventory : questions about stock levels, warehouses, stockouts, days of supply
- nlsql     : aggregation/calculation/ranking questions that need exact numbers across
              ALL data (e.g. "average delay", "top 5 suppliers by...", "total count of",
              "rank all...", "how many... in total")
- general   : questions NOT related to supply chain at all

Rules:
- Return ["nlsql"] for any question needing precise aggregation or full-dataset ranking.
- Return ["general"] for completely off-topic questions.
- Return one or more of [supplier, shipment, inventory] for contextual/risk questions.
- A query can match multiple domains (e.g. ["supplier", "inventory"]).

Return ONLY valid JSON: {"agents": ["supplier", "shipment"]}"""


def classify_node(state: SupplyChainState) -> dict:
    response = chat([
        {"role": "system", "content": CLASSIFIER_SYSTEM},
        {"role": "user",   "content": f"Classify: {state['query']}"}
    ])
    try:
        start   = response.find("{")
        end     = response.rfind("}") + 1
        parsed  = json.loads(response[start:end])
        valid   = {"supplier", "shipment", "inventory", "nlsql", "general"}
        agents  = [a for a in parsed.get("agents", []) if a in valid]
        if agents:
            return {"routed_agents": agents}
    except Exception:
        pass
    return {"routed_agents": ["supplier", "shipment", "inventory"]}


# ── Retrieval ────────────────────────────────────────────────────────────────

def retrieve_node(state: SupplyChainState) -> dict:
    raw  = hybrid_search(state["query"], top_k=20, filters=state.get("filters") or None)
    top  = rerank(state["query"], raw, top_k=state.get("top_k", 5))
    return {"retrieved_incidents": top}


# ── Specialist agent nodes ────────────────────────────────────────────────────

def supplier_node(state: SupplyChainState) -> dict:
    findings = SupplierRiskAgent().analyze(state["query"], state["retrieved_incidents"])
    return {"agent_findings": {**state.get("agent_findings", {}), "supplier": findings}}


def shipment_node(state: SupplyChainState) -> dict:
    findings = ShipmentAgent().analyze(state["query"], state["retrieved_incidents"])
    return {"agent_findings": {**state.get("agent_findings", {}), "shipment": findings}}


def inventory_node(state: SupplyChainState) -> dict:
    findings = InventoryAgent().analyze(state["query"], state["retrieved_incidents"])
    return {"agent_findings": {**state.get("agent_findings", {}), "inventory": findings}}


# ── NL-to-SQL node ───────────────────────────────────────────────────────────

_DB_SCHEMA = """
Tables in the supply chain SQLite database:

suppliers(supplier_id, supplier_name, category, country, region,
          on_time_delivery_rate, defect_rate, avg_lead_time_days,
          contract_value_usd, payment_terms, risk_tier, reliability_score, active)

products(product_id, product_name, category, supplier_id,
         unit_cost_usd, unit_price_usd, weight_kg,
         reorder_point_units, safety_stock_days)

warehouses(warehouse_id, warehouse_name, city, country, region,
           capacity_units, current_utilization_pct)

inventory(inventory_id, product_id, warehouse_id,
          stock_level_units,      -- ← THIS is the inventory/stock level (units on hand)
          reorder_point_units, avg_daily_demand, days_of_supply,
          last_replenishment_date, stockout_count_30d,
          status)                 -- values: healthy, low, critical, stockout

shipments(shipment_id, supplier_id, product_id, destination_warehouse_id,
          origin_city, origin_country, destination_city, destination_country,
          order_date, scheduled_delivery_date, actual_delivery_date,
          delay_days, shipping_mode, carrier,
          status,                 -- values: Delivered, In Transit, Delayed, Cancelled
          quantity_units, shipment_cost_usd, is_late, late_delivery_risk,
          severity, risk_score)

IMPORTANT RULES:
- "inventory level" or "stock level" always means column: stock_level_units in inventory table
- "delivery delay" always means column: delay_days in shipments table
- For warehouse name searches use LIKE: WHERE warehouse_name LIKE '%Tokyo%'
- inventory.warehouse_id joins to warehouses.warehouse_id
- shipments.destination_warehouse_id joins to warehouses.warehouse_id
- shipments.supplier_id joins to suppliers.supplier_id
- shipments.product_id joins to products.product_id

Warehouse names (WH-01 to WH-15):
WH-01 Chicago Distribution Center, WH-02 Los Angeles Fulfillment Hub,
WH-03 Toronto Logistics Center, WH-04 Houston Supply Depot,
WH-05 Berlin Central Warehouse, WH-06 Paris Distribution Hub,
WH-07 London Regional Center, WH-08 Amsterdam Port Facility,
WH-09 São Paulo Distribution Center, WH-10 Bogotá Logistics Hub,
WH-11 Santiago Supply Depot, WH-12 Singapore Regional Hub,
WH-13 Tokyo Distribution Center, WH-14 Johannesburg Supply Hub,
WH-15 Lagos Distribution Center
"""


def nlsql_node(state: SupplyChainState) -> dict:
    import re
    import sqlite3
    import pandas as pd

    query = state["query"]

    # Step 1: Generate SQL using our existing chat() (no LangChain agent needed)
    sql_response = chat([
        {
            "role": "system",
            "content": (
                "You are a SQLite expert. Generate a single valid SQLite SQL query "
                "to answer the user's question using the schema provided. "
                "Return ONLY the SQL query — no explanation, no markdown."
            )
        },
        {
            "role": "user",
            "content": f"Schema:\n{_DB_SCHEMA}\n\nQuestion: {query}"
        }
    ])

    # Strip markdown code fences if present
    sql_query = re.sub(r'```[a-zA-Z]*', '', sql_response).replace('```', '').strip()
    # Step 2: Execute primary SQL directly against SQLite
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        df   = pd.read_sql_query(sql_query, conn)

        if df.empty:
            raw_result = "No data found."
        else:
            raw_result = df.to_string(index=False)

        # Step 2b: Run a follow-up context query to enrich the answer
        # Extract warehouse name from the primary SQL to get product-level breakdown
        context_result = ""
        try:
            wh_match = re.search(
                r"warehouse_name\s+LIKE\s+'([^']+)'|warehouse_name\s*=\s*'([^']+)'",
                sql_query, re.IGNORECASE
            )
            wh_id_match = re.search(
                r"warehouse_id\s*=\s*'([^']+)'",
                sql_query, re.IGNORECASE
            )

            if wh_match or wh_id_match:
                wh_filter = ""
                if wh_id_match:
                    wh_filter = f"i.warehouse_id = '{wh_id_match.group(1)}'"
                elif wh_match:
                    name_val = wh_match.group(1) or wh_match.group(2)
                    wh_filter = f"w.warehouse_name LIKE '{name_val}'"

                if wh_filter:
                    ctx_sql = f"""
                        SELECT p.product_name,
                               i.stock_level_units,
                               i.reorder_point_units,
                               i.days_of_supply,
                               i.status,
                               i.stockout_count_30d
                        FROM inventory i
                        JOIN products p ON i.product_id = p.product_id
                        JOIN warehouses w ON i.warehouse_id = w.warehouse_id
                        WHERE {wh_filter}
                        ORDER BY i.stock_level_units ASC
                        LIMIT 10
                    """
                    ctx_df = pd.read_sql_query(ctx_sql, conn)
                    if not ctx_df.empty:
                        context_result = "\n\nProduct breakdown (lowest stock first):\n" + ctx_df.to_string(index=False)
        except Exception:
            pass

        conn.close()

    except Exception as e:
        raw_result = f"SQL execution error: {str(e)}\nQuery attempted: {sql_query}"
        context_result = ""

    # Step 3: Generate a detailed natural language answer
    answer = chat([
        {
            "role": "system",
            "content": (
                "You are a supply chain analyst. Answer the user's question with detail. "
                "Include: the main metric answer, a breakdown of key products or items, "
                "which items are at risk (critical/stockout status), and any actionable context. "
                "Use bullet points for the breakdown. Be specific with numbers and names."
            )
        },
        {
            "role": "user",
            "content": (
                f"Question: {query}\n\n"
                f"Primary Result:\n{raw_result}"
                f"{context_result}\n\n"
                f"Provide a detailed answer with specific product names, stock levels, and risk context."
            )
        }
    ])

    return {
        "sql_result":      f"SQL: {sql_query}\n\nResults:\n{raw_result}",
        "answer":          answer,
        "agent_findings":  {
            "nlsql": {
                "summary":       answer,
                "risk_level":    "medium",
                "confidence":    0.9,
                "findings":      [
                    f"Analytical query: {query}",
                    f"Result: {raw_result[:200]}",
                    "Recommendations should focus on improving or acting on this data.",
                ],
                "sql_query":     sql_query,
                "raw_result":    raw_result[:500],
            }
        },
        "retrieved_incidents": state.get("retrieved_incidents", []),
    }


# ── Summary node ─────────────────────────────────────────────────────────────

def summary_node(state: SupplyChainState) -> dict:
    findings = state.get("agent_findings", {})
    answer   = SummaryAgent().summarize(state["query"], findings)
    anomalies = _detect_anomaly_correlations(findings)

    confidences = [
        float(v.get("confidence", 0.5))
        for v in findings.values()
        if isinstance(v, dict) and "confidence" in v
    ]
    confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.5

    return {
        "answer":              answer,
        "anomaly_correlations": anomalies,
        "confidence_score":    confidence,
    }


# ── Recommendation node ──────────────────────────────────────────────────────

def recommendation_node(state: SupplyChainState) -> dict:
    findings = state.get("agent_findings", {})
    result   = RecommendationAgent().analyze(state["query"], findings)
    return {"recommendations": result.get("recommendations", [])}


# ── General node (off-topic) ─────────────────────────────────────────────────

def general_node(state: SupplyChainState) -> dict:
    result = BaseAgent().answer_general(state["query"])
    return {
        "answer":           result["answer"],
        "confidence_score": result.get("confidence", 0.8),
    }


# ── Anomaly correlation helper ────────────────────────────────────────────────

def _detect_anomaly_correlations(findings: dict) -> list:
    correlations = []
    supplier_risk  = findings.get("supplier",  {}).get("risk_level", "low")
    inventory_risk = findings.get("inventory", {}).get("risk_level", "low")
    shipment_risk  = findings.get("shipment",  {}).get("risk_level", "low")
    high_medium    = {"high", "medium"}

    if supplier_risk == "high" and inventory_risk in high_medium:
        correlations.append({
            "type":            "supplier_inventory_cascade",
            "description":     "Supplier delivery delays correlating with inventory depletion — cascade risk detected.",
            "severity":        "high",
            "agents_involved": ["supplier", "inventory"],
        })
    if shipment_risk == "high" and supplier_risk in high_medium:
        correlations.append({
            "type":            "shipment_supplier_compound",
            "description":     "Concurrent shipment disruptions and supplier issues — compound bottleneck risk.",
            "severity":        "high",
            "agents_involved": ["shipment", "supplier"],
        })
    if inventory_risk == "high" and shipment_risk in high_medium:
        correlations.append({
            "type":            "inventory_shipment_stockout",
            "description":     "Shipment delays compounding low inventory — elevated stockout risk.",
            "severity":        "medium",
            "agents_involved": ["inventory", "shipment"],
        })
    return correlations


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_classify(state: SupplyChainState) -> str:
    agents = state["routed_agents"]
    if "general" in agents:
        return "general_node"
    if "nlsql" in agents:
        return "nlsql_node"
    return "retrieve_node"


def route_after_retrieve(state: SupplyChainState) -> str:
    agents = state["routed_agents"]
    if "supplier" in agents:
        return "supplier_node"
    if "shipment" in agents:
        return "shipment_node"
    if "inventory" in agents:
        return "inventory_node"
    return "summary_node"


def route_after_supplier(state: SupplyChainState) -> str:
    agents = state["routed_agents"]
    if "shipment" in agents:
        return "shipment_node"
    if "inventory" in agents:
        return "inventory_node"
    return "summary_node"


def route_after_shipment(state: SupplyChainState) -> str:
    if "inventory" in state["routed_agents"]:
        return "inventory_node"
    return "summary_node"
