from fastapi import APIRouter, HTTPException
from api.schemas import QueryRequest, QueryResponse
from graph.builder import graph
from evaluation.runner import evaluate_query

router = APIRouter()


@router.post("/query", response_model=QueryResponse, summary="Natural language supply chain query")
async def query_endpoint(request: QueryRequest):
    filters = None
    if request.filters:
        filters = {k: v for k, v in request.filters.model_dump().items() if v is not None}
        if not filters:
            filters = None

    initial_state = {
        "query":               request.query.strip(),
        "filters":             filters or {},
        "top_k":               request.top_k,
        "validation_passed":   None,
        "routed_agents":       [],
        "agent_sub_queries":   None,
        "retrieved_incidents": [],  # populated by orchestrator_node
        "agent_findings":      {},
        "sql_result":          None,
        "sql_data":            None,
        "sql_entities":        None,
        "answer":              "",
        "recommendations":     [],
        "anomaly_correlations": [],
        "confidence_score":    0.0,
        "evaluation":          {},
        "execution_log":       [],
    }

    try:
        result = graph.invoke(initial_state)

        result["evaluation"] = evaluate_query(
            query=request.query.strip(),
            answer=result.get("answer", ""),
            retrieved_docs=result.get("retrieved_incidents", []),
            sql_data=result.get("sql_data", ""),
            agent_findings=result.get("agent_findings", {}),
            agent_sub_queries=result.get("agent_sub_queries", {}),
        )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
