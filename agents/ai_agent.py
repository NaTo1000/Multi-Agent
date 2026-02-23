"""
AI Agent — intelligent automation layer.

Provides:
- Autonomous frequency optimisation using gradient-ascent RSSI feedback
- Predictive interference detection using rolling statistics
- Adaptive modulation selection
- Anomaly detection on telemetry streams
- Natural-language research + recommendation generation
"""

import logging
import math
import statistics
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from orchestrator.agent import AgentBase
from orchestrator.device import ESP32Device

logger = logging.getLogger(__name__)

WINDOW_SIZE = 50  # samples for rolling statistics


class AIAgent(AgentBase):
    """
    AI/ML automation agent.

    Uses lightweight on-device algorithms (no heavy ML framework required)
    plus optional cloud offload for heavier inference tasks.
    """

    TASKS = {
        "auto_optimise",
        "detect_interference",
        "predict_congestion",
        "anomaly_detect",
        "recommend_config",
        "research",
        "auto_tune_fleet",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("ai_agent", config)
        # Per-device rolling RSSI window
        self._rssi_windows: Dict[str, Deque[float]] = {}
        # Per-device recommendation cache
        self._recommendations: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # AgentBase interface
    # ------------------------------------------------------------------

    async def _execute(
        self,
        task: str,
        params: Dict[str, Any],
        device: Optional[ESP32Device],
    ) -> Any:
        if task == "auto_optimise":
            return await self._auto_optimise(params, device)
        if task == "detect_interference":
            return await self._detect_interference(params, device)
        if task == "predict_congestion":
            return await self._predict_congestion(params, device)
        if task == "anomaly_detect":
            return self._anomaly_detect(params, device)
        if task == "recommend_config":
            return await self._recommend_config(params, device)
        if task == "research":
            return await self._research(params)
        if task == "auto_tune_fleet":
            return await self._auto_tune_fleet(params)
        raise ValueError(f"Unknown task: {task}")

    # ------------------------------------------------------------------
    # Task implementations
    # ------------------------------------------------------------------

    async def _auto_optimise(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Continuously optimise a device's frequency and modulation by
        iterating toward higher RSSI using coordinate ascent.
        """
        if not device or not self.orchestrator:
            return {"optimised": False, "reason": "no_device_or_orchestrator"}

        freq_agents = self.orchestrator.get_agents_by_type("frequency_agent")
        mod_agents = self.orchestrator.get_agents_by_type("modulation_agent")

        results = []

        # Step 1: fine-tune frequency
        if freq_agents:
            task_id = await self.orchestrator.dispatch_task(
                freq_agents[0].agent_id,
                "fine_tune",
                {"step_hz": 500_000, "iterations": 5},
                device.device_id,
            )
            results.append({"step": "frequency_fine_tune", "task_id": task_id})

        # Step 2: adaptive modulation
        if mod_agents:
            rssi = await device.get_rssi() or -80
            task_id = await self.orchestrator.dispatch_task(
                mod_agents[0].agent_id,
                "adaptive_select",
                {"snr_db": rssi + 100},
                device.device_id,
            )
            results.append({"step": "adaptive_modulation", "task_id": task_id})

        return {"optimised": True, "device_id": device.device_id, "steps": results}

    async def _detect_interference(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Detect RF interference by analysing RSSI variance over a rolling window.
        High variance → likely interference / congested channel.
        """
        if not device:
            return {"interference": False, "reason": "no_device"}

        window = self._rssi_windows.setdefault(
            device.device_id, deque(maxlen=WINDOW_SIZE)
        )
        rssi = await device.get_rssi()
        if rssi is not None:
            window.append(rssi)

        if len(window) < 5:
            return {"interference": False, "reason": "insufficient_data", "samples": len(window)}

        variance = statistics.variance(window)
        mean = statistics.mean(window)
        threshold = params.get("variance_threshold", 25.0)
        interference_detected = variance > threshold

        if interference_detected:
            logger.warning("Interference detected on device %s (variance=%.1f)",
                           device.device_id, variance)

        return {
            "device_id": device.device_id,
            "interference": interference_detected,
            "rssi_mean": round(mean, 2),
            "rssi_variance": round(variance, 2),
            "threshold": threshold,
            "samples": len(window),
        }

    async def _predict_congestion(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Predict future channel congestion using linear extrapolation of RSSI trend.
        Falling RSSI trend → increasing congestion.
        """
        if not device:
            return {"congestion_risk": "unknown"}

        window = self._rssi_windows.get(device.device_id, deque())
        if len(window) < 10:
            return {"congestion_risk": "insufficient_data"}

        samples = list(window)
        n = len(samples)
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(samples)
        slope = sum((i - x_mean) * (s - y_mean) for i, s in enumerate(samples)) / \
                sum((i - x_mean) ** 2 for i in range(n))

        horizon = params.get("horizon_steps", 10)
        predicted = samples[-1] + slope * horizon

        risk_level = "low"
        if slope < -0.5:
            risk_level = "medium"
        if slope < -1.0:
            risk_level = "high"

        return {
            "device_id": device.device_id,
            "current_rssi": samples[-1],
            "rssi_slope_per_step": round(slope, 3),
            "predicted_rssi_in_%d_steps" % horizon: round(predicted, 1),
            "congestion_risk": risk_level,
        }

    def _anomaly_detect(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Flag anomalies in device telemetry using z-score method.
        """
        if not device:
            return {"anomalies": []}

        telemetry = device.telemetry
        window = self._rssi_windows.get(device.device_id, deque())
        anomalies = []

        if len(window) >= 10:
            mean = statistics.mean(window)
            stdev = statistics.stdev(window) or 1
            current = telemetry.get("rssi")
            if current is not None:
                z = abs((current - mean) / stdev)
                if z > params.get("z_threshold", 3.0):
                    anomalies.append({
                        "field": "rssi",
                        "value": current,
                        "z_score": round(z, 2),
                    })

        return {
            "device_id": device.device_id if device else None,
            "anomalies": anomalies,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _recommend_config(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Generate a configuration recommendation based on current device state.
        """
        if not device:
            return {"recommendations": []}

        recs = []
        rssi = await device.get_rssi() or -100

        if rssi < -80:
            recs.append({
                "priority": "high",
                "action": "switch_modulation",
                "params": {"scheme": "LoRa"},
                "reason": "Low RSSI detected — LoRa offers better sensitivity",
            })
        elif rssi > -50:
            recs.append({
                "priority": "low",
                "action": "switch_modulation",
                "params": {"scheme": "QAM16"},
                "reason": "Strong signal — higher throughput modulation available",
            })

        window = self._rssi_windows.get(device.device_id, deque())
        if len(window) >= 10:
            variance = statistics.variance(window)
            if variance > 25:
                recs.append({
                    "priority": "medium",
                    "action": "hop_channel",
                    "params": {},
                    "reason": "High RSSI variance suggests interference — channel hop recommended",
                })

        self._recommendations[device.device_id] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recommendations": recs,
        }
        return self._recommendations[device.device_id]

    async def _research(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query a configured LLM / cloud AI endpoint for research-grade
        recommendations on frequency, modulation, or firmware strategy.
        Falls back to built-in heuristics when no cloud endpoint is set.
        """
        query = params.get("query", "")
        endpoint = self.config.get("ai_research_endpoint")

        if endpoint:
            try:
                import json
                import urllib.request

                body = json.dumps({"query": query, "context": params.get("context", {})}).encode()
                req = urllib.request.Request(
                    endpoint, data=body, headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read())
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("AI research endpoint failed: %s — using heuristics", exc)

        # Built-in heuristic response
        return {
            "query": query,
            "source": "builtin_heuristics",
            "response": (
                "For ESP32 frequency optimisation: prefer 5 GHz WiFi for throughput, "
                "915 MHz LoRa for long-range low-power, and BLE 5 for short-range "
                "high-speed. Enable GPS for location-aware adaptive power control."
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _auto_tune_fleet(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run auto-optimise across all online devices simultaneously.
        """
        if not self.orchestrator:
            return {"tuned": 0}
        devices = self.orchestrator.get_online_devices()
        import asyncio
        results = await asyncio.gather(
            *[self._auto_optimise(params, d) for d in devices],
            return_exceptions=True,
        )
        successes = sum(1 for r in results if isinstance(r, dict) and r.get("optimised"))
        return {
            "tuned": successes,
            "total": len(devices),
            "results": [r if isinstance(r, dict) else str(r) for r in results],
        }
