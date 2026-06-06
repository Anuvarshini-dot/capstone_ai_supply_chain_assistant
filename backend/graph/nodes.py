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
are needed, the order they should run, and write a focused sub-question for each agent.

Available specialists:
- supplier  : supplier performance, reliability, risk, defect rates
- shipment  : delivery routes, delays, shipping modes, carriers, regions, at-risk shipments
- inventory : stock levels, warehouses, stockouts, days of supply

Rules:
- Only include agents whose sub-question is genuinely answered by their specialty.
- If the query has ONE focus (e.g. only about stock levels), return only ONE agent.
- If the query has TWO distinct parts (e.g. warehouse stock + supplier contribution), return TWO agents.
- Write each sub_query as a standalone question the agent can answer independently.
  Use exact entity names from SQL context (e.g. "Los Angeles Fulfillment Hub") in sub-queries.
- Ordering: put the most data-rich agent for this query FIRST.
  warehouse/stock focus → inventory first; supplier/risk focus → supplier first; delays → shipment first.
- Return [] if the SQL answer alone is sufficient and no specialist adds value.

Return ONLY valid JSON:
{"agents": [{"name": "inventory", "sub_query": "which warehouse has the highest stock?"}, {"name": "supplier", "sub_query": "who is the highest contributing supplier to Los Angeles Fulfillment Hub?"}]}"""


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

    agents:      list = []
    sub_queries: dict = {}
    valid = {"supplier", "shipment", "inventory"}

    try:
        response = chat([
            {"role": "system", "content": SPECIALIST_CLASSIFIER_SYSTEM},
            {"role": "user",   "content": f"Query: {query}{entity_context}"}
        ])
        start  = response.find("{"); end = response.rfind("}") + 1
        parsed = json.loads(response[start:end])

        for item in parsed.get("agents", []):
            if isinstance(item, dict) and item.get("name") in valid:
                name = item["name"]
                agents.append(name)
                sub_queries[name] = item.get("sub_query") or query
            elif isinstance(item, str) and item in valid:
                # Fallback: plain string list (old format)
                agents.append(item)
                sub_queries[item] = query
    except Exception:
        # Keyword fallback — one agent, full query
        q = query.lower()
        if any(k in q for k in {"supplier", "vendor", "defect", "reliability"}):
            agents.append("supplier"); sub_queries["supplier"] = query
        if any(k in q for k in {"shipment", "delivery", "carrier", "route", "delay",
                                  "transit", "shipping", "freight", "latam", "region"}):
            agents.append("shipment"); sub_queries["shipment"] = query
        if any(k in q for k in {"inventory", "stock", "warehouse", "stockout", "reorder"}):
            agents.append("inventory"); sub_queries["inventory"] = query

    log = state.get("execution_log", [])
    log.append({
        "step":        "Specialist Classification",
        "icon":        "🎯",
        "detail":      f"{len(agents)} specialist(s) assigned with focused sub-questions" if agents else "No specialists — SQL answer sufficient",
        "agents":      agents,
        "sub_queries": sub_queries,
        "ms":          round((time.time() - t0) * 1000),
    })
    return {"routed_agents": agents, "agent_sub_queries": sub_queries, "execution_log": log}


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


def _targeted_docs(agent_name: str, state: dict, base_docs: list) -> list:
    """Return docs targeted to this agent's role — profiles first, shipments to fill remaining slots."""
    sub_query       = (state.get("agent_sub_queries") or {}).get(agent_name) or state["query"]
    sql_entities    = state.get("sql_entities") or {}
    supplier_names  = sql_entities.get("supplier_names", [])
    warehouse_names = sql_entities.get("warehouse_names", [])

    profile_docs:  list = []
    shipment_docs: list = []

    if agent_name == "supplier":
        # 1. Supplier profiles — aggregated reliability, risk, lead time
        if supplier_names:
            profile_docs = hybrid_search(sub_query, top_k=min(len(supplier_names) + 2, 6),
                                         filters={"doc_type": "supplier_profile", "supplier_name": supplier_names})
        else:
            profile_docs = hybrid_search(sub_query, top_k=4, filters={"doc_type": "supplier_profile"})

        # 2. Shipment events filtered to the identified warehouse (if any) for contribution data
        if warehouse_names:
            shipment_docs = hybrid_search(sub_query, top_k=10, filters={"warehouse_name": warehouse_names})
        elif supplier_names:
            shipment_docs = hybrid_search(sub_query, top_k=10, filters={"supplier_name": supplier_names})

    elif agent_name == "inventory":
        # 1. Warehouse profiles — capacity, utilisation, region
        if warehouse_names:
            profile_docs = hybrid_search(sub_query, top_k=min(len(warehouse_names) + 2, 6),
                                         filters={"doc_type": "warehouse_profile", "warehouse_name": warehouse_names})
        else:
            profile_docs = hybrid_search(sub_query, top_k=4, filters={"doc_type": "warehouse_profile"})

        # 2. Inventory/shipment events for that warehouse
        if warehouse_names:
            shipment_docs = hybrid_search(sub_query, top_k=10, filters={"warehouse_name": warehouse_names})

    elif agent_name == "shipment":
        # Shipment events: warehouse-targeted if available, else supplier-targeted
        if warehouse_names:
            shipment_docs = hybrid_search(sub_query, top_k=15, filters={"warehouse_name": warehouse_names})
        elif supplier_names:
            shipment_docs = hybrid_search(sub_query, top_k=15, filters={"supplier_name": supplier_names})

    # Merge: profiles guaranteed first, shipments fill remaining slots
    seen, combined = set(), []
    for doc in profile_docs:
        if doc["id"] not in seen:
            seen.add(doc["id"])
            combined.append(doc)

    remaining = max(8 - len(combined), 2)
    for doc in rerank(sub_query, shipment_docs, top_k=remaining) if shipment_docs else []:
        if doc["id"] not in seen:
            seen.add(doc["id"])
            combined.append(doc)

    return combined if len(combined) >= 2 else base_docs


