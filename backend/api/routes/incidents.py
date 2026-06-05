from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from retrieval.vector_store import get_collection, semantic_search
from retrieval.hybrid_search import hybrid_search
from retrieval.reranker import rerank
from api.schemas import SimilarIncidentRequest
from llm.client import embed

router = APIRouter()


@router.get("/incidents", summary="List incidents with optional filters")
async def list_incidents(
    doc_type:                 Optional[str] = Query(default="shipment"),
    supplier_id:              Optional[str] = Query(None),
    supplier_name:            Optional[str] = Query(None),
    supplier_category:        Optional[str] = Query(None),
    supplier_region:          Optional[str] = Query(None),
    risk_tier:                Optional[str] = Query(None),
    shipment_status:          Optional[str] = Query(None),
    severity:                 Optional[str] = Query(None),
    shipping_mode:            Optional[str] = Query(None),
    warehouse_region:         Optional[str] = Query(None),
    warehouse_id:             Optional[str] = Query(None),
    destination_warehouse_id: Optional[str] = Query(None),
    inventory_status:         Optional[str] = Query(None),
    limit:  int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0,  ge=0),
):
    collection = get_collection()
    if collection.count() == 0:
        return {"incidents": [], "total": 0, "offset": offset, "limit": limit}

    where_conditions = []

    # doc_type filter — drives which collection is queried
    where_conditions.append({"doc_type": {"$eq": doc_type}})

    # ── Shipment filters ──────────────────────────────────────────────────
    if supplier_id:
        where_conditions.append({"supplier_id":              {"$eq": supplier_id}})
    if supplier_name:
        where_conditions.append({"supplier_name":            {"$eq": supplier_name}})
    if risk_tier:
        where_conditions.append({"risk_tier":                {"$eq": risk_tier}})
    if shipment_status:
        where_conditions.append({"shipment_status":          {"$eq": shipment_status}})
    if severity:
        where_conditions.append({"severity":                 {"$eq": severity}})
    if shipping_mode:
        where_conditions.append({"shipping_mode":            {"$eq": shipping_mode}})
    if warehouse_region:
        where_conditions.append({"warehouse_region":         {"$eq": warehouse_region}})
    if inventory_status:
        where_conditions.append({"inventory_status":         {"$eq": inventory_status}})
    if destination_warehouse_id:
        where_conditions.append({"warehouse_id": {"$eq": destination_warehouse_id}})

    # ── Supplier profile filters ──────────────────────────────────────────
    if supplier_category:
        where_conditions.append({"supplier_category":        {"$eq": supplier_category}})
    if supplier_region:
        where_conditions.append({"supplier_region":          {"$eq": supplier_region}})

    # ── Warehouse profile filters ─────────────────────────────────────────
    if warehouse_id:
        where_conditions.append({"warehouse_id":             {"$eq": warehouse_id}})

    kwargs = {
        "include": ["documents", "metadatas"],
        "limit":   limit,
        "offset":  offset,
    }
    if where_conditions:
        kwargs["where"] = (
            {"$and": where_conditions} if len(where_conditions) > 1 else where_conditions[0]
        )

    results = collection.get(**kwargs)

    incidents = [
        {
            "id":       results["ids"][i],
            "text":     results["documents"][i],
            "metadata": results["metadatas"][i],
        }
        for i in range(len(results["ids"]))
    ]

    return {"incidents": incidents, "total": len(incidents), "offset": offset, "limit": limit}


@router.get("/incidents/{incident_id}", summary="Get a single incident by ID")
async def get_incident(incident_id: str):
    collection = get_collection()
    result = collection.get(ids=[incident_id], include=["documents", "metadatas"])

    if not result["ids"]:
        raise HTTPException(status_code=404, detail="Incident not found")

    return {
        "id":       result["ids"][0],
        "text":     result["documents"][0],
        "metadata": result["metadatas"][0],
    }


@router.post("/incidents/similar", summary="Find similar incidents by text")
async def find_similar(request: SimilarIncidentRequest):
    query_embedding = embed([request.incident_text])[0]
    where = None
    if request.filters:
        f = {k: v for k, v in request.filters.model_dump().items() if v is not None}
        if f:
            conditions = [{k: {"$eq": str(v)}} for k, v in f.items()]
            where = {"$and": conditions} if len(conditions) > 1 else conditions[0]

    hits = semantic_search(query_embedding, top_k=request.top_k, where=where)
    return {"similar_incidents": hits, "total": len(hits)}
