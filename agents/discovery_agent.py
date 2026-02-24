"""
Auto-Discovery Agent — zero-config ESP32 fleet discovery.

Discovery methods:
1. mDNS / Zeroconf  — devices announce themselves as <name>.local
2. ARP subnet scan  — ping-sweep a CIDR subnet and probe each host
3. BLE beacon scan  — ESP32 BLE advertising packets
4. Manual CSV file  — import from devices.yaml or a CSV

All discovered devices are automatically registered with the orchestrator.
"""

import asyncio
import logging
import socket
import struct
from datetime import datetime, timezone
from ipaddress import IPv4Network
from typing import Any, Dict, List, Optional

from orchestrator.agent import AgentBase
from orchestrator.device import ESP32Device, DeviceCapability

logger = logging.getLogger(__name__)

# Well-known mDNS service type for our firmware
MDNS_SERVICE = "_multiagent._tcp.local."
# Port our firmware's HTTP server listens on
FIRMWARE_PORT = 80
# Timeout for HTTP probe (seconds)
PROBE_TIMEOUT = 2


class DiscoveryAgent(AgentBase):
    """
    Agent that auto-discovers ESP32 devices on the local network and
    automatically registers them with the orchestrator.

    Supports four discovery strategies:
      - mdns   : Zeroconf / mDNS service browse
      - arp    : ARP + TCP probe of every host in a subnet
      - ble    : BLE advertisement scan (requires bleak)
      - file   : Load from devices.yaml / CSV
    """

    TASKS = {
        "discover",          # run one or all discovery methods
        "mdns_scan",
        "arp_scan",
        "ble_scan",
        "file_import",
        "list_discovered",
        "clear_discovered",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("discovery_agent", config)
        self._discovered: Dict[str, Dict[str, Any]] = {}  # ip → device info

    # ------------------------------------------------------------------
    # AgentBase interface
    # ------------------------------------------------------------------

    async def _execute(
        self,
        task: str,
        params: Dict[str, Any],
        device: Optional[ESP32Device],
    ) -> Any:
        if task == "discover":
            return await self._discover_all(params)
        if task == "mdns_scan":
            return await self._mdns_scan(params)
        if task == "arp_scan":
            return await self._arp_scan(params)
        if task == "ble_scan":
            return await self._ble_scan(params)
        if task == "file_import":
            return await self._file_import(params)
        if task == "list_discovered":
            return {"devices": list(self._discovered.values())}
        if task == "clear_discovered":
            self._discovered.clear()
            return {"ok": True}
        raise ValueError(f"Unknown task: {task}")

    # ------------------------------------------------------------------
    # Discover all
    # ------------------------------------------------------------------

    async def _discover_all(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run all discovery methods concurrently."""
        results = await asyncio.gather(
            self._mdns_scan(params),
            self._arp_scan(params),
            return_exceptions=True,
        )
        found = []
        for r in results:
            if isinstance(r, dict):
                found.extend(r.get("devices", []))
        # Deduplicate by IP
        seen = {}
        for d in found:
            seen[d.get("ip_address", d.get("device_id"))] = d
        registered = await self._register_all(list(seen.values()))
        return {
            "discovered": len(seen),
            "registered": registered,
            "devices": list(seen.values()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # mDNS discovery
    # ------------------------------------------------------------------

    async def _mdns_scan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Browse mDNS for devices announcing _multiagent._tcp.local.
        Falls back gracefully if python-zeroconf is not installed.
        """
        timeout = params.get("timeout_sec", 5)
        found = []
        try:
            from zeroconf import ServiceBrowser, Zeroconf  # type: ignore
            from zeroconf.asyncio import AsyncZeroconf  # type: ignore

            az = AsyncZeroconf()
            services_found = []

            class _Listener:
                def add_service(self, zc, stype, name):
                    info = zc.get_service_info(stype, name)
                    if info:
                        addr = socket.inet_ntoa(info.addresses[0]) if info.addresses else None
                        services_found.append({
                            "device_id": name.replace(f".{stype}", ""),
                            "name": info.server.rstrip("."),
                            "ip_address": addr,
                            "port": info.port,
                            "capabilities": ["wifi"],
                        })

                def remove_service(self, zc, stype, name):
                    pass

                def update_service(self, zc, stype, name):
                    pass

            browser = ServiceBrowser(az.zeroconf, MDNS_SERVICE, _Listener())
            await asyncio.sleep(timeout)
            await az.async_close()
            found = services_found
        except ImportError:
            logger.info("zeroconf not installed — mDNS scan unavailable. "
                        "Install with: pip install zeroconf")
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("mDNS scan error: %s", exc)

        return {"method": "mdns", "devices": found}

    # ------------------------------------------------------------------
    # ARP / TCP probe scan
    # ------------------------------------------------------------------

    async def _arp_scan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Probe every host in a CIDR subnet for our firmware's HTTP API.
        Concurrent probes bounded by a semaphore.
        """
        subnet = params.get("subnet", self._guess_local_subnet())
        concurrency = params.get("concurrency", 50)
        found = []

        sem = asyncio.Semaphore(concurrency)

        async def _probe(ip: str):
            async with sem:
                info = await self._probe_host(ip)
                if info:
                    found.append(info)

        try:
            hosts = [str(h) for h in IPv4Network(subnet, strict=False).hosts()]
        except ValueError:
            return {"method": "arp", "devices": [], "error": f"Invalid subnet: {subnet}"}

        logger.info("ARP scan: probing %d hosts in %s", len(hosts), subnet)
        await asyncio.gather(*[_probe(ip) for ip in hosts])
        logger.info("ARP scan complete: found %d devices", len(found))
        return {"method": "arp", "devices": found}

    async def _probe_host(self, ip: str) -> Optional[Dict[str, Any]]:
        """
        Try to connect to the firmware HTTP API on the given IP.
        Returns device info dict on success, None otherwise.
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, FIRMWARE_PORT), timeout=PROBE_TIMEOUT
            )
            # Send a minimal HTTP GET
            writer.write(
                b"GET /api/command HTTP/1.0\r\nHost: esp32\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 30\r\n\r\n"
                b'{"command":"get_status","payload":{}}'
            )
            await writer.drain()
            response = await asyncio.wait_for(reader.read(512), timeout=PROBE_TIMEOUT)
            writer.close()

            if b"firmware_version" in response or b"ESP32" in response:
                # Parse version from response if possible
                import json
                try:
                    body = response.split(b"\r\n\r\n", 1)[-1]
                    data = json.loads(body)
                    version = data.get("firmware_version", "unknown")
                    name = data.get("device_name", f"ESP32-{ip.split('.')[-1]}")
                except Exception:  # pylint: disable=broad-except
                    version = "unknown"
                    name = f"ESP32-{ip.split('.')[-1]}"
                return {
                    "device_id": f"auto-{ip.replace('.', '-')}",
                    "name": name,
                    "ip_address": ip,
                    "firmware_version": version,
                    "capabilities": ["wifi"],
                    "discovery_method": "arp",
                }
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            pass
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug("Probe error on %s: %s", ip, exc)
        return None

    # ------------------------------------------------------------------
    # BLE scan
    # ------------------------------------------------------------------

    async def _ble_scan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Scan for ESP32 devices advertising over BLE."""
        from comms.ble import BLEManager
        duration = params.get("duration_sec", 5)
        mgr = BLEManager()
        peers = await mgr.scan(duration=duration)
        found = []
        for p in peers:
            if "ESP32" in p.name or "MultiAgent" in p.name:
                found.append({
                    "device_id": f"ble-{p.address.replace(':', '-')}",
                    "name": p.name,
                    "ble_address": p.address,
                    "rssi": p.rssi,
                    "capabilities": ["ble"],
                    "discovery_method": "ble",
                })
        return {"method": "ble", "devices": found}

    # ------------------------------------------------------------------
    # File / config import
    # ------------------------------------------------------------------

    async def _file_import(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Import device list from devices.yaml or a CSV file."""
        import csv
        from pathlib import Path

        path = params.get("path", "config/devices.yaml")
        p = Path(path)
        found = []

        if p.suffix in (".yaml", ".yml"):
            try:
                import yaml  # type: ignore
                with open(p, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                for d in data.get("devices", []):
                    found.append({**d, "discovery_method": "file"})
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("YAML import error: %s", exc)

        elif p.suffix == ".csv":
            try:
                with open(p, newline="", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        found.append({**row, "discovery_method": "csv"})
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("CSV import error: %s", exc)

        registered = await self._register_all(found)
        return {"method": "file", "path": str(p), "devices": found, "registered": registered}

    # ------------------------------------------------------------------
    # Auto-register helpers
    # ------------------------------------------------------------------

    async def _register_all(self, devices: List[Dict[str, Any]]) -> int:
        """Register all discovered devices with the orchestrator."""
        if not self.orchestrator:
            return 0
        count = 0
        for d in devices:
            device_id = d.get("device_id") or f"auto-{d.get('ip_address', 'unknown')}"
            if self.orchestrator.get_device(device_id):
                continue  # already registered
            caps_raw: List[str] = d.get("capabilities", ["wifi"])
            caps = []
            for c in caps_raw:
                try:
                    caps.append(DeviceCapability(c))
                except ValueError:
                    pass
            device = ESP32Device(
                device_id=device_id,
                name=d.get("name", device_id),
                ip_address=d.get("ip_address"),
                mac_address=d.get("mac_address"),
                capabilities=caps or None,
                config={"firmware_version": d.get("firmware_version", "unknown")},
            )
            self.orchestrator.register_device(device)
            self._discovered[d.get("ip_address", device_id)] = d
            count += 1
        return count

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _guess_local_subnet() -> str:
        """Guess the local /24 subnet from the host's primary IP."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            parts = ip.rsplit(".", 1)
            return f"{parts[0]}.0/24"
        except Exception:  # pylint: disable=broad-except
            return "192.168.1.0/24"
