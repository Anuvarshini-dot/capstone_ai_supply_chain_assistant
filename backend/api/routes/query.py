from fastapi import APIRouter, HTTPException
from api.schemas import QueryRequest, QueryResponse
from guardrails.input_validator import validate_query, ValidationError
from graph.builder import graph
from evaluation.runner import evaluate_query

router = APIRouter()


@router.post("/query", response_model=QueryResponse, summary="Natural language supply chain query")
async def query_endpoint(request: QueryRequest):
    try:
        validated_query = validate_query(request.query)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    filters = None
    if request.filters:
        filters = {k: v for k, v in request.filters.model_dump().items() if v is not None}
        if not filters:
            filters = None

    initial_state = {
        "query":               validated_query,
        "filters":             filters or {},
        "top_k":               request.top_k,
        "routed_agents":       [],
        "retrieved_incidents": [],
        "agent_findings":      {},
        "sql_result":          None,
        "answer":              "",
        "recommendations":     [],
        "anomaly_correlations": [],
        "confidence_score":    0.0,
        "evaluation":          {},
    }

    try:
        result = graph.invoke(initial_state)

        result["evaluation"] = evaluate_query(
            query=validated_query,
            answer=result.get("answer", ""),
            retrieved_docs=result.get("retrieved_incidents", []),
        )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
