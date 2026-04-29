"""Fortunia API main application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import ingest, expenses, reports, admin, categories

app = FastAPI(
    title="Fortunia API",
    description="Personal finance sub-agent for OpenClaw",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# CORS: only localhost/LAN for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(ingest.router)
app.include_router(expenses.router)
app.include_router(reports.router)
app.include_router(admin.router)
app.include_router(categories.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    """Top-level health check endpoint."""
    return {"status": "ok"}
