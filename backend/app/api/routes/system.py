from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import DB
from app.core.config import settings
from app.schemas.api import MetaOut

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict:
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(db: DB) -> JSONResponse:
    """Readiness: the database is reachable and pgvector is installed."""
    try:
        await db.execute(text("SELECT 1"))
        has_vector = await db.scalar(text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "down"})
    return JSONResponse(content={"status": "ok", "database": "up", "pgvector": bool(has_vector)})


@router.get("/meta", response_model=MetaOut)
async def meta() -> MetaOut:
    return MetaOut(
        version=settings.app_version,
        environment=settings.environment,
        llm_provider=settings.llm_provider,
        llm_model="mock-heuristic-v1" if settings.llm_provider == "mock" else settings.llm_model,
        embedding_provider=settings.embedding_provider,
        email_delivery=settings.email_delivery,
        allow_public_signup=settings.allow_public_signup,
        max_upload_mb=settings.max_upload_mb,
        max_files_per_upload=settings.max_files_per_upload,
    )
