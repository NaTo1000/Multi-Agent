"""
BLE manager — Bluetooth Low Energy 5 scanning and connection utilities
for the orchestration backend (host side).

Uses the 'bleak' library when available; gracefully degrades otherwise.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BLEDevice:
    """Lightweight representation of a discovered BLE peripheral."""

    def __init__(self, address: str, name: Optional[str], rssi: Optional[int]):
        self.address = address
        self.name = name or "Unknown"
        self.rssi = rssi

    def to_dict(self) -> Dict[str, Any]:
        return {"address": self.address, "name": self.name, "rssi": self.rssi}


class BLEManager:
    """
    Host-side BLE manager.

    Requires the 'bleak' Python package and a system Bluetooth adapter.
    Falls back gracefully if bleak is not installed.
    """

    def __init__(self):
        self._bleak_available = False
        try:
            import bleak  # noqa: F401
            self._bleak_available = True
        except ImportError:
            logger.warning("bleak not installed — BLE scanning unavailable. "
                           "Install with: pip install bleak")

    async def scan(self, duration: float = 5.0) -> List[BLEDevice]:
        """Scan for BLE peripherals for `duration` seconds."""
        if not self._bleak_available:
            logger.warning("BLE scan unavailable (bleak not installed)")
            return []
        try:
            from bleak import BleakScanner
            devices = await BleakScanner.discover(timeout=duration)
            return [BLEDevice(d.address, d.name, d.rssi) for d in devices]
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("BLE scan error: %s", exc)
            return []

    async def connect(self, address: str) -> Optional[Any]:
        """Connect to a BLE peripheral by address and return the client object."""
        if not self._bleak_available:
            return None
        try:
            from bleak import BleakClient
            client = BleakClient(address)
            await client.connect()
            logger.info("BLE connected to %s", address)
            return client
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("BLE connect error (%s): %s", address, exc)
            return None

    async def read_characteristic(
        self, client: Any, uuid: str
    ) -> Optional[bytes]:
        """Read a GATT characteristic from a connected BLE client."""
        try:
            return await client.read_gatt_char(uuid)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("BLE read error: %s", exc)
            return None

    async def write_characteristic(
        self, client: Any, uuid: str, data: bytes
    ) -> bool:
        """Write data to a GATT characteristic."""
        try:
            await client.write_gatt_char(uuid, data)
            return True
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("BLE write error: %s", exc)
            return False
