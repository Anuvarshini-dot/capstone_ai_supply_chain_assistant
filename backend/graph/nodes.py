"""
LangGraph node functions for the supply chain query pipeline.
Each node receives the full state, does its work, and returns a partial state update.

Execution order:
  general_check_node → (general) → general_node → END
  general_check_node → (supply chain) → nlsql_node → classify_node
    → (specialists) → retrieve_node → orchestrator_node → summary_node → recommendation_node → END
    → (no specialists) → recommendation_node → END

The orchestrator_node runs specialist agents in the order chosen by classify_node,
passing accumulated findings from earlier agents into later ones.
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
from agents.nlsql_agent import NLSQLAgent
from retrieval.hybrid_search import hybrid_search
from retrieval.reranker import rerank
from llm.client import chat


# ── General check ────────────────────────────────────────────────────────────

GENERAL_CHECK_SYSTEM = """You are a supply chain query filter.
Determine if the query is related to supply chain operations (suppliers, shipments,
inventory, warehouses, logistics, delivery, products, carriers, routes) or completely unrelated.

Return ONLY valid JSON: {"is_supply_chain": true} or {"is_supply_chain": false}
Return false ONLY if the query has zero supply chain content whatsoever."""

# Supply chain signal words — safety net for the general check
_SC_KEYWORDS = {
    "supplier", "shipment", "delivery", "warehouse", "inventory", "stock",
    "carrier", "route", "delay", "risk", "defect", "order", "product",
    "shipping", "freight", "logistics", "dispatch", "fulfilment", "fulfillment",
    "reorder", "stockout", "lead time", "transit", "cargo", "vendor",
    "latam", "europe", "usca", "region", "pacific", "africa",
}


def general_check_node(state: SupplyChainState) -> dict:
    """Binary check: supply chain query or off-topic? Runs before everything else."""
    t0    = time.time()
    query = state["query"]

    is_supply_chain = True  # safe default
    try:
        response = chat([
            {"role": "system", "content": GENERAL_CHECK_SYSTEM},
            {"role": "user",   "content": f"Query: {query}"}
        ])
        start = response.find("{"); end = response.rfind("}") + 1
        parsed = json.loads(response[start:end])
        is_supply_chain = parsed.get("is_supply_chain", True)
    except Exception:
        pass

    # Safety net: keyword override
    if not is_supply_chain and any(kw in query.lower() for kw in _SC_KEYWORDS):
        is_supply_chain = True

    agents = ["supply_chain"] if is_supply_chain else ["general"]
    log    = state.get("execution_log", [])
    log.append({
        "step":   "General Check",
        "icon":   "🔍",
        "detail": "Supply chain query — proceeding" if is_supply_chain else "Off-topic — routing to general QA",
        "ms":     round((time.time() - t0) * 1000),
    })
    return {"routed_agents": agents, "execution_log": log}


# ── Specialist classifier ────────────────────────────────────────────────────

SPECIALIST_CLASSIFIER_SYSTEM = """You are a supply chain specialist router.
SQL has already run and extracted exact entity names. Decide which specialist agents
are needed for deeper risk analysis, AND the order they should run.

Available specialists:
- supplier  : supplier performance, reliability, risk, defect rates
- shipment  : delivery routes, delays, shipping modes, carriers, regions, at-risk shipments
- inventory : stock levels, warehouses, stockouts, days of supply

Ordering rules — put the most data-rich agent for this query FIRST:
- Query is primarily about warehouses/stock → inventory first
- Query is primarily about supplier risk/reliability → supplier first
- Query is primarily about routes/delays/carriers → shipment first
- When agents are equally relevant, default order: supplier → shipment → inventory
- Return [] if the SQL answer is self-contained and no specialist adds value.

