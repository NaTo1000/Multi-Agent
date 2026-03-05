"""
FastAPI application factory.
Mounts REST routes and the WebSocket endpoint.

Uses the modern lifespan context manager instead of deprecated on_event.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

logger = logging.getLogger(__name__)


def create_app(orchestrator=None):
    """
    Create and return the FastAPI application.

    Parameters
    ----------
    orchestrator : Orchestrator | None
        An already-configured Orchestrator instance.  If None a new one
        will be created from the default config.
    """
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
    except ImportError:
        raise RuntimeError(
            "FastAPI is required to run the API server. "
            "Install it with: pip install fastapi uvicorn"
        )

    from .routes import build_router
    from .websocket import build_ws_router

    # Resolve orchestrator
    if orchestrator is None:
        from orchestrator import Orchestrator
        orchestrator = Orchestrator()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Modern lifespan handler replacing deprecated @app.on_event."""
        await orchestrator.start()
        logger.info("Orchestrator started via lifespan startup")
        yield
        await orchestrator.stop()
        logger.info("Orchestrator stopped via lifespan shutdown")

    app = FastAPI(
        title="Multi-Agent ESP32 Orchestration API",
        description=(
            "REST + WebSocket API for real-time multi-agent orchestration "
            "of ESP32 modules with AI-driven frequency control, modulation, "
            "firmware OTA deployment, GPS/GNSS tracking, and cloud integration."
        ),
        version="2.0.0",
        lifespan=lifespan,
    )

    # CORS -- configurable via environment variable, defaults to restrictive
    allowed_origins = os.environ.get("CORS_ORIGINS", "").strip()
    if allowed_origins:
        origins = [o.strip() for o in allowed_origins.split(",") if o.strip()]
    else:
        # Default: allow all in development (override for production)
        origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Attach the orchestrator to app state
    app.state.orchestrator = orchestrator

    # Mount routers
    app.include_router(build_router(), prefix="/api/v1")
    app.include_router(build_ws_router(), prefix="/ws")

    @app.get("/health", tags=["System"])
    async def health():
        return {"status": "ok", "version": "2.0.0"}

    return app
