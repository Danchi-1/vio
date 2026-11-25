from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from vio_backend.config import Settings
from vio_backend.database import make_engine, make_session_factory
from vio_backend.errors import register_error_handlers
from vio_backend.routers import auth, authority, catalogue, dashboard, findings, lecturer, reports, student


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_environment()
    app.state.settings = settings
    app.state.session_factory = None
    app.state.engine = None
    if settings.database_url:
        engine = make_engine(settings.database_url)
        app.state.engine = engine
        app.state.session_factory = make_session_factory(engine)
    yield
    if app.state.engine is not None:
        await app.state.engine.dispose()


app = FastAPI(title="VIO API", version="0.1.0", lifespan=lifespan)
frontend_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://127.0.0.1:5500,http://localhost:5500",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key", "Authorization", "X-Worker-Secret"],
)
register_error_handlers(app)
app.include_router(catalogue.router)
app.include_router(auth.router)
app.include_router(student.router)
app.include_router(reports.router)
app.include_router(findings.router)
app.include_router(lecturer.router)
app.include_router(authority.router)
app.include_router(dashboard.router)


@app.get("/health/live", tags=["health"])
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
async def readiness(request: Request) -> dict[str, str]:
    factory = request.app.state.session_factory
    if factory is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        async with factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    return {"status": "ready", "database": "connected"}
