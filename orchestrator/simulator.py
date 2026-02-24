"""
ESP32 Device Simulator — virtual ESP32 for no-hardware development.

Creates a realistic software-emulated ESP32 that:
- Responds to all HTTP commands (same API as real firmware)
- Simulates RSSI with noise and interference models
- Simulates GPS movement along a configurable path
- Emulates OTA update acceptance
- Generates realistic telemetry data
- Can simulate hardware faults and edge-cases
"""

import asyncio
import json
import logging
import math
import random
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import threading

from orchestrator.device import ESP32Device, DeviceCapability, DeviceStatus

logger = logging.getLogger(__name__)


class SimulatedESP32:
    """
    Full software simulation of an ESP32 running our multi-agent firmware.

    Spawns a real HTTP server on localhost so the orchestrator can connect
    to it exactly like a physical device.
    """

    def __init__(
        self,
        device_id: str,
        name: str,
        port: int = 9100,
        scenario: str = "normal",  # normal | noisy | degraded | moving
        gps_path: Optional[List[Tuple[float, float]]] = None,
    ):
        self.device_id = device_id
        self.name = name
        self.port = port
        self.scenario = scenario
        self._state: Dict[str, Any] = {
            "firmware_version": "sim-1.0.0",
            "frequency_hz": 2412e6,
            "modulation": "GFSK",
            "tx_power_dbm": 14,
            "uptime_sec": 0,
            "free_heap_bytes": 250_000,
            "cpu_freq_mhz": 240,
            "wifi_rssi": -65,
            "ble_active": True,
            "gps_fix": False,
            "latitude": 0.0,
            "longitude": 0.0,
            "altitude_m": 0.0,
            "satellites": 0,
        }
        self._gps_path = gps_path or self._default_path()
        self._gps_idx = 0
        self._fault: Optional[str] = None
        self._server: Optional[HTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._tick = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> "SimulatedESP32":
        """Start the simulated device's HTTP server."""
        sim = self  # capture for closure

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    req = json.loads(body)
                except json.JSONDecodeError:
                    self._respond(400, {"error": "invalid_json"})
                    return
                response = sim.handle_command(req.get("command", ""), req.get("payload", {}))
                self._respond(200, response)

            def do_GET(self):
                if self.path == "/health":
                    self._respond(200, {"status": "ok", "name": sim.name})
                else:
                    self._respond(404, {"error": "not_found"})

            def _respond(self, code, data):
                body = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt, *args):
                pass  # suppress noisy access log

        self._server = HTTPServer(("127.0.0.1", self.port), _Handler)
        self._server_thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._server_thread.start()
        # Start telemetry update ticker
        self._ticker_thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._ticker_thread.start()
        logger.info("SimulatedESP32 '%s' started on port %d (scenario=%s)",
                    self.name, self.port, self.scenario)
        return self

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None

    def to_esp32_device(self) -> ESP32Device:
        """Return an ESP32Device pointing at this simulator."""
        device = ESP32Device(
            device_id=self.device_id,
            name=self.name,
            ip_address=f"127.0.0.1:{self.port}",
            capabilities=[DeviceCapability.WIFI, DeviceCapability.BLE, DeviceCapability.GPS],
            config={"firmware_version": self._state["firmware_version"]},
        )
        device.status = DeviceStatus.ONLINE
        device.ip_address = "127.0.0.1"
        # Patch send_command to use our local port
        original_send = device.send_command

        async def _patched_send(command: str, payload: Optional[Dict] = None):
            import json
            import urllib.request
            url = f"http://127.0.0.1:{self.port}/api/command"
            body = json.dumps({"command": command, "payload": payload or {}}).encode()
            req = urllib.request.Request(
                url, data=body, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read())

        device.send_command = _patched_send  # type: ignore[assignment]
        return device

    # ------------------------------------------------------------------
    # Command handler (mirrors real firmware API)
    # ------------------------------------------------------------------

    def handle_command(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process an incoming command and return the response."""
        self._tick += 1
        self._state["uptime_sec"] = self._tick

        if self._fault == "no_response":
            return {}  # Simulate dropped packet
        if self._fault == "error_response":
            return {"status": "error", "reason": "simulated_fault"}

        cmd_map = {
            "get_status": self._cmd_get_status,
            "set_frequency": self._cmd_set_frequency,
            "get_frequency": self._cmd_get_frequency,
            "get_rssi": self._cmd_get_rssi,
            "set_modulation": self._cmd_set_modulation,
            "configure_lora": self._cmd_configure_lora,
            "configure_ble": self._cmd_configure_ble,
            "get_gps": self._cmd_get_gps,
            "wifi_scan": self._cmd_wifi_scan,
            "wifi_connect": self._cmd_wifi_connect,
            "wifi_disconnect": self._cmd_wifi_disconnect,
            "ble_scan": self._cmd_ble_scan,
            "ble_advertise": self._cmd_ble_advertise,
            "diagnostics": self._cmd_diagnostics,
            "get_firmware_info": self._cmd_get_firmware_info,
            "get_telemetry": self._cmd_get_telemetry,
            "ota_update": self._cmd_ota_update,
            "ota_rollback": self._cmd_ota_rollback,
            "set_hostname": self._cmd_set_hostname,
        }
        handler = cmd_map.get(command)
        if handler:
            return handler(payload)
        return {"status": "unknown_command", "command": command}

    # ------------------------------------------------------------------
    # Individual command handlers
    # ------------------------------------------------------------------

    def _cmd_get_status(self, _) -> Dict[str, Any]:
        return {"status": "ok", **{k: self._state[k]
                for k in ("firmware_version", "uptime_sec")}}

    def _cmd_set_frequency(self, payload: Dict) -> Dict[str, Any]:
        self._state["frequency_hz"] = float(payload.get("frequency_hz", self._state["frequency_hz"]))
        return {"status": "ok", "frequency_hz": self._state["frequency_hz"]}

    def _cmd_get_frequency(self, _) -> Dict[str, Any]:
        return {"status": "ok", "frequency_hz": self._state["frequency_hz"]}

    def _cmd_get_rssi(self, _) -> Dict[str, Any]:
        rssi = self._simulate_rssi()
        self._state["wifi_rssi"] = rssi
        return {"status": "ok", "rssi": rssi}

    def _cmd_set_modulation(self, payload: Dict) -> Dict[str, Any]:
        self._state["modulation"] = payload.get("scheme", self._state["modulation"])
        return {"status": "ok", "modulation": self._state["modulation"]}

    def _cmd_configure_lora(self, payload: Dict) -> Dict[str, Any]:
        self._state["modulation"] = "LoRa"
        self._state.update({k: payload[k] for k in payload if k in
                             ("spreading_factor", "coding_rate", "bandwidth_hz", "tx_power_dbm")})
        return {"status": "ok"}

    def _cmd_configure_ble(self, payload: Dict) -> Dict[str, Any]:
        return {"status": "ok", "ble_config": payload}

    def _cmd_get_gps(self, _) -> Dict[str, Any]:
        lat, lon = self._advance_gps()
        return {
            "status": "ok",
            "fix": True,
            "latitude": lat,
            "longitude": lon,
            "altitude_m": self._state["altitude_m"] + random.gauss(0, 0.5),
            "satellites": random.randint(6, 12),
            "hdop": round(random.uniform(0.8, 1.5), 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _cmd_wifi_scan(self, _) -> Dict[str, Any]:
        return {
            "status": "ok",
            "networks": [
                {"ssid": "HomeNetwork", "rssi": -55, "channel": 6, "bssid": "AA:BB:CC:DD:EE:01"},
                {"ssid": "NeighborWifi", "rssi": -75, "channel": 11, "bssid": "AA:BB:CC:DD:EE:02"},
                {"ssid": "GuestNet", "rssi": -82, "channel": 1, "bssid": "AA:BB:CC:DD:EE:03"},
            ],
        }

    def _cmd_wifi_connect(self, payload: Dict) -> Dict[str, Any]:
        return {"status": "ok", "ssid": payload.get("ssid"), "ip_address": "192.168.1.200"}

    def _cmd_wifi_disconnect(self, _) -> Dict[str, Any]:
        return {"status": "ok"}

    def _cmd_ble_scan(self, _) -> Dict[str, Any]:
        return {
            "status": "ok",
            "peers": [
                {"address": "AA:BB:CC:11:22:33", "name": "Phone-1", "rssi": -62},
                {"address": "AA:BB:CC:44:55:66", "name": "ESP32-Node2", "rssi": -74},
            ],
        }

    def _cmd_ble_advertise(self, payload: Dict) -> Dict[str, Any]:
        return {"status": "ok"}

    def _cmd_diagnostics(self, _) -> Dict[str, Any]:
        return {
            "status": "ok",
            "uptime_sec": self._state["uptime_sec"],
            "free_heap_bytes": max(10_000, self._state["free_heap_bytes"] - self._tick * 10),
            "cpu_freq_mhz": self._state["cpu_freq_mhz"],
            "wifi_rssi": self._state["wifi_rssi"],
            "ble_active": self._state["ble_active"],
            "gps_fix": True,
        }

    def _cmd_get_firmware_info(self, _) -> Dict[str, Any]:
        return {
            "status": "ok",
            "version": self._state["firmware_version"],
            "build_date": "Feb 24 2026",
            "features": ["wifi", "ble", "gps"],
        }

    def _cmd_get_telemetry(self, _) -> Dict[str, Any]:
        lat, lon = self._advance_gps()
        return {
            "status": "ok",
            "rssi": self._simulate_rssi(),
            "frequency_hz": self._state["frequency_hz"],
            "latitude": lat,
            "longitude": lon,
            "uptime_sec": self._state["uptime_sec"],
            "free_heap_bytes": max(10_000, self._state["free_heap_bytes"] - self._tick * 5),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _cmd_ota_update(self, payload: Dict) -> Dict[str, Any]:
        logger.info("SimESP32 %s: OTA update from %s", self.name, payload.get("url"))
        self._state["firmware_version"] = "sim-2.0.0"
        return {"status": "ok", "new_version": self._state["firmware_version"]}

    def _cmd_ota_rollback(self, _) -> Dict[str, Any]:
        return {"status": "ok"}

    def _cmd_set_hostname(self, payload: Dict) -> Dict[str, Any]:
        self.name = payload.get("hostname", self.name)
        return {"status": "ok", "hostname": self.name}

    # ------------------------------------------------------------------
    # Simulation helpers
    # ------------------------------------------------------------------

    def _simulate_rssi(self) -> int:
        base = -65
        if self.scenario == "noisy":
            base = -75
            noise = random.gauss(0, 10)
        elif self.scenario == "degraded":
            base = -88
            noise = random.gauss(0, 5)
        else:
            noise = random.gauss(0, 3)
        # Add frequency-dependent component
        freq_mhz = self._state["frequency_hz"] / 1e6
        if 2400 <= freq_mhz <= 2500:
            # Simulate a busy ch6 (2437 MHz)
            if abs(freq_mhz - 2437) < 5:
                base = -50
        return int(base + noise)

    def _advance_gps(self) -> Tuple[float, float]:
        """Move along the GPS path."""
        lat, lon = self._gps_path[self._gps_idx % len(self._gps_path)]
        self._gps_idx += 1
        self._state["latitude"] = lat
        self._state["longitude"] = lon
        self._state["gps_fix"] = True
        return lat, lon

    @staticmethod
    def _default_path() -> List[Tuple[float, float]]:
        """Simple circular path around (37.7749, -122.4194) — San Francisco."""
        center_lat, center_lon = 37.7749, -122.4194
        radius_deg = 0.001
        steps = 36
        return [
            (
                center_lat + radius_deg * math.cos(2 * math.pi * i / steps),
                center_lon + radius_deg * math.sin(2 * math.pi * i / steps),
            )
            for i in range(steps)
        ]

    def _tick_loop(self) -> None:
        """Background thread that increments simulated time."""
        import time
        while self._server is not None:
            time.sleep(1)
            self._tick += 1
            self._state["uptime_sec"] = self._tick

    # ------------------------------------------------------------------
    # Fault injection
    # ------------------------------------------------------------------

    def inject_fault(self, fault: Optional[str]) -> None:
        """
        Simulate hardware faults.
        fault: None | "no_response" | "error_response"
        """
        self._fault = fault
        logger.info("SimESP32 %s: fault injected = %s", self.name, fault)

    def clear_fault(self) -> None:
        self._fault = None


class SimulatorFleet:
    """Manages a collection of simulated devices."""

    def __init__(self):
        self._sims: Dict[str, SimulatedESP32] = {}

    def add(
        self,
        device_id: str,
        name: str,
        port: int,
        scenario: str = "normal",
    ) -> SimulatedESP32:
        sim = SimulatedESP32(device_id, name, port, scenario)
        self._sims[device_id] = sim
        return sim

    def start_all(self) -> None:
        for sim in self._sims.values():
            sim.start()

    def stop_all(self) -> None:
        for sim in self._sims.values():
            sim.stop()

    def get(self, device_id: str) -> Optional[SimulatedESP32]:
        return self._sims.get(device_id)

    def get_all_devices(self) -> List[ESP32Device]:
        return [s.to_esp32_device() for s in self._sims.values()]

    def inject_fault(self, device_id: str, fault: Optional[str]) -> None:
        sim = self._sims.get(device_id)
        if sim:
            sim.inject_fault(fault)
