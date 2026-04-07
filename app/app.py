"""
FastAPI application factory.

All router registration and middleware setup lives here.
The entry-point (main.py) simply imports `create_app()`.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import cleanup, download, orchestrator, process, transcribe, workflow


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""

    application = FastAPI(
        title=settings.app_title,
        version=settings.app_version,
        description=settings.app_description,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    application.include_router(download.router)
    application.include_router(process.router)
    application.include_router(transcribe.router)
    application.include_router(cleanup.router)
    application.include_router(orchestrator.router)
    application.include_router(workflow.router)

    # ── Health check ──────────────────────────────────────────────────────────
    @application.get("/", tags=["Health"], summary="API health check")
    def health():
        return {
            "status": "ok",
            "version": settings.app_version,
            "message": f"{settings.app_title} is running.",
        }

    return application
