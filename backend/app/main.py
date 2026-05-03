"""FastAPI application factory + entrypoint.

Run locally:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app import __version__
from app.config import settings
from app.routes import datasets, history, query
from app.services.database import init_db
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "Starting Autonomous AI Data Analyst v{} env={} llm_model={}",
        __version__, settings.app_env, settings.openai_model,
    )
    init_db()
    if not settings.openai_api_key:
        logger.warning(
            "OPENAI_API_KEY not set. Upload + browse will work, but /query will fail."
        )
    yield
    logger.info("Shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Autonomous AI Data Analyst",
        description=(
            "Upload CSVs, ask questions in natural language, and let an agent "
            "(Planner / Executor / Critic) run SQL + pandas + charts to answer."
        ),
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(datasets.router)
    app.include_router(query.router)
    app.include_router(history.router)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        logger.exception("Unhandled error")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"{type(exc).__name__}: {exc}"},
        )

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__, "env": settings.app_env}

    return app


app = create_app()
