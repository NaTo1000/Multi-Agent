"""
WebSocket endpoint — streams real-time telemetry and orchestrator events
to connected clients (mobile apps, web dashboards).
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)

# Global set of active WebSocket connections
_connections: Set[Any] = set()


def build_ws_router():
    try:
        from fastapi import APIRouter, WebSocket, WebSocketDisconnect
    except ImportError:
        raise RuntimeError("fastapi is required")

    router = APIRouter()

    @router.websocket("/telemetry")
    async def telemetry_ws(websocket: WebSocket):
        """
        WebSocket endpoint that pushes orchestrator status and device
        telemetry to connected clients at 1 Hz.

        Clients can also send JSON commands:
          {"command": "dispatch", "agent_id": "...", "task": "...", "params": {...}}
        """
        await websocket.accept()
        _connections.add(websocket)
        orchestrator = websocket.app.state.orchestrator
        logger.info("WebSocket client connected")

        try:
            async def _push_loop():
                while True:
                    try:
                        status = orchestrator.get_status()
                        devices = [d.to_dict() for d in orchestrator.list_devices()]
                        payload = json.dumps({
                            "type": "status",
                            "orchestrator": status,
                            "devices": devices,
                        })
                        await websocket.send_text(payload)
                    except Exception:  # pylint: disable=broad-except
                        break
                    await asyncio.sleep(1)

            push_task = asyncio.ensure_future(_push_loop())

            # Receive loop
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                    await _handle_ws_message(orchestrator, websocket, msg)
                except json.JSONDecodeError:
                    await websocket.send_text(
                        json.dumps({"type": "error", "detail": "Invalid JSON"})
                    )
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        finally:
            _connections.discard(websocket)
            push_task.cancel()

    return router


async def _handle_ws_message(
    orchestrator: Any, websocket: Any, msg: Dict[str, Any]
) -> None:
    """Process an inbound WebSocket message from a client."""
    command = msg.get("command")
    if command == "dispatch":
        try:
            task_id = await orchestrator.dispatch_task(
                msg["agent_id"],
                msg["task"],
                msg.get("params", {}),
                msg.get("device_id"),
            )
            await websocket.send_text(
                json.dumps({"type": "task_queued", "task_id": task_id})
            )
        except (KeyError, ValueError) as exc:
            await websocket.send_text(
                json.dumps({"type": "error", "detail": str(exc)})
            )
    elif command == "ping":
        await websocket.send_text(json.dumps({"type": "pong"}))
    else:
        await websocket.send_text(
            json.dumps({"type": "error", "detail": f"Unknown command: {command}"})
        )


async def broadcast_event(event: Dict[str, Any]) -> None:
    """Broadcast an event to all connected WebSocket clients."""
    payload = json.dumps(event)
    dead = set()
    for ws in _connections:
        try:
            await ws.send_text(payload)
        except Exception:  # pylint: disable=broad-except
            dead.add(ws)
    _connections.difference_update(dead)
