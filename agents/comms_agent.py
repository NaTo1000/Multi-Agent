"""
Communications Agent — manages WiFi scanning/connection, BLE advertising,
GPS/GNSS parsing, and cloud telemetry upload for the ESP32 fleet.
"""

import logging
from typing import Any, Dict, List, Optional

from orchestrator.agent import AgentBase
from orchestrator.device import ESP32Device, DeviceCapability

logger = logging.getLogger(__name__)


class CommsAgent(AgentBase):
    """
    Agent responsible for all communication layer operations:

    - WiFi network scanning & association
    - BLE device discovery & pairing
    - GPS/GNSS fix retrieval and parsing
    - Cloud telemetry push
    - Device connectivity diagnostics
    """

    TASKS = {
        "wifi_scan",
        "wifi_connect",
        "wifi_disconnect",
        "ble_scan",
        "ble_advertise",
        "get_gps",
        "cloud_push",
        "compute_offload",
        "diagnostics",
        "set_hostname",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("comms_agent", config)

    async def _execute(
        self,
        task: str,
        params: Dict[str, Any],
        device: Optional[ESP32Device],
    ) -> Any:
        if task == "wifi_scan":
            return await self._wifi_scan(device)
        if task == "wifi_connect":
            return await self._wifi_connect(params, device)
        if task == "wifi_disconnect":
            return await self._wifi_disconnect(device)
        if task == "ble_scan":
            return await self._ble_scan(params, device)
        if task == "ble_advertise":
            return await self._ble_advertise(params, device)
        if task == "get_gps":
            return await self._get_gps(device)
        if task == "cloud_push":
            return await self._cloud_push(params, device)
        if task == "compute_offload":
            return await self._compute_offload(params, device)
        if task == "diagnostics":
            return await self._diagnostics(device)
        if task == "set_hostname":
            return await self._set_hostname(params, device)
        raise ValueError(f"Unknown task: {task}")

    # ------------------------------------------------------------------
    # WiFi
    # ------------------------------------------------------------------

    async def _wifi_scan(self, device: Optional[ESP32Device]) -> Dict[str, Any]:
        if not device:
            return {"networks": [], "reason": "no_device"}
        if not device.has_capability(DeviceCapability.WIFI):
            return {"networks": [], "reason": "wifi_not_supported"}
        resp = await device.send_command("wifi_scan")
        networks = resp.get("networks", [])
        logger.info("WiFi scan on %s found %d networks", device.device_id, len(networks))
        return {"device_id": device.device_id, "networks": networks}

    async def _wifi_connect(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        if not device:
            return {"connected": False, "reason": "no_device"}
        ssid = params.get("ssid")
        password = params.get("password", "")
        if not ssid:
            return {"connected": False, "reason": "ssid_required"}
        resp = await device.send_command("wifi_connect", {"ssid": ssid, "password": password})
        ok = resp.get("status") == "ok"
        if ok:
            device.ip_address = resp.get("ip_address", device.ip_address)
        logger.info("WiFi connect %s → %s: %s", device.device_id, ssid, "ok" if ok else "failed")
        return {"connected": ok, "ssid": ssid, "ip_address": device.ip_address}

    async def _wifi_disconnect(self, device: Optional[ESP32Device]) -> Dict[str, Any]:
        if not device:
            return {"ok": False}
        resp = await device.send_command("wifi_disconnect")
        return {"ok": resp.get("status") == "ok", "device_id": device.device_id}

    # ------------------------------------------------------------------
    # BLE
    # ------------------------------------------------------------------

    async def _ble_scan(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        if not device:
            return {"peers": [], "reason": "no_device"}
        if not device.has_capability(DeviceCapability.BLE):
            return {"peers": [], "reason": "ble_not_supported"}
        duration = params.get("duration_sec", 5)
        resp = await device.send_command("ble_scan", {"duration_sec": duration})
        peers: List[Dict] = resp.get("peers", [])
        logger.info("BLE scan on %s found %d peers", device.device_id, len(peers))
        return {"device_id": device.device_id, "peers": peers}

    async def _ble_advertise(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        if not device:
            return {"ok": False, "reason": "no_device"}
        adv_cfg = {
            "name": params.get("name", device.name),
            "service_uuid": params.get("service_uuid", ""),
            "interval_ms": params.get("interval_ms", 100),
        }
        resp = await device.send_command("ble_advertise", adv_cfg)
        return {"ok": resp.get("status") == "ok", "config": adv_cfg}

    # ------------------------------------------------------------------
    # GPS / GNSS
    # ------------------------------------------------------------------

    async def _get_gps(self, device: Optional[ESP32Device]) -> Dict[str, Any]:
        if not device:
            return {"fix": False, "reason": "no_device"}
        if not device.has_capability(DeviceCapability.GPS):
            return {"fix": False, "reason": "gps_not_supported"}
        resp = await device.send_command("get_gps")
        fix = resp.get("fix", False)
        if fix:
            device.update_telemetry({
                "latitude": resp.get("latitude"),
                "longitude": resp.get("longitude"),
                "altitude_m": resp.get("altitude_m"),
                "satellites": resp.get("satellites"),
            })
        return {
            "device_id": device.device_id,
            "fix": fix,
            "latitude": resp.get("latitude"),
            "longitude": resp.get("longitude"),
            "altitude_m": resp.get("altitude_m"),
            "satellites": resp.get("satellites"),
            "hdop": resp.get("hdop"),
            "timestamp": resp.get("timestamp"),
        }

    # ------------------------------------------------------------------
    # Cloud telemetry
    # ------------------------------------------------------------------

    async def _cloud_push(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Push device telemetry to the configured webhook endpoint.
        Supports AWS IoT, GCP Pub/Sub, Azure IoT Hub, generic HTTP, and
        self-hosted VPS/local webhook listeners (``connector: vps|local``).
        """
        from cloud.connector import CloudConnector

        raw_connector = params.get("connector", self.config.get("cloud_connector", "http"))
        if isinstance(raw_connector, dict):
            # Nested style: cloud_connector: {backend: aws, endpoint: "..."}
            connector_cfg = {**self.config, **raw_connector}
            connector_type = str(raw_connector.get("backend", "http"))
            endpoint = params.get("endpoint", raw_connector.get("endpoint", ""))
        else:
            connector_cfg = self.config
            connector_type = str(raw_connector)
            endpoint = params.get("endpoint", self.config.get("cloud_endpoint", ""))
        payload = device.to_dict() if device else params.get("payload", {})

        connector = CloudConnector.create(connector_type, endpoint, connector_cfg)
        ok = await connector.push(payload)
        logger.info("Cloud push (%s) for %s: %s",
                    connector_type,
                    device.device_id if device else "n/a",
                    "ok" if ok else "failed")
        return {"ok": ok, "connector": connector_type}

    # ------------------------------------------------------------------
    # Compute offload
    # ------------------------------------------------------------------

    async def _compute_offload(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Offload a heavy compute job to the configured backend.
        Backends: local VPS (default), AWS Lambda, GCP Cloud Functions.
        Per-request ``backend`` / ``endpoint`` / ``function`` override the
        configured defaults.
        """
        from cloud.compute import ComputeBackend, compute_config_from_dict

        compute_cfg = compute_config_from_dict(self.config)
        for key in ("endpoint", "function", "api_key", "aws_region"):
            if key in params:
                compute_cfg[key] = params[key]
        backend_type = str(params.get("backend", compute_cfg.get("backend", "local")))

        job = params.get("job", "generic")
        payload = params.get("payload")
        if payload is None:
            payload = device.to_dict() if device else {}

        backend = ComputeBackend.create(backend_type, compute_cfg)
        result = await backend.run(job, payload)
        logger.info("Compute offload (%s) job '%s': %s",
                    backend_type, job, "ok" if result.get("ok") else "failed")
        return result

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    async def _diagnostics(self, device: Optional[ESP32Device]) -> Dict[str, Any]:
        if not device:
            return {"ok": False, "reason": "no_device"}
        resp = await device.send_command("diagnostics")
        return {
            "device_id": device.device_id,
            "uptime_sec": resp.get("uptime_sec"),
            "free_heap_bytes": resp.get("free_heap_bytes"),
            "cpu_freq_mhz": resp.get("cpu_freq_mhz"),
            "wifi_rssi": resp.get("wifi_rssi"),
            "ble_active": resp.get("ble_active"),
            "gps_fix": resp.get("gps_fix"),
        }

    async def _set_hostname(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        if not device:
            return {"ok": False}
        hostname = params.get("hostname", device.name)
        resp = await device.send_command("set_hostname", {"hostname": hostname})
        return {"ok": resp.get("status") == "ok", "hostname": hostname}