Return ONLY valid JSON with agents in execution order: {"agents": ["inventory", "supplier"]}"""


def classify_node(state: SupplyChainState) -> dict:
    """Specialist-only classifier. Runs after nlsql_node so sql_entities are available."""
    t0           = time.time()
    query        = state["query"]
    sql_entities = state.get("sql_entities") or {}

    # Build entity context for the classifier
    entity_lines = []
    if sql_entities.get("supplier_names"):
        entity_lines.append(f"SQL identified suppliers: {', '.join(sql_entities['supplier_names'])}")
    if sql_entities.get("warehouse_names"):
        entity_lines.append(f"SQL identified warehouses: {', '.join(sql_entities['warehouse_names'])}")
    if sql_entities.get("product_names"):
        entity_lines.append(f"SQL identified products: {', '.join(sql_entities['product_names'])}")
    entity_context = ("\n" + "\n".join(entity_lines)) if entity_lines else ""

    agents: list = []
    try:
        response = chat([
            {"role": "system", "content": SPECIALIST_CLASSIFIER_SYSTEM},
            {"role": "user",   "content": f"Query: {query}{entity_context}"}
        ])
        start  = response.find("{"); end = response.rfind("}") + 1
        parsed = json.loads(response[start:end])
        valid  = {"supplier", "shipment", "inventory"}
        agents = [a for a in parsed.get("agents", []) if a in valid]
    except Exception:
        # Keyword fallback
        q = query.lower()
        if any(k in q for k in {"supplier", "vendor", "defect", "reliability"}):
            agents.append("supplier")
        if any(k in q for k in {"shipment", "delivery", "carrier", "route", "delay",
                                  "transit", "shipping", "freight", "latam", "region"}):
            agents.append("shipment")
        if any(k in q for k in {"inventory", "stock", "warehouse", "stockout", "reorder"}):
            agents.append("inventory")

    log = state.get("execution_log", [])
    log.append({
        "step":   "Specialist Classification",
        "icon":   "🎯",
        "detail": f"Specialists: {', '.join(agents)}" if agents else "No specialists — SQL answer sufficient",
        "agents": agents,
        "ms":     round((time.time() - t0) * 1000),
    })
    return {"routed_agents": agents, "execution_log": log}


# ── Retrieval ────────────────────────────────────────────────────────────────

def retrieve_node(state: SupplyChainState) -> dict:
    t0    = time.time()
    query = state["query"]

    sql_entities    = state.get("sql_entities") or {}
    supplier_names  = sql_entities.get("supplier_names",  [])
    warehouse_names = sql_entities.get("warehouse_names", [])
    all_entity_names = supplier_names + warehouse_names

    retrieval_query = f"{query} {' '.join(all_entity_names[:4])}" if all_entity_names else query
    user_filters    = state.get("filters") or {}
    target_k        = state.get("top_k", 5)

    # ── Step 1: Fetch pre-aggregated profile docs for SQL-identified entities ──
    # Profiles contain delay rates, avg/max delay, inventory impact — better than
    # individual shipment events for supplier/warehouse performance questions.
    profile_docs: list = []
    if supplier_names:
        profile_filter = {"doc_type": "supplier_profile", "supplier_name": supplier_names}
        profile_docs = hybrid_search(query, top_k=min(len(supplier_names), 8),
                                     filters=profile_filter)
    elif warehouse_names:
        profile_filter = {"doc_type": "warehouse_profile", "warehouse_name": warehouse_names}
        profile_docs = hybrid_search(query, top_k=min(len(warehouse_names), 5),
                                     filters=profile_filter)

    # ── Step 2: Fetch shipment event docs for incident-level context ───────────
    entity_filter: dict = {}
    if supplier_names:
        entity_filter["supplier_name"] = supplier_names
    elif warehouse_names:
        entity_filter["warehouse_name"] = warehouse_names

    combined_filters = {**entity_filter, **user_filters} if entity_filter else user_filters or None
    shipment_docs = hybrid_search(retrieval_query, top_k=15, filters=combined_filters)

    # Fallback: if entity filter was too restrictive, relax to user filters only
    if len(shipment_docs) < 2 and entity_filter:
        shipment_docs = hybrid_search(retrieval_query, top_k=15, filters=user_filters or None)

    # ── Step 3: Combine — profiles guaranteed first, shipments fill remaining ──
    seen: set = set()
    combined: list = []
    for doc in profile_docs:
        if doc["id"] not in seen:
            seen.add(doc["id"])
            combined.append(doc)

    remaining = max(target_k - len(combined), 2)
    for doc in rerank(query, shipment_docs, top_k=remaining):
        if doc["id"] not in seen:
            seen.add(doc["id"])
            combined.append(doc)

    profile_count  = sum(1 for d in combined
                         if d.get("metadata", {}).get("doc_type")
                         in ("supplier_profile", "warehouse_profile"))
    shipment_count = len(combined) - profile_count
    entity_note    = f" (SQL-targeted: {', '.join(all_entity_names[:3])})" if all_entity_names else ""

    log = state.get("execution_log", [])
    log.append({
        "step":           "Vector Retrieval",
        "icon":           "🗄️",
        "detail":         f"{profile_count} profiles + {shipment_count} shipments retrieved{entity_note}",
        "docs_retrieved": len(combined),
        "profile_count":  profile_count,
        "shipment_count": shipment_count,
        "ms":             round((time.time() - t0) * 1000),
    })
    return {"retrieved_incidents": combined, "execution_log": log}


# ── Orchestrator node ─────────────────────────────────────────────────────────

_AGENT_META = {
    "supplier":  {"label": "Supplier Risk Agent", "icon": "🏭"},
    "shipment":  {"label": "Shipment Agent",       "icon": "🚢"},
    "inventory": {"label": "Inventory Agent",      "icon": "📦"},
}


def _run_agent(name: str, state: dict, findings_so_far: dict) -> dict:
    """Call the right agent class based on name, injecting accumulated context."""
    query = state["query"]
    docs  = state["retrieved_incidents"]
    if name == "supplier":
        return SupplierRiskAgent().analyze(
            query, docs,
            sql_entities=state.get("sql_entities") or {},
            prior_findings=findings_so_far,
        )
    if name == "shipment":
        return ShipmentAgent().analyze(
            query, docs,
            prior_findings=findings_so_far,
        )
    if name == "inventory":
        return InventoryAgent().analyze(
            query, docs,
            sql_answer=state.get("answer", ""),
            prior_findings=findings_so_far,
        )
    return {}


def orchestrator_node(state: SupplyChainState) -> dict:
    """Run specialist agents in the classifier-determined order, passing accumulated findings forward."""
    ordered = [a for a in state["routed_agents"] if a in _AGENT_META]
    findings = dict(state.get("agent_findings", {}))
    log      = list(state.get("execution_log", []))

    t_total = time.time()

    # Header log entry — records the execution plan
    log.append({
        "step":   "Orchestrator",
        "icon":   "🎛️",
        "detail": f"Running {len(ordered)} agent(s) in order: {' → '.join(ordered)}",
        "agents": ordered,
        "ms":     0,
    })
    header_idx = len(log) - 1

    for agent_name in ordered:
        t0     = time.time()
        result = _run_agent(agent_name, state, findings)
        findings[agent_name] = result

        top_finding = result.get("findings", [None])[0]
        entry = {
            "step":           _AGENT_META[agent_name]["label"],
            "icon":           _AGENT_META[agent_name]["icon"],
            "detail":         result.get("summary", "")[:120],
            "risk_level":     result.get("risk_level", "unknown"),
            "confidence":     round(result.get("confidence", 0) * 100),
            "findings_count": len(result.get("findings", [])),
            "top_finding":    str(top_finding)[:100] if top_finding else None,
            "ms":             round((time.time() - t0) * 1000),
        }
        if agent_name == "supplier":
            affected = result.get("affected_suppliers") or []
            if affected:
                entry["affected_suppliers"] = affected[:3]
        if agent_name == "inventory":
            warehouses = result.get("at_risk_warehouses") or []
            if warehouses:
                entry["warehouses_at_risk"] = warehouses[:3]
        log.append(entry)

    log[header_idx]["ms"] = round((time.time() - t_total) * 1000)

    return {"agent_findings": findings, "execution_log": log}


# ── NL-to-SQL node ───────────────────────────────────────────────────────────

def nlsql_node(state: SupplyChainState) -> dict:
    t0     = time.time()
    result = NLSQLAgent().analyze(state["query"])

    entities = result.get("sql_entities", {})
    entity_names = (
        entities.get("supplier_names", []) +
        entities.get("warehouse_names", []) +
        entities.get("product_names", [])
    )

    log = state.get("execution_log", [])
    log.append({
        "step":           "NL→SQL Agent",
        "icon":           "🗃️",
        "detail":         f"{len(result['sql_queries'])} SQL query/queries executed",
        "sql_queries":    result["sql_queries"],
        "rows_returned":  result.get("rows_returned"),
        "entities_found": entity_names[:6] if entity_names else None,
        "ms":             round((time.time() - t0) * 1000),
    })

    return {
        "sql_result":       "\n\n".join(result["sql_queries"]),
        "sql_data":         result.get("sql_data", ""),
        "answer":           result["answer"],
        "confidence_score": result["confidence"],
        "execution_log":    log,
        "agent_findings":   {
            **state.get("agent_findings", {}),
            "nlsql": {
                "summary":     result["summary"],
                "risk_level":  result["risk_level"],
                "confidence":  result["confidence"],
                "findings":    result["findings"],
                "sql_queries": result["sql_queries"],
            },
        },
        "sql_entities": result["sql_entities"],
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

    anomaly_types = [a.get("type", "").replace("_", " ") for a in anomalies]

    log = state.get("execution_log", [])
    log.append({
        "step":          "Summary Generation",
        "icon":          "✦",
        "detail":        f"Confidence: {round(confidence * 100)}% | Anomalies detected: {len(anomalies)}",
        "confidence":    round(confidence * 100),
        "anomalies":     len(anomalies),
        "anomaly_types": anomaly_types if anomaly_types else None,
        "ms":            round((time.time() - t0) * 1000),
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


def route_after_general_check(state: SupplyChainState) -> str:
    if "general" in state["routed_agents"]:
        return "general_node"
    return "nlsql_node"


def route_after_classify(state: SupplyChainState) -> str:
    if any(a in state["routed_agents"] for a in _SC_AGENTS):
        return "retrieve_node"
    return "recommendation_node"
