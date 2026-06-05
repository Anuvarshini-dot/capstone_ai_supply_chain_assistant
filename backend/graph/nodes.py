"""
LangGraph node functions for the supply chain query pipeline.
Each node receives the full state, does its work, and returns a partial state update.
"""
import json
import os
import sys
import time

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
- shipment  : questions about delivery routes, delays, shipping modes, carriers, regions,
              delivery status, at-risk shipments
- inventory : questions about stock levels, warehouses, stockouts, days of supply
- nlsql     : aggregation/calculation/ranking questions that need exact numbers across
              ALL data (e.g. "average delay", "top 5 suppliers by...", "total count of",
              "rank all...", "how many... in total", "highest/lowest X", "who contributes most")
- general   : use ONLY when the ENTIRE query has zero supply chain relevance

Rules:
- Return ["nlsql"] for any question needing precise aggregation or full-dataset ranking.
- Return ONE OR MORE of [supplier, shipment, inventory] for risk/analysis/contextual questions.
- COMPOUND QUERIES: A query can combine specialist agents WITH nlsql when it has BOTH
  a risk/analysis part AND a ranking/aggregation part.
  Examples:
    "Which warehouses are critical? and who is the highest supplier in Asia?"
    → ["inventory", "nlsql"]   (warehouse risk = inventory, highest supplier = nlsql)
    "What shipments are delayed in LATAM? and what is the average delay overall?"
    → ["shipment", "nlsql"]
    "Are there stockouts? and who ships the most to Singapore?"
    → ["inventory", "nlsql"]
- MIXED QUERIES with off-topic content: classify ONLY on supply chain parts, ignore off-topic.
  Example: "What shipments are at risk? and what is a computer mouse" → ["shipment"]
- Return ["general"] ONLY when the entire query has zero supply chain relevance.
- NEVER return ["general"] if any supply chain term is present.

