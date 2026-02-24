"""
Spectrum Analyzer Agent — real-time FFT-based RF spectrum analysis.

Capabilities:
- Sweep a frequency band and collect RSSI samples
- Compute FFT-based power spectral density (PSD)
- Generate channel occupancy heatmaps
- Build rolling waterfall data for visualization
- Detect occupied channels vs. clear channels
- Identify primary interference sources
- Return spectrum data consumable by the web dashboard
"""

import cmath
import logging
import math
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from orchestrator.agent import AgentBase
from orchestrator.device import ESP32Device

logger = logging.getLogger(__name__)

# ISM bands with their channel plans
BAND_CHANNELS: Dict[str, List[Tuple[float, str]]] = {
    "2.4GHz": [
        (2412e6, "ch1"), (2417e6, "ch2"), (2422e6, "ch3"), (2427e6, "ch4"),
        (2432e6, "ch5"), (2437e6, "ch6"), (2442e6, "ch7"), (2447e6, "ch8"),
        (2452e6, "ch9"), (2457e6, "ch10"), (2462e6, "ch11"), (2467e6, "ch12"),
        (2472e6, "ch13"),
    ],
    "5GHz": [
        (5180e6, "ch36"), (5200e6, "ch40"), (5220e6, "ch44"), (5240e6, "ch48"),
        (5260e6, "ch52"), (5280e6, "ch56"), (5300e6, "ch60"), (5320e6, "ch64"),
        (5745e6, "ch149"), (5765e6, "ch153"), (5785e6, "ch157"), (5805e6, "ch161"),
    ],
    "915MHz": [
        (902e6 + i * 200e3, f"ch{i}") for i in range(64)
    ],
    "868MHz": [
        (868.1e6, "ch0"), (868.3e6, "ch1"), (868.5e6, "ch2"),
    ],
    "433MHz": [
        (433.175e6, "ch0"), (433.375e6, "ch1"), (433.575e6, "ch2"),
        (433.775e6, "ch3"), (433.975e6, "ch4"),
    ],
}

WATERFALL_DEPTH = 60   # rows kept in the rolling waterfall buffer


def _fft(signal: List[complex]) -> List[complex]:
    """
    Cooley-Tukey radix-2 FFT — pure Python, no numpy required.
    Input length must be a power of 2.
    """
    n = len(signal)
    if n <= 1:
        return signal
    if n & (n - 1):
        # Pad to next power-of-2
        target = 1
        while target < n:
            target <<= 1
        signal = signal + [0j] * (target - n)
        n = target

    even = _fft(signal[0::2])
    odd  = _fft(signal[1::2])
    k_range = n // 2
    result = [0j] * n
    for k in range(k_range):
        t = cmath.exp(-2j * cmath.pi * k / n) * odd[k]
        result[k]          = even[k] + t
        result[k + k_range] = even[k] - t
    return result


def _power_db(c: complex) -> float:
    mag = abs(c)
    return 20 * math.log10(mag + 1e-12)  # avoid log(0)


