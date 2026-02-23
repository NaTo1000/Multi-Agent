"""
OTA Flasher — uploads a firmware binary to one or many ESP32 devices
via the device HTTP OTA endpoint.
"""

import asyncio
import http.server
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class _BinaryHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Minimal HTTP handler that serves a single binary file."""

    def log_message(self, fmt, *args):  # suppress noisy access log
        pass


class OTAFlasher:
    """
    Serves a firmware binary over a temporary HTTP server and triggers
    OTA updates on one or more ESP32 devices.
    """

    def __init__(self, host_ip: Optional[str] = None, port: int = 8888):
        self.host_ip = host_ip or self._get_local_ip()
        self.port = port
        self._server: Optional[http.server.HTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # HTTP server lifecycle
    # ------------------------------------------------------------------

    def _start_server(self, serve_dir: str) -> None:
        os.chdir(serve_dir)
        self._server = http.server.HTTPServer(("", self.port), _BinaryHTTPHandler)
        self._server_thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._server_thread.start()
        logger.info("OTA HTTP server started on %s:%d", self.host_ip, self.port)

    def _stop_server(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None
        logger.info("OTA HTTP server stopped")

    # ------------------------------------------------------------------
    # Flash a single device
    # ------------------------------------------------------------------

    async def flash_device(
        self, device: Any, binary_path: str
    ) -> Dict[str, Any]:
        """
        Flash `binary_path` to `device` via OTA.

        Starts a temporary HTTP server, sends the OTA command, then tears
        the server down.
        """
        path = Path(binary_path)
        if not path.exists():
            return {"ok": False, "device_id": device.device_id, "reason": "binary_not_found"}

        self._start_server(str(path.parent))
        firmware_url = f"http://{self.host_ip}:{self.port}/{path.name}"
        try:
            ok = await device.flash_firmware(firmware_url)
            return {"ok": ok, "device_id": device.device_id, "firmware_url": firmware_url}
        finally:
            self._stop_server()

    # ------------------------------------------------------------------
    # Flash multiple devices simultaneously
    # ------------------------------------------------------------------

    async def flash_fleet(
        self, devices: List[Any], binary_path: str
    ) -> List[Dict[str, Any]]:
        """Flash the same binary to a list of devices concurrently."""
        path = Path(binary_path)
        if not path.exists():
            return [{"ok": False, "device_id": d.device_id, "reason": "binary_not_found"}
                    for d in devices]

        self._start_server(str(path.parent))
        firmware_url = f"http://{self.host_ip}:{self.port}/{path.name}"
        try:
            results = await asyncio.gather(
                *[device.flash_firmware(firmware_url) for device in devices],
                return_exceptions=True,
            )
            return [
                {
                    "ok": r is True,
                    "device_id": devices[i].device_id,
                    "firmware_url": firmware_url,
                    "error": str(r) if isinstance(r, Exception) else None,
                }
                for i, r in enumerate(results)
            ]
        finally:
            self._stop_server()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _get_local_ip() -> str:
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:  # pylint: disable=broad-except
            return "127.0.0.1"
