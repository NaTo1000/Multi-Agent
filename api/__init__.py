"""
API package — FastAPI REST + WebSocket server for the multi-agent system.
"""

from .server import create_app

__all__ = ["create_app"]