class SpectrumAnalyzerAgent(AgentBase):
    """
    FFT-based spectrum analyzer for the ESP32 fleet.

    In production the RSSI sweep data comes from real devices.
    When no device is attached the agent generates synthetic spectrum
    data for UI development and testing.
    """

    TASKS = {
        "sweep",             # one-shot sweep and return full spectrum
        "waterfall_frame",   # return one new row for the waterfall plot
        "channel_occupancy", # return per-channel busy/clear assessment
        "find_best_channels",# return top N channels with lowest occupancy
        "peak_interference", # locate the dominant interference source
        "continuous_scan",   # start a background continuous scan loop
        "stop_scan",         # stop the continuous scan loop
        "get_waterfall",     # return the full rolling waterfall buffer
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("spectrum_agent", config)
        # Rolling waterfall: device_id → deque of spectrum rows
        self._waterfall: Dict[str, deque] = {}
        # Per-channel occupancy counts: device_id → {channel: count_busy}
        self._occupancy: Dict[str, Dict[str, int]] = {}
        self._scan_counts: Dict[str, int] = {}
        self._continuous: Dict[str, bool] = {}

    # ------------------------------------------------------------------
    # AgentBase interface
    # ------------------------------------------------------------------

    async def _execute(
        self,
        task: str,
        params: Dict[str, Any],
        device: Optional[ESP32Device],
    ) -> Any:
        if task == "sweep":
            return await self._sweep(params, device)
        if task == "waterfall_frame":
            return await self._waterfall_frame(params, device)
        if task == "channel_occupancy":
            return await self._channel_occupancy(params, device)
        if task == "find_best_channels":
            return await self._find_best_channels(params, device)
        if task == "peak_interference":
            return await self._peak_interference(params, device)
        if task == "get_waterfall":
            return self._get_waterfall(device)
        if task == "continuous_scan":
            return self._start_continuous(params, device)
        if task == "stop_scan":
            return self._stop_continuous(device)
        raise ValueError(f"Unknown task: {task}")

    # ------------------------------------------------------------------
    # Sweep
    # ------------------------------------------------------------------

    async def _sweep(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Sweep a band, collect per-channel RSSI, run FFT,
        and return PSD + raw channel data.
        """
        band = params.get("band", "2.4GHz")
        channels = BAND_CHANNELS.get(band, BAND_CHANNELS["2.4GHz"])
        samples = []

        for freq, ch_name in channels:
            if device:
                ok = await device.set_frequency(freq)
                rssi = await device.get_rssi() if ok else None
            else:
                rssi = self._synthetic_rssi(freq)
            samples.append({
                "channel": ch_name,
                "frequency_hz": freq,
                "rssi_dbm": rssi if rssi is not None else -100,
            })

        psd = self._compute_psd([s["rssi_dbm"] for s in samples])

        device_id = device.device_id if device else "synthetic"
        wf = self._waterfall.setdefault(device_id, deque(maxlen=WATERFALL_DEPTH))
        wf.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "band": band,
            "psd": psd,
        })

        return {
            "band": band,
            "device_id": device_id,
            "channels": samples,
            "psd": psd,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Waterfall frame
    # ------------------------------------------------------------------

    async def _waterfall_frame(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """Return one new row of the waterfall."""
        result = await self._sweep(params, device)
        return {
            "type": "waterfall_frame",
            "device_id": result["device_id"],
            "timestamp": result["timestamp"],
            "band": result["band"],
            "psd": result["psd"],
        }

    # ------------------------------------------------------------------
    # Channel occupancy
    # ------------------------------------------------------------------

    async def _channel_occupancy(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """Classify each channel as busy/clear based on RSSI threshold."""
        threshold = params.get("busy_threshold_dbm", -75.0)
        sweep = await self._sweep(params, device)

        device_id = sweep["device_id"]
        self._occupancy.setdefault(device_id, {})
        self._scan_counts[device_id] = self._scan_counts.get(device_id, 0) + 1

        results = []
        for ch in sweep["channels"]:
            busy = ch["rssi_dbm"] > threshold
            name = ch["channel"]
            occ = self._occupancy[device_id]
            if busy:
                occ[name] = occ.get(name, 0) + 1
            total = self._scan_counts[device_id]
            results.append({
                **ch,
                "busy": busy,
                "busy_pct": round(100 * occ.get(name, 0) / total, 1),
            })

        return {
            "device_id": device_id,
            "band": sweep["band"],
            "channels": results,
            "busy_threshold_dbm": threshold,
            "scan_count": self._scan_counts[device_id],
        }

    # ------------------------------------------------------------------
    # Find best channels
    # ------------------------------------------------------------------

    async def _find_best_channels(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """Return the N cleanest channels (lowest RSSI = least interference)."""
        n = params.get("n", 3)
        occ = await self._channel_occupancy(params, device)
        sorted_ch = sorted(occ["channels"], key=lambda c: c["rssi_dbm"])
        return {
            "device_id": occ["device_id"],
            "band": occ["band"],
            "best_channels": sorted_ch[:n],
        }

    # ------------------------------------------------------------------
    # Peak interference detection
    # ------------------------------------------------------------------

    async def _peak_interference(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """Identify the channel carrying the strongest (dominant) interferer."""
        sweep = await self._sweep(params, device)
        if not sweep["channels"]:
            return {"peak": None}
        peak = max(sweep["channels"], key=lambda c: c["rssi_dbm"])
        return {
            "device_id": sweep["device_id"],
            "band": sweep["band"],
            "peak_channel": peak["channel"],
            "peak_frequency_hz": peak["frequency_hz"],
            "peak_rssi_dbm": peak["rssi_dbm"],
            "recommendation": (
                f"Avoid {peak['channel']} ({peak['frequency_hz']/1e6:.1f} MHz) "
                f"— dominant interference at {peak['rssi_dbm']} dBm"
            ),
        }

    # ------------------------------------------------------------------
    # Waterfall buffer access
    # ------------------------------------------------------------------

    def _get_waterfall(self, device: Optional[ESP32Device]) -> Dict[str, Any]:
        device_id = device.device_id if device else "synthetic"
        frames = list(self._waterfall.get(device_id, []))
        return {"device_id": device_id, "frames": frames, "depth": len(frames)}

    # ------------------------------------------------------------------
    # Continuous scan control
    # ------------------------------------------------------------------

    def _start_continuous(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        import asyncio

        device_id = device.device_id if device else "synthetic"
        interval = params.get("interval_sec", 2.0)
        self._continuous[device_id] = True

        async def _loop():
            while self._continuous.get(device_id, False):
                try:
                    await self._sweep(params, device)
                except Exception as exc:  # pylint: disable=broad-except
                    logger.warning("Continuous scan error: %s", exc)
                await asyncio.sleep(interval)

        asyncio.ensure_future(_loop())
        logger.info("Continuous spectrum scan started on %s", device_id)
        return {"started": True, "device_id": device_id, "interval_sec": interval}

    def _stop_continuous(self, device: Optional[ESP32Device]) -> Dict[str, Any]:
        device_id = device.device_id if device else "synthetic"
        self._continuous[device_id] = False
        return {"stopped": True, "device_id": device_id}

    # ------------------------------------------------------------------
    # DSP helpers
    # ------------------------------------------------------------------

    def _compute_psd(self, rssi_samples: List[float]) -> List[float]:
        """
        Treat RSSI values as a time-domain signal and compute FFT-based PSD.
        Returns magnitude spectrum in dB.
        """
        n = len(rssi_samples)
        if n == 0:
            return []
        # Convert to complex signal centred around mean
        mean = sum(rssi_samples) / n
        signal = [complex(r - mean, 0) for r in rssi_samples]
        spectrum = _fft(signal)
        # Return the first half (positive frequencies only)
        half = n // 2 or 1
        return [round(_power_db(spectrum[i]), 2) for i in range(half)]

    @staticmethod
    def _synthetic_rssi(frequency_hz: float) -> float:
        """
        Generate realistic-looking synthetic RSSI for testing.
        Adds channel-specific offsets and random-walk noise.
        """
        import random
        # Simulate a few busy channels
        busy_freqs = [2437e6, 2462e6, 5180e6, 915e6]
        base = -80.0
        for bf in busy_freqs:
            if abs(frequency_hz - bf) < 5e6:
                base = -55.0 - random.uniform(0, 10)
                break
        return round(base + random.gauss(0, 3), 1)