def _run_agent(name: str, sub_query: str, state: dict, findings_so_far: dict, docs: list) -> dict:
    """Call the right agent class with its focused sub-question and pre-targeted docs."""
    if name == "supplier":
        return SupplierRiskAgent().analyze(
            sub_query, docs,
            sql_entities=state.get("sql_entities") or {},
            prior_findings=findings_so_far,
        )
    if name == "shipment":
        return ShipmentAgent().analyze(
            sub_query, docs,
            prior_findings=findings_so_far,
        )
    if name == "inventory":
        return InventoryAgent().analyze(
            sub_query, docs,
            sql_answer=state.get("answer", ""),
            prior_findings=findings_so_far,
        )
    return {}


def orchestrator_node(state: SupplyChainState) -> dict:
    """Run specialist agents in classifier-determined order, each with its own focused sub-question."""
    ordered     = [a for a in state["routed_agents"] if a in _AGENT_META]
    sub_queries = state.get("agent_sub_queries") or {}
    findings    = dict(state.get("agent_findings", {}))
    log         = list(state.get("execution_log", []))

    t_total = time.time()

    # Header log entry — records the execution plan with each agent's sub-question
    plan_detail = " → ".join(
        f"{a} ({sub_queries.get(a, '...')})" for a in ordered
    )
    log.append({
        "step":   "Orchestrator",
        "icon":   "🎛️",
        "detail": f"Running {len(ordered)} agent(s): {plan_detail}",
        "agents": ordered,
        "ms":     0,
    })
    header_idx = len(log) - 1

    base_docs = state["retrieved_incidents"]

    for agent_name in ordered:
        t0        = time.time()
        sub_query = sub_queries.get(agent_name) or state["query"]
        docs      = _targeted_docs(agent_name, state, base_docs)
        result    = _run_agent(agent_name, sub_query, state, findings, docs)
        findings[agent_name] = result

        top_finding = result.get("findings", [None])[0]
        entry = {
            "step":           _AGENT_META[agent_name]["label"],
            "icon":           _AGENT_META[agent_name]["icon"],
            "detail":         result.get("summary", "")[:120],
            "sub_query":      sub_query if sub_query != state["query"] else None,
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
