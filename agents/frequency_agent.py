"""
Frequency Agent — handles frequency scanning, locking, fine-tuning,
and real-time adaptive control for ESP32 radio modules.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from orchestrator.agent import AgentBase
from orchestrator.device import ESP32Device

logger = logging.getLogger(__name__)

# Supported ISM bands (Hz)
ISM_BANDS: Dict[str, Tuple[float, float]] = {
    "2.4GHz": (2.400e9, 2.4835e9),
    "5GHz": (5.150e9, 5.850e9),
    "868MHz": (868.0e6, 868.6e6),
    "915MHz": (902.0e6, 928.0e6),
    "433MHz": (433.05e6, 434.79e6),
}


class FrequencyAgent(AgentBase):
    """
    Agent responsible for all frequency-related operations:

    - Scanning available channels
    - Locking onto a target frequency
    - Fine-tuning with PID-like feedback
    - Adaptive channel hopping to avoid interference
    - Multi-device frequency synchronisation
    """

    TASKS = {
        "scan",
        "lock",
        "fine_tune",
        "set_frequency",
        "get_frequency",
        "hop_channel",
        "sync_fleet",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("frequency_agent", config)
        self._lock_history: Dict[str, List[float]] = {}   # device_id → history
        self._target_frequencies: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # AgentBase interface
    # ------------------------------------------------------------------

    async def _execute(
        self,
        task: str,
        params: Dict[str, Any],
        device: Optional[ESP32Device],
    ) -> Any:
        if task == "scan":
            return await self._scan(params, device)
        if task == "lock":
            return await self._lock(params, device)
        if task == "fine_tune":
            return await self._fine_tune(params, device)
        if task == "set_frequency":
            return await self._set_frequency(params, device)
        if task == "get_frequency":
            return await self._get_frequency(device)
        if task == "hop_channel":
            return await self._hop_channel(params, device)
        if task == "sync_fleet":
            return await self._sync_fleet(params)
        raise ValueError(f"Unknown task: {task}")

    # ------------------------------------------------------------------
    # Task implementations
    # ------------------------------------------------------------------

    async def _scan(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """Scan a frequency band and return channels with signal strength."""
        band_name = params.get("band", "2.4GHz")
        band = ISM_BANDS.get(band_name)
        if band is None:
            raise ValueError(f"Unknown band: {band_name}.  Choose from {list(ISM_BANDS)}")

        low, high = band
        step_hz = params.get("step_hz", 1e6)
        channels = []
        freq = low
        while freq <= high:
            rssi = None
            if device:
                rssi = await device.get_rssi()
            channels.append({"frequency_hz": freq, "rssi": rssi})
            freq += step_hz

        best = min(channels, key=lambda c: c["rssi"] if c["rssi"] is not None else 0)
        logger.info("Scan complete on %s — best channel: %.3f MHz",
                    band_name, best["frequency_hz"] / 1e6)
        return {"band": band_name, "channels": channels, "best_channel": best}

    async def _lock(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """Lock onto a target frequency."""
        target = float(params["target_hz"])
        tolerance = float(params.get("tolerance_hz", 1000))

        if device:
            await device.set_frequency(target)
            current_rssi = await device.get_rssi()
            self._target_frequencies[device.device_id] = target
            history = self._lock_history.setdefault(device.device_id, [])
            history.append(target)
            if len(history) > 100:
                history.pop(0)
            logger.info("Locked device %s to %.3f MHz (RSSI=%s)",
                        device.device_id, target / 1e6, current_rssi)
            return {
                "locked": True,
                "target_hz": target,
                "actual_hz": device.current_frequency,
                "tolerance_hz": tolerance,
                "rssi": current_rssi,
            }
        return {"locked": False, "reason": "no_device"}

    async def _fine_tune(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Fine-tune frequency using iterative RSSI-gradient ascent.
        Sweeps ±step_hz around the current frequency and homes in on peak RSSI.
        """
        if not device:
            return {"tuned": False, "reason": "no_device"}

        current = device.current_frequency
        step = float(params.get("step_hz", 10000))
        iterations = int(params.get("iterations", 5))

        best_freq = current
        best_rssi = await device.get_rssi() or -100

        for _ in range(iterations):
            for candidate in (current - step, current + step):
                await device.set_frequency(candidate)
                rssi = await device.get_rssi() or -100
                if rssi > best_rssi:
                    best_rssi = rssi
                    best_freq = candidate
            current = best_freq
            step /= 2  # Halve step each iteration (binary-search style)

        await device.set_frequency(best_freq)
        logger.info("Fine-tuned %s to %.3f MHz (RSSI=%d)",
                    device.device_id, best_freq / 1e6, best_rssi)
        return {"tuned": True, "frequency_hz": best_freq, "rssi": best_rssi}

    async def _set_frequency(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        if not device:
            return {"ok": False, "reason": "no_device"}
        freq = float(params["frequency_hz"])
        ok = await device.set_frequency(freq)
        return {"ok": ok, "frequency_hz": freq}

    async def _get_frequency(self, device: Optional[ESP32Device]) -> Dict[str, Any]:
        if not device:
            return {"frequency_hz": None}
        return {"frequency_hz": device.current_frequency}

    async def _hop_channel(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """Jump to the next available channel in the hopping sequence."""
        if not device:
            return {"hopped": False, "reason": "no_device"}
        sequence: List[float] = params.get("sequence", [])
        if not sequence:
            # Default 2.4 GHz WiFi channels (centre freqs in Hz)
            sequence = [2412e6, 2437e6, 2462e6]
        next_freq = sequence[0]
        history = self._lock_history.get(device.device_id, [])
        if history:
            last = history[-1]
            for i, f in enumerate(sequence):
                if abs(f - last) < 1e6:
                    next_freq = sequence[(i + 1) % len(sequence)]
                    break
        await device.set_frequency(next_freq)
        return {"hopped": True, "new_frequency_hz": next_freq}

    async def _sync_fleet(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronise all online devices to the same frequency."""
        target = float(params["target_hz"])
        results = []
        if self.orchestrator:
            import asyncio
            tasks = [
                d.set_frequency(target)
                for d in self.orchestrator.get_online_devices()
            ]
            statuses = await asyncio.gather(*tasks, return_exceptions=True)
            for device, status in zip(self.orchestrator.get_online_devices(), statuses):
                results.append({"device_id": device.device_id, "ok": status is True})
        return {"synced": results, "target_hz": target}
