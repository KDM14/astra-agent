"""FastAPI application factory for Astra Agent."""

from __future__ import annotations

import pathlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from astra_agent.api.routes import router as api_router
from astra_agent.core.config import settings
from astra_agent.observability.logger import setup_logging


def create_app() -> FastAPI:
    """Builds and configures the FastAPI application."""
    setup_logging(level=settings.log_level)

    app = FastAPI(
        title="Astra Agent API",
        version="0.1.0",
        description="Production-oriented, autonomous, verified open-source AI agent system.",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    # Mount static files for dashboard if directory exists
    static_dir = pathlib.Path(__file__).parent.parent / "web" / "static"
    if static_dir.exists():
        app.mount("/ui", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


app = create_app()
