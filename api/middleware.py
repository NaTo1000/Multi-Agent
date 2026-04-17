"""
Custom middleware for the API server.
"""

import logging
import time
from collections import defaultdict
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Paths that bypass authentication
_PUBLIC_PATHS = frozenset({"/health", "/docs", "/redoc", "/openapi.json"})


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Simple API key authentication middleware.

    Checks the ``Authorization: Bearer <key>`` header or the
    ``X-API-Key`` header against a configured key.  Public paths
    (health, docs) are exempt.
    """

    def __init__(self, app, api_key: str):
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Allow public endpoints without auth
        if path in _PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        # Allow WebSocket upgrade (WS auth handled separately)
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # Check API key
        auth = request.headers.get("authorization", "")
        api_key_header = request.headers.get("x-api-key", "")

        key: Optional[str] = None
        if auth.startswith("Bearer "):
            key = auth[7:].strip()
        elif api_key_header:
            key = api_key_header.strip()

        if key != self._api_key:
            logger.warning(
                "Unauthorized API request: %s %s from %s",
                request.method, path, request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory sliding-window rate limiter.

    Limits each client IP to ``max_requests`` per ``window_seconds``.
    """

    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self._max_requests = max_requests
        self._window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - self._window

        # Clean old entries
        self._requests[client_ip] = [
            t for t in self._requests[client_ip] if t > window_start
        ]

        if len(self._requests[client_ip]) >= self._max_requests:
            logger.warning("Rate limit exceeded for %s", client_ip)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(self._window)},
            )

        self._requests[client_ip].append(now)
        return await call_next(request)
