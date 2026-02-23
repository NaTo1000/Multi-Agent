"""
FastAPI application factory.
Mounts REST routes and the WebSocket endpoint.
"""

import logging

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

    app = FastAPI(
        title="Multi-Agent ESP32 Orchestration API",
        description=(
            "REST + WebSocket API for real-time multi-agent orchestration "
            "of ESP32 modules with AI-driven frequency control, modulation, "
            "firmware OTA deployment, GPS/GNSS tracking, and cloud integration."
        ),
        version="1.0.0",
    )

    # Allow cross-origin requests (mobile apps, web dashboards)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Attach the orchestrator to app state
    if orchestrator is None:
        from orchestrator import Orchestrator
        orchestrator = Orchestrator()
    app.state.orchestrator = orchestrator

    # Register startup / shutdown hooks
    @app.on_event("startup")
    async def _startup():
        import asyncio
        asyncio.ensure_future(orchestrator.start())
        logger.info("Orchestrator started via API startup hook")

    @app.on_event("shutdown")
    async def _shutdown():
        await orchestrator.stop()
        logger.info("Orchestrator stopped via API shutdown hook")

    # Mount routers
    app.include_router(build_router(), prefix="/api/v1")
    app.include_router(build_ws_router(), prefix="/ws")

    @app.get("/health", tags=["System"])
    async def health():
        return {"status": "ok"}

    return app
