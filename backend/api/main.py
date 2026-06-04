import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import query, incidents
from config import FRONTEND_URL

app = FastAPI(
    title="Supply Chain Risk Intelligence API",
    description="AI-powered supply chain risk analysis and recommendation system using hybrid RAG and multi-agent orchestration.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query.router, prefix="/api", tags=["Query"])
app.include_router(incidents.router, prefix="/api", tags=["Incidents"])



@app.get("/api/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "Supply Chain Risk Intelligence API", "version": "1.0.0"}
