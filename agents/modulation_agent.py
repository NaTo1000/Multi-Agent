"""
Modulation Agent — configures and adaptively controls the modulation
scheme (AM/FM/FSK/GFSK/LoRa/QAM) used by each ESP32 module.
"""

import logging
from typing import Any, Dict, List, Optional

from orchestrator.agent import AgentBase
from orchestrator.device import ESP32Device

logger = logging.getLogger(__name__)

# Supported modulation schemes and their typical parameters
MODULATION_SCHEMES: Dict[str, Dict[str, Any]] = {
    "AM": {"bandwidth_hz": 10000, "carrier_required": True},
    "FM": {"bandwidth_hz": 200000, "deviation_hz": 75000},
    "FSK": {"bandwidth_hz": 250000, "deviation_hz": 25000},
    "GFSK": {"bandwidth_hz": 250000, "bt": 0.5},       # BLE default
    "OOK": {"bandwidth_hz": 100000},
    "QPSK": {"bandwidth_hz": 500000, "bits_per_symbol": 2},
    "QAM16": {"bandwidth_hz": 1000000, "bits_per_symbol": 4},
    "LoRa": {"spreading_factor": 7, "coding_rate": "4/5", "bandwidth_hz": 125000},
}


class ModulationAgent(AgentBase):
    """
    Agent that manages radio modulation across the ESP32 fleet.

    Supports:
    - Setting / getting modulation scheme per device
    - Adaptive modulation based on SNR / link quality
    - Spread-spectrum and LoRa configuration
    - Fleet-wide modulation broadcast
    """

    TASKS = {
        "set_modulation",
        "get_modulation",
        "adaptive_select",
        "list_schemes",
        "configure_lora",
        "configure_ble",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("modulation_agent", config)
        self._current_scheme: Dict[str, str] = {}  # device_id → scheme

    # ------------------------------------------------------------------
    # AgentBase interface
    # ------------------------------------------------------------------

    async def _execute(
        self,
        task: str,
        params: Dict[str, Any],
        device: Optional[ESP32Device],
    ) -> Any:
        if task == "set_modulation":
            return await self._set_modulation(params, device)
        if task == "get_modulation":
            return self._get_modulation(device)
        if task == "adaptive_select":
            return await self._adaptive_select(params, device)
        if task == "list_schemes":
            return {"schemes": list(MODULATION_SCHEMES.keys())}
        if task == "configure_lora":
            return await self._configure_lora(params, device)
        if task == "configure_ble":
            return await self._configure_ble(params, device)
        raise ValueError(f"Unknown task: {task}")

    # ------------------------------------------------------------------
    # Task implementations
    # ------------------------------------------------------------------

    async def _set_modulation(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        scheme = params.get("scheme", "GFSK").upper()
        if scheme not in MODULATION_SCHEMES:
            raise ValueError(f"Unsupported scheme '{scheme}'.  Options: {list(MODULATION_SCHEMES)}")
        scheme_params = {**MODULATION_SCHEMES[scheme], **params.get("overrides", {})}
        if device:
            resp = await device.send_command("set_modulation", {"scheme": scheme, **scheme_params})
            ok = resp.get("status") == "ok"
            if ok:
                self._current_scheme[device.device_id] = scheme
            logger.info("Device %s modulation → %s (%s)", device.device_id, scheme,
                        "ok" if ok else "failed")
            return {"ok": ok, "scheme": scheme, "params": scheme_params}
        return {"ok": False, "reason": "no_device"}

    def _get_modulation(self, device: Optional[ESP32Device]) -> Dict[str, Any]:
        if not device:
            return {"scheme": None}
        return {"scheme": self._current_scheme.get(device.device_id, "unknown")}

    async def _adaptive_select(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Choose the best modulation scheme based on current SNR.
        Simple heuristic: high SNR → denser modulation (QAM16),
        low SNR → robust scheme (GFSK or LoRa).
        """
        if not device:
            return {"selected": None, "reason": "no_device"}

        snr = params.get("snr_db")
        if snr is None:
            rssi = await device.get_rssi() or -100
            snr = rssi + 100  # rough approximation

        if snr >= 25:
            scheme = "QAM16"
        elif snr >= 15:
            scheme = "QPSK"
        elif snr >= 5:
            scheme = "GFSK"
        else:
            scheme = "LoRa"

        result = await self._set_modulation({"scheme": scheme}, device)
        result["snr_db"] = snr
        return result

    async def _configure_lora(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """Apply LoRa-specific parameters (SF, CR, BW, TX power)."""
        if not device:
            return {"ok": False, "reason": "no_device"}
        lora_cfg = {
            "spreading_factor": params.get("spreading_factor", 7),
            "coding_rate": params.get("coding_rate", "4/5"),
            "bandwidth_hz": params.get("bandwidth_hz", 125000),
            "tx_power_dbm": params.get("tx_power_dbm", 14),
        }
        resp = await device.send_command("configure_lora", lora_cfg)
        ok = resp.get("status") == "ok"
        if ok:
            self._current_scheme[device.device_id] = "LoRa"
        return {"ok": ok, "lora_config": lora_cfg}

    async def _configure_ble(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """Configure BLE 5 advertising and connection parameters."""
        if not device:
            return {"ok": False, "reason": "no_device"}
        ble_cfg = {
            "advertising_interval_ms": params.get("advertising_interval_ms", 100),
            "tx_power_dbm": params.get("tx_power_dbm", 0),
            "phy": params.get("phy", "LE_2M"),         # BLE 5 2 Mbps PHY
            "coded_phy": params.get("coded_phy", False),
        }
        resp = await device.send_command("configure_ble", ble_cfg)
        ok = resp.get("status") == "ok"
        if ok:
            self._current_scheme[device.device_id] = "GFSK"
        return {"ok": ok, "ble_config": ble_cfg}