Return ONLY valid JSON: {"agents": ["inventory", "nlsql"]}"""


# Supply chain signal words — used as a safety net in classify_node
_SC_KEYWORDS = {
    "supplier", "shipment", "delivery", "warehouse", "inventory", "stock",
    "carrier", "route", "delay", "risk", "defect", "order", "product",
    "shipping", "freight", "logistics", "dispatch", "fulfilment", "fulfillment",
    "reorder", "stockout", "lead time", "transit", "cargo", "vendor",
    "latam", "europe", "usca", "region", "pacific", "africa",
}


def classify_node(state: SupplyChainState) -> dict:
    t0    = time.time()
    query = state["query"]

    response = chat([
        {"role": "system", "content": CLASSIFIER_SYSTEM},
        {"role": "user",   "content": f"Classify: {query}"}
    ])
    agents = ["supplier", "shipment", "inventory"]
    try:
        start  = response.find("{")
        end    = response.rfind("}") + 1
        parsed = json.loads(response[start:end])
        valid  = {"supplier", "shipment", "inventory", "nlsql", "general"}
        agents = [a for a in parsed.get("agents", []) if a in valid] or agents
    except Exception:
        pass

    # Safety net: if LLM returned ["general"] but the query contains supply chain
    # keywords, override to the most relevant specialist agents
    if agents == ["general"]:
        q_lower = query.lower()
        if any(kw in q_lower for kw in _SC_KEYWORDS):
            # Re-classify with a focused second call on just the supply chain part
            focused = chat([
                {"role": "system", "content": CLASSIFIER_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"This query contains supply chain content. "
                        f"Classify ONLY the supply chain parts, ignore off-topic parts.\n"
                        f"Query: {query}"
                    )
                }
            ])
            try:
                s2 = focused.find("{"); e2 = focused.rfind("}") + 1
                p2 = json.loads(focused[s2:e2])
                sc_agents = [a for a in p2.get("agents", [])
                             if a in {"supplier", "shipment", "inventory", "nlsql"}]
                if sc_agents:
                    agents = sc_agents
            except Exception:
                # Fallback: keyword-based heuristic
                agents = []
                if any(k in q_lower for k in {"supplier", "vendor", "defect", "reliability"}):
                    agents.append("supplier")
                if any(k in q_lower for k in {"shipment", "delivery", "carrier", "route",
                                               "delay", "transit", "shipping", "freight",
                                               "latam", "europe", "usca", "region"}):
                    agents.append("shipment")
                if any(k in q_lower for k in {"inventory", "stock", "warehouse",
                                               "stockout", "reorder", "fulfillment"}):
                    agents.append("inventory")
                if not agents:
                    agents = ["general"]   # truly no SC content found

    log = state.get("execution_log", [])
    log.append({
        "step":   "Query Classification",
        "icon":   "🔍",
        "detail": f"Routed to: {', '.join(agents)}",
        "agents": agents,
        "ms":     round((time.time() - t0) * 1000),
    })
    return {"routed_agents": agents, "execution_log": log}


# ── Retrieval ────────────────────────────────────────────────────────────────

def retrieve_node(state: SupplyChainState) -> dict:
    t0    = time.time()
    query = state["query"]

    # When SQL ran first (hybrid path), enrich the retrieval query with entity names
    # so ChromaDB returns docs about the specific suppliers/warehouses SQL identified.
    sql_entities = state.get("sql_entities") or {}
    entity_names = (
        sql_entities.get("supplier_names", []) +
        sql_entities.get("warehouse_names", []) +
        sql_entities.get("product_names", [])
    )
    retrieval_query = f"{query} {' '.join(entity_names[:4])}" if entity_names else query

    raw = hybrid_search(retrieval_query, top_k=20, filters=state.get("filters") or None)
    top = rerank(query, raw, top_k=state.get("top_k", 5))

    entity_note = f" (entity-targeted: {', '.join(entity_names[:3])})" if entity_names else ""
    log = state.get("execution_log", [])
    log.append({
        "step":   "Vector Retrieval",
        "icon":   "🗄️",
        "detail": f"Hybrid BM25 + Semantic search — {len(top)} incidents retrieved{entity_note}",
        "docs_retrieved": len(top),
        "ms":     round((time.time() - t0) * 1000),
    })
    return {"retrieved_incidents": top, "execution_log": log}


# ── Specialist agent nodes ────────────────────────────────────────────────────

def supplier_node(state: SupplyChainState) -> dict:
    t0 = time.time()
    findings = SupplierRiskAgent().analyze(state["query"], state["retrieved_incidents"])
    log = state.get("execution_log", [])
    log.append({
        "step":     "Supplier Risk Agent",
        "icon":     "🏭",
        "detail":   findings.get("summary", "")[:120],
        "risk_level": findings.get("risk_level", "unknown"),
        "confidence": round(findings.get("confidence", 0) * 100),
        "findings_count": len(findings.get("findings", [])),
        "ms":       round((time.time() - t0) * 1000),
    })
    return {"agent_findings": {**state.get("agent_findings", {}), "supplier": findings}, "execution_log": log}


def shipment_node(state: SupplyChainState) -> dict:
    t0 = time.time()
    findings = ShipmentAgent().analyze(state["query"], state["retrieved_incidents"])
    log = state.get("execution_log", [])
    log.append({
        "step":     "Shipment Agent",
        "icon":     "🚢",
        "detail":   findings.get("summary", "")[:120],
        "risk_level": findings.get("risk_level", "unknown"),
        "confidence": round(findings.get("confidence", 0) * 100),
        "findings_count": len(findings.get("findings", [])),
        "ms":       round((time.time() - t0) * 1000),
    })
    return {"agent_findings": {**state.get("agent_findings", {}), "shipment": findings}, "execution_log": log}


def inventory_node(state: SupplyChainState) -> dict:
    t0 = time.time()
    findings = InventoryAgent().analyze(state["query"], state["retrieved_incidents"])
    log = state.get("execution_log", [])
    log.append({
        "step":     "Inventory Agent",
        "icon":     "📦",
        "detail":   findings.get("summary", "")[:120],
        "risk_level": findings.get("risk_level", "unknown"),
        "confidence": round(findings.get("confidence", 0) * 100),
        "findings_count": len(findings.get("findings", [])),
        "ms":       round((time.time() - t0) * 1000),
    })
    return {"agent_findings": {**state.get("agent_findings", {}), "inventory": findings}, "execution_log": log}


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

    t0    = time.time()
    query = state["query"]

    # Step 1: Generate SQL using our existing chat() (no LangChain agent needed)
    sql_response = chat([
        {
            "role": "system",
            "content": (
                "You are a SQLite expert. Generate a single valid SQLite SQL query "
                "to answer the user's question using the schema provided. "
                "Return ONLY the SQL query — no explanation, no markdown.\n\n"
                "Important rules:\n"
                "- When results include a supplier, always JOIN suppliers to include supplier_name.\n"
                "- When results include a product, always JOIN products to include product_name.\n"
                "- Never return only IDs in results — always include human-readable names."
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
    display_facts = []   # clean human-readable facts for the agent card
    sql_entities  = None
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        df   = pd.read_sql_query(sql_query, conn)

        if df.empty:
            raw_result = "No data found."
        else:
            raw_result = df.to_string(index=False)
            # Build clean display facts from the DataFrame (max 2 result rows, 5 cols)
            for _, row in df.head(2).iterrows():
                for col in list(df.columns)[:5]:
                    val  = row[col]
                    label = str(col).replace('_', ' ').title()
                    if isinstance(val, float):
                        is_rate = any(k in col.lower() for k in ('rate', 'pct', 'score', 'defect', 'reliability'))
                        val_str = f"{val:.1%}" if (is_rate and val <= 1) else f"{val:,.2f}"
                    elif isinstance(val, (int,)):
                        val_str = f"{val:,}"
                    else:
                        val_str = str(val)
                    display_facts.append(f"{label}: {val_str}")

        # Extract named entities from SQL result for targeted ChromaDB retrieval downstream
        sql_entities: dict = {
            "supplier_ids":    re.findall(r'\b(SUP-\d+)\b', raw_result)[:5],
            "warehouse_ids":   re.findall(r'\b(WH-\d+)\b',  raw_result)[:5],
            "supplier_names":  [],
            "warehouse_names": [],
            "product_names":   [],
        }
        for col in df.columns:
            col_l = col.lower()
            vals  = [v for v in df[col].dropna().unique().tolist() if isinstance(v, str)][:5]
            if "supplier_name" in col_l:
                sql_entities["supplier_names"].extend(vals)
            elif "warehouse_name" in col_l:
                sql_entities["warehouse_names"].extend(vals)
            elif "product_name" in col_l:
                sql_entities["product_names"].extend(vals)

        # Step 2b: Run follow-up context queries to enrich the answer with real names
        context_result = ""
        try:
            # Warehouse query: get product-level inventory breakdown
            wh_match = re.search(
                r"warehouse_name\s+LIKE\s+'([^']+)'|warehouse_name\s*=\s*'([^']+)'",
                sql_query, re.IGNORECASE
            )
            wh_id_match = re.search(r"warehouse_id\s*=\s*'([^']+)'", sql_query, re.IGNORECASE)

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
                        context_result += "\n\nProduct breakdown (lowest stock first):\n" + ctx_df.to_string(index=False)

            # Supplier query: enrich with supplier name + product-level risk breakdown
            sup_match = re.search(r'\b(SUP-\d+)\b', raw_result)
            if sup_match:
                sup_id = sup_match.group(1)

                # Get supplier name
                name_df = pd.read_sql_query(
                    f"SELECT supplier_name FROM suppliers WHERE supplier_id = '{sup_id}'", conn
                )
                sup_name = name_df.iloc[0]["supplier_name"] if not name_df.empty else sup_id

                # Products shipped: volume + late rate
                sup_ctx_sql = f"""
                    SELECT p.product_name,
                           SUM(s.quantity_units)                                          AS total_units_shipped,
                           ROUND(AVG(CASE WHEN s.is_late THEN 1.0 ELSE 0.0 END)*100, 1)  AS late_pct
                    FROM shipments s
                    JOIN products p ON s.product_id = p.product_id
                    WHERE s.supplier_id = '{sup_id}'
                    GROUP BY p.product_name
                    ORDER BY total_units_shipped DESC
                    LIMIT 8
                """
                sup_df = pd.read_sql_query(sup_ctx_sql, conn)
                if not sup_df.empty:
                    context_result += (
                        f"\n\nSupplier: {sup_name} ({sup_id})"
                        f"\nProducts shipped (by volume):\n" + sup_df.to_string(index=False)
                    )

                # Lowest-performing products: high late rate, low stock
                risk_ctx_sql = f"""
                    SELECT p.product_name,
                           ROUND(AVG(CASE WHEN s.is_late THEN 1.0 ELSE 0.0 END)*100, 1) AS late_pct,
                           SUM(s.quantity_units)                                          AS total_units,
                           MIN(i.stock_level_units)                                       AS min_stock,
                           MIN(i.days_of_supply)                                          AS min_days_supply,
                           MAX(i.status)                                                  AS worst_inv_status
                    FROM shipments s
                    JOIN products p ON s.product_id = p.product_id
                    LEFT JOIN inventory i ON i.product_id = p.product_id
                    WHERE s.supplier_id = '{sup_id}'
                    GROUP BY p.product_name
                    ORDER BY late_pct DESC, min_stock ASC
                    LIMIT 5
                """
                risk_df = pd.read_sql_query(risk_ctx_sql, conn)
                if not risk_df.empty:
                    context_result += f"\n\nRisk breakdown (worst late rate / lowest stock):\n" + risk_df.to_string(index=False)

        except Exception:
            pass

        conn.close()

    except Exception as e:
        raw_result = f"SQL execution error: {str(e)}\nQuery attempted: {sql_query}"
        context_result = ""

    # Step 3: Generate a risk-focused natural language answer from SQL results only
    answer = chat([
        {
            "role": "system",
            "content": (
                "You are a supply chain RISK analyst. Your primary job is to surface risks and drive action.\n\n"
                "When the question asks about positive performance (best, highest, top, most):\n"
                "1. State the top result in 1-2 sentences using full names (never IDs alone).\n"
                "2. Immediately pivot to risk: identify the WORST-performing products or items "
                "from that entity — highest late rates, lowest stock, critical/stockout status.\n"
                "3. End with 2-3 specific, actionable recommendations to mitigate those risks.\n\n"
                "When the question asks about negative performance (worst, lowest, failing):\n"
                "1. Answer directly with the worst performers and their specific risk metrics.\n"
                "2. Give 2-3 recommendations.\n\n"
                "Rules:\n"
                "- Always use full supplier/product names from the data — never IDs alone.\n"
                "- Be specific with numbers (units, %, days).\n"
                "- Keep the positive acknowledgment brief (max 2 sentences); spend most space on risks.\n"
                "- Use markdown: bold for names/numbers, bullet points for breakdowns."
            )
        },
        {
            "role": "user",
            "content": (
                f"Question: {query}\n\n"
                f"Primary SQL Result:\n{raw_result}"
                f"{context_result}\n\n"
                "Answer following the risk-first format above."
            )
        }
    ])

    elapsed = round((time.time() - t0) * 1000)

    # Clean 1-sentence summary from the LLM answer (strip markdown)
    first_line = answer.split('\n')[0].strip()
    card_summary = re.sub(r'\*+', '', first_line)[:200]

    card_findings = display_facts[:6] if display_facts else ["No structured data returned"]

    log = state.get("execution_log", [])
    log.append({
        "step":          "NL→SQL Agent",
        "icon":          "🗃️",
        "detail":        "SQL executed against supply_chain.db",
        "sql_query":     sql_query,
        "rows_returned": len(raw_result.splitlines()) - 1 if raw_result != "No data found." else 0,
        "ms":            elapsed,
    })

    # Merge nlsql findings into any existing specialist findings (hybrid path)
    merged_findings = {
        **state.get("agent_findings", {}),
        "nlsql": {
            "summary":    card_summary,
            "risk_level": "medium",
            "confidence": 0.9,
            "findings":   card_findings,
            "sql_query":  sql_query,
            "raw_result": raw_result[:500],
        }
    }

    return {
        "sql_result":          f"SQL: {sql_query}\n\nResults:\n{raw_result}",
        "answer":              answer,
        "confidence_score":    0.9,
        "execution_log":       log,
        "agent_findings":      merged_findings,
        "retrieved_incidents": state.get("retrieved_incidents", []),
        "sql_entities":        sql_entities,
    }


# ── Summary node ─────────────────────────────────────────────────────────────

def summary_node(state: SupplyChainState) -> dict:
    t0       = time.time()
    findings = state.get("agent_findings", {})
    answer   = SummaryAgent().summarize(state["query"], findings)
    anomalies = _detect_anomaly_correlations(findings)

    confidences = [
        float(v.get("confidence", 0.5))
        for v in findings.values()
        if isinstance(v, dict) and "confidence" in v
    ]
    confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.5

    log = state.get("execution_log", [])
    log.append({
        "step":       "Summary Generation",
        "icon":       "✦",
        "detail":     f"Confidence: {round(confidence * 100)}% | Anomalies detected: {len(anomalies)}",
        "confidence": round(confidence * 100),
        "anomalies":  len(anomalies),
        "ms":         round((time.time() - t0) * 1000),
    })

    return {
        "answer":               answer,
        "anomaly_correlations": anomalies,
        "confidence_score":     confidence,
        "execution_log":        log,
    }


# ── Recommendation node ──────────────────────────────────────────────────────

def recommendation_node(state: SupplyChainState) -> dict:
    t0       = time.time()
    findings = state.get("agent_findings", {})
    result   = RecommendationAgent().analyze(state["query"], findings)
    recs     = result.get("recommendations", [])

    log = state.get("execution_log", [])
    log.append({
        "step":   "Recommendation Engine",
        "icon":   "💡",
        "detail": f"{len(recs)} recommendations generated",
        "count":  len(recs),
        "ms":     round((time.time() - t0) * 1000),
    })

    return {"recommendations": recs, "execution_log": log}


# ── General node (off-topic) ─────────────────────────────────────────────────

def general_node(state: SupplyChainState) -> dict:
    t0     = time.time()
    result = BaseAgent().answer_general(state["query"])
    log    = state.get("execution_log", [])
    log.append({
        "step":   "General QA",
        "icon":   "💬",
        "detail": "Off-topic query — answered directly without supply chain analysis",
        "ms":     round((time.time() - t0) * 1000),
    })
    return {
        "answer":           result["answer"],
        "confidence_score": result.get("confidence", 0.8),
        "execution_log":    log,
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

_SC_AGENTS = {"supplier", "shipment", "inventory"}


def route_after_classify(state: SupplyChainState) -> str:
    agents = state["routed_agents"]
    if "general" in agents:
        return "general_node"
    # nlsql always runs first — both pure-SQL and hybrid paths
    if "nlsql" in agents:
        return "nlsql_node"
    # Specialist-only (no nlsql) → retrieval first
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
    agents   = state["routed_agents"]
    findings = state.get("agent_findings", {})
    if "shipment" in agents:
        return "shipment_node"
    if "inventory" in agents:
        return "inventory_node"
    # Only route to nlsql if it hasn't run yet (pure-specialist path, no SQL-first)
    if "nlsql" in agents and "nlsql" not in findings:
        return "nlsql_node"
    return "summary_node"


def route_after_shipment(state: SupplyChainState) -> str:
    agents   = state["routed_agents"]
    findings = state.get("agent_findings", {})
    if "inventory" in agents:
        return "inventory_node"
    if "nlsql" in agents and "nlsql" not in findings:
        return "nlsql_node"
    return "summary_node"


def route_after_inventory(state: SupplyChainState) -> str:
    findings = state.get("agent_findings", {})
    if "nlsql" in state["routed_agents"] and "nlsql" not in findings:
        return "nlsql_node"
    return "summary_node"


def route_after_nlsql(state: SupplyChainState) -> str:
    # Hybrid path: specialist agents still need to run → send to retrieve_node now
    # (nlsql ran first, so sql_entities are in state for targeted ChromaDB retrieval)
    if any(a in state["routed_agents"] for a in _SC_AGENTS):
        return "retrieve_node"
    # Pure nlsql path → skip summary, go straight to recommendations
    return "recommendation_node"
