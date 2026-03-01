"""
FastAPI application — mounts all routes and starts the server.
"""
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.api.routes import router

app = FastAPI(
    title="Hye-tasion — Armenian Reddit Post Generator",
    description="Scrape Armenian news & history, generate Reddit post ideas, A/B test for engagement.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── API key authentication middleware ─────────────────────────────────────────

API_KEY = os.getenv("API_KEY", "")


@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    """Require X-API-Key header on all /api/* routes (skip static frontend)."""
    if request.url.path.startswith("/api") and API_KEY:
        key = request.headers.get("X-API-Key", "")
        if not key or key != API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )
    response = await call_next(request)
    return response


app.include_router(router, prefix="/api")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


@app.on_event("startup")
def on_startup():
    init_db()
