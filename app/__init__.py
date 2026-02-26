"""
FastAPI application — mounts all routes and starts the server.
"""
from fastapi import FastAPI
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

app.include_router(router, prefix="/api")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


@app.on_event("startup")
def on_startup():
    init_db()
