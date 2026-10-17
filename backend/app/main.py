"""ScreenIQ API — FastAPI application factory."""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, request_id_var
from app.services import tasks
from app.services.embeddings import get_embedder
from app.services.pipeline import recover_interrupted_work, stale_work_sweeper

configure_logging(settings.log_level, settings.log_json)
logger = logging.getLogger("screeniq")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "Starting %s %s (env=%s, llm=%s/%s, embeddings=%s)",
        settings.app_name, settings.app_version, settings.environment,
        settings.llm_provider, settings.llm_model, settings.embedding_provider,
    )
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    await recover_interrupted_work()
    sweeper = asyncio.create_task(stale_work_sweeper(), name="stale-work-sweeper")
    if settings.embedding_provider == "bge":
        # Warm the model in the background so the first upload isn't slow
        asyncio.get_running_loop().run_in_executor(None, get_embedder)
    yield
    sweeper.cancel()
    await tasks.drain()
    await engine.dispose()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="ScreenIQ API",
        description="AI resume screening & interview platform: parsing, semantic matching, RAG, "
        "explainable scoring, AI interviews, bias detection.",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.path != f"{settings.api_prefix}/health":
            logger.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, elapsed_ms,
                        extra={"request_id": rid})
        return response

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
