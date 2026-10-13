"""
CEREVIORA — FastAPI Application Entry Point

This file creates the FastAPI application, configures middleware,
registers all route modules ("routers"), and initialises the database.

Think of it as the main() function of the backend.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.api import health

# ---------------------------------------------------------------------------
# Create the tables in the database (if they don't already exist).
# In production you would use Alembic migrations instead, but for
# development this approach is fast and simple.
# ---------------------------------------------------------------------------
Base.metadata.create_all(bind=engine)

# ---------------------------------------------------------------------------
# Create the FastAPI application instance.
# The metadata here appears in the auto-generated docs at /docs
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered personal intelligence and task automation platform.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS (Cross-Origin Resource Sharing)
#
# Browsers block JavaScript on one origin (e.g. localhost:5173) from calling
# an API on a different origin (e.g. localhost:8000) unless the server
# explicitly allows it.  CORS middleware adds the required HTTP headers.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Register route modules
# Each router is a mini-application with its own set of endpoints.
# ---------------------------------------------------------------------------
app.include_router(health.router)


@app.get("/", tags=["System"])
def root():
    """Redirect hint for the root path."""
    return {"message": "Welcome to CEREVIORA API. Visit /docs for the full API reference."}
