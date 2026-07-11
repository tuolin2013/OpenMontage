"""web_api/main.py — OpenMontage Web SaaS API (FastAPI).

Exposes deterministic REST endpoints that wrap the core pipeline engine.
LLMs are called only as API tools inside the agent; they do NOT control routing.

Run:
    uvicorn web_api.main:app --reload --port 8000
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web_api.routers import projects, stages, checkpoints

app = FastAPI(
    title="OpenMontage Web API",
    description="Deterministic SaaS API for the OpenMontage video production engine",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api/project", tags=["projects"])
app.include_router(stages.router, prefix="/api/project", tags=["stages"])
app.include_router(checkpoints.router, prefix="/api/project", tags=["checkpoints"])


@app.get("/api/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "OpenMontage Web API", "version": "2.0.0"}
