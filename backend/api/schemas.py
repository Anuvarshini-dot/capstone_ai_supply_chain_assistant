from pydantic import BaseModel, Field
from typing import Optional, List, Any


class FilterParams(BaseModel):
    risk_tier: Optional[str] = None
    shipment_status: Optional[str] = None
    severity: Optional[str] = None
    shipping_mode: Optional[str] = None
    warehouse_region: Optional[str] = None
    inventory_status: Optional[str] = None
    supplier_category: Optional[str] = None


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=5, max_length=500)
    filters: Optional[FilterParams] = None
    top_k: int = Field(default=5, ge=1, le=20)


class QueryResponse(BaseModel):
    answer: str
    retrieved_incidents: List[dict]
    agent_findings: dict
    recommendations: List[dict]
    anomaly_correlations: List[dict]
    confidence_score: float
    routed_agents: List[str] = []
    evaluation: dict = {}
    execution_log: List[dict] = []
    sql_entities: Optional[dict] = None


class SimilarIncidentRequest(BaseModel):
    incident_text: str = Field(..., min_length=10)
    top_k: int = Field(default=5, ge=1, le=20)
    filters: Optional[FilterParams] = None


class RecommendationRequest(BaseModel):
    query: str = Field(..., min_length=5, max_length=500)
    incidents: Optional[List[dict]] = None
