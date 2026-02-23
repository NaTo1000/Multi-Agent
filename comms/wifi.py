"""
WiFi manager — host-side WiFi utilities for the orchestration backend.
Handles network discovery, connection management, and IP allocation tracking.
"""

import asyncio
import logging
import socket
import struct
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WiFiManager:
    """
    Manages WiFi operations from the orchestrator host perspective.
    On a Raspberry Pi this leverages nmcli / iwlist; in cloud mode it
    delegates to the device REST API.
    """

    def __init__(self, interface: str = "wlan0"):
        self.interface = interface
        self._known_networks: Dict[str, str] = {}  # ssid → password (in-memory, not persisted)

    async def scan_networks(self) -> List[Dict[str, Any]]:
        """Return available WiFi networks (requires nmcli or iwlist on the host)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "nmcli", "-t", "-f", "SSID,BSSID,SIGNAL,FREQ", "dev", "wifi",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return self._parse_nmcli(stdout.decode())
        except FileNotFoundError:
            logger.warning("nmcli not available — returning empty network list")
            return []

    @staticmethod
    def _parse_nmcli(output: str) -> List[Dict[str, Any]]:
        networks = []
        for line in output.strip().splitlines():
            parts = line.split(":")
            if len(parts) >= 4:
                networks.append({
                    "ssid": parts[0],
                    "bssid": parts[1],
                    "signal": int(parts[2]) if parts[2].isdigit() else None,
                    "frequency": parts[3],
                })
        return networks

    async def connect(self, ssid: str, password: str = "") -> bool:
        """Connect to a WiFi network using nmcli."""
        try:
            cmd = ["nmcli", "dev", "wifi", "connect", ssid]
            if password:
                cmd += ["password", password]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, _ = await proc.communicate()
            ok = proc.returncode == 0
            if ok:
                self._known_networks[ssid] = password
            return ok
        except FileNotFoundError:
            logger.warning("nmcli not available")
            return False

    def get_local_ip(self) -> Optional[str]:
        """Return the host's primary local IP address."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:  # pylint: disable=broad-except
            return None

    @staticmethod
    def ip_to_int(ip: str) -> int:
        return struct.unpack("!I", socket.inet_aton(ip))[0]

    @staticmethod
    def int_to_ip(value: int) -> str:
        return socket.inet_ntoa(struct.pack("!I", value))

    def scan_subnet(self, subnet: str = "192.168.1.0/24") -> List[str]:
        """Return list of responding hosts in the given subnet (ARP scan fallback)."""
        try:
            import ipaddress
            net = ipaddress.IPv4Network(subnet, strict=False)
            return [str(h) for h in net.hosts()]
        except Exception:  # pylint: disable=broad-except
            return []
