"""
main.py
-------
FastAPI application entry point for Lodestone.

This file creates the FastAPI app instance and wires together:
  - Startup lifecycle: creates DB tables when the server starts
  - Route mounting: registers all API routers (added in later checkpoints)

Run the server with:
    uvicorn main:app --reload
  
  - 'main' refers to this file (main.py)
  - 'app' refers to the FastAPI() instance defined below
  - '--reload' auto-restarts the server when you save any .py file
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from db import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager — runs startup and shutdown logic.

    Code before 'yield' runs ONCE when the server starts.
    Code after 'yield' runs ONCE when the server shuts down.

    This replaces the older @app.on_event("startup") decorator pattern,
    which is deprecated in modern FastAPI versions.
    """
    # ── Startup ──────────────────────────────────────────────────────────────
    # Create all database tables if they don't already exist.
    # This is safe to run every startup — CREATE TABLE IF NOT EXISTS.
    print("[Lodestone] Starting up — creating database tables...")
    create_tables()
    print("[Lodestone] Database ready.")

    yield  # ← server is live and serving requests here

    # ── Shutdown ─────────────────────────────────────────────────────────────
    # Nothing to clean up for SQLite. If we were using a connection pool
    # (Postgres), we'd close it here.
    print("[Lodestone] Shutting down.")


# Create the FastAPI application instance.
# - title and description appear in the auto-generated /docs UI.
# - lifespan= attaches our startup/shutdown handler.
app = FastAPI(
    title="Lodestone API",
    description="AI-Powered Socratic Coding Education Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Enable CORS for frontend API calls
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for the hackathon showcase
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health check endpoint ──────────────────────────────────────────────────────
# A simple GET / that returns OK — useful to confirm the server is alive
# before testing the real endpoints.
@app.get("/", tags=["health"])
def health_check():
    """Returns a status message confirming the server is running."""
    return {"status": "ok", "service": "Lodestone API"}


# ── Route mounting ────────────────────────────────────────────────────────────
# Each feature area has its own router module in routes/.
# We import the router and mount it with a URL prefix.
# Tags group the endpoints in the /docs UI.
from routes.session import router as session_router
app.include_router(session_router, prefix="/session", tags=["session"])

from routes.dashboard import router as dashboard_router
app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
