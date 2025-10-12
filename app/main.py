from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .db import init_db
from .cache import cache
from .routers import auth, repos, webhooks, github_app

app = FastAPI()

# Use dynamic origins from settings
allowed_origins = [
    settings.FRONTEND_ORIGIN,
    settings.BACKEND_ORIGIN,
    "http://localhost:3000",  # Development frontend
    "http://localhost:8000"   # Development backend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    """Health check endpoint including Redis status"""
    redis_healthy = cache.health_check()
    return {
        "ok": True,
        "database": "connected",  # Assuming DB is healthy if we got here
        "redis": "connected" if redis_healthy else "disconnected"
    }


app.include_router(auth.router)
app.include_router(repos.router)
app.include_router(webhooks.router)
app.include_router(github_app.router)


