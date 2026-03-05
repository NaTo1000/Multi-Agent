"""
ESP32 device model -- represents a single physical ESP32 module.
Stores connectivity info, current firmware version, and capability flags.

Uses httpx for non-blocking async HTTP communication with devices.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class DeviceStatus(Enum):
    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    UPDATING = "updating"
    ERROR = "error"


class DeviceCapability(Enum):
    WIFI = "wifi"
    BLE = "ble"
    GPS = "gps"
    GNSS = "gnss"
    LORA = "lora"


class ESP32Device:
    """
    Represents a single ESP32 module in the fleet.

    Tracks connectivity, hardware capabilities, current operating
    frequency, firmware version, and provides async helpers for
    sending commands over the air via non-blocking httpx.
    """

    # Shared httpx client -- initialised once per process for connection pooling
    _http_client: Optional[httpx.AsyncClient] = None

    @classmethod
    def get_http_client(cls) -> httpx.AsyncClient:
        """Return (and lazily create) the shared async HTTP client."""
        if cls._http_client is None or cls._http_client.is_closed:
            cls._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )
        return cls._http_client

    @classmethod
    async def close_http_client(cls) -> None:
        """Gracefully close the shared HTTP client (call on shutdown)."""
        if cls._http_client and not cls._http_client.is_closed:
            await cls._http_client.aclose()
            cls._http_client = None

    def __init__(
        self,
        device_id: str,
        name: str,
        ip_address: Optional[str] = None,
        mac_address: Optional[str] = None,
        capabilities: Optional[List[DeviceCapability]] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.device_id = device_id
        self.name = name
        self.ip_address = ip_address
        self.mac_address = mac_address
        self.capabilities: List[DeviceCapability] = capabilities or [
            DeviceCapability.WIFI,
            DeviceCapability.BLE,
        ]
        self.config: Dict[str, Any] = config or {}
        self.status: DeviceStatus = DeviceStatus.UNKNOWN
        self.firmware_version: str = self.config.get("firmware_version", "0.0.0")
        self.current_frequency: float = self.config.get("frequency_hz", 2.4e9)
        self.rssi: Optional[int] = None
        self.last_seen: Optional[str] = None
        self.telemetry: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Connectivity
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        """
        Ping the device over the network.
        Returns True if the device responds, False otherwise.
        """
        if not self.ip_address:
            self.status = DeviceStatus.OFFLINE
            return False
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", "2", self.ip_address,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5)
            online = proc.returncode == 0
            self.status = DeviceStatus.ONLINE if online else DeviceStatus.OFFLINE
            if online:
                self.last_seen = datetime.now(timezone.utc).isoformat()
            return online
        except Exception as exc:
            logger.warning("Ping failed for %s: %s", self.device_id, exc)
            self.status = DeviceStatus.OFFLINE
            return False

    async def send_command(
        self, command: str, payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a JSON command to the device via async HTTP (httpx).
        Requires the device to be running the companion firmware.
        """
        if not self.ip_address:
            raise ConnectionError(f"Device {self.device_id} has no IP address")

        url = f"http://{self.ip_address}/api/command"
        body = {"command": command, "payload": payload or {}}

        client = self.get_http_client()
        try:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException as exc:
            logger.error("Timeout sending '%s' to %s: %s", command, self.device_id, exc)
            raise ConnectionError(f"Timeout communicating with {self.device_id}") from exc
        except httpx.HTTPStatusError as exc:
            logger.error("HTTP %d from %s on '%s': %s", exc.response.status_code,
                         self.device_id, command, exc)
            raise
        except httpx.RequestError as exc:
            logger.error("Command '%s' failed on %s: %s", command, self.device_id, exc)
            raise ConnectionError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Frequency / modulation
    # ------------------------------------------------------------------

    async def set_frequency(self, frequency_hz: float) -> bool:
        """Tune the device to the specified frequency (Hz)."""
        try:
            resp = await self.send_command("set_frequency", {"frequency_hz": frequency_hz})
            if resp.get("status") == "ok":
                self.current_frequency = frequency_hz
                logger.info("Device %s tuned to %.3f MHz", self.device_id, frequency_hz / 1e6)
                return True
            return False
        except Exception:
            return False

    async def get_rssi(self) -> Optional[int]:
        """Read current RSSI from the device."""
        try:
            resp = await self.send_command("get_rssi")
            self.rssi = resp.get("rssi")
            return self.rssi
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Firmware
    # ------------------------------------------------------------------

    async def flash_firmware(self, firmware_url: str) -> bool:
        """Trigger an OTA firmware update on the device."""
        logger.info("OTA update initiated on %s from %s", self.device_id, firmware_url)
        self.status = DeviceStatus.UPDATING
        try:
            resp = await self.send_command("ota_update", {"url": firmware_url})
            if resp.get("status") == "ok":
                self.firmware_version = resp.get("new_version", self.firmware_version)
                self.status = DeviceStatus.ONLINE
                return True
            self.status = DeviceStatus.ERROR
            return False
        except Exception as exc:
            logger.error("OTA update failed on %s: %s", self.device_id, exc)
            self.status = DeviceStatus.ERROR
            return False

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    def update_telemetry(self, data: Dict[str, Any]) -> None:
        """Merge incoming telemetry data from the device."""
        self.telemetry.update(data)
        self.last_seen = datetime.now(timezone.utc).isoformat()
        if "rssi" in data:
            self.rssi = data["rssi"]
        if "frequency_hz" in data:
            self.current_frequency = data["frequency_hz"]

    def has_capability(self, cap: DeviceCapability) -> bool:
        return cap in self.capabilities

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "ip_address": self.ip_address,
            "mac_address": self.mac_address,
            "status": self.status.value,
            "firmware_version": self.firmware_version,
            "current_frequency_hz": self.current_frequency,
            "rssi": self.rssi,
            "last_seen": self.last_seen,
            "capabilities": [c.value for c in self.capabilities],
            "telemetry": self.telemetry,
        }
