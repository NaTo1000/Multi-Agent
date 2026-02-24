"""
Predictive Maintenance Agent — ML-based device health prediction.

Uses lightweight rolling-window algorithms (no heavy ML frameworks):
- Exponential smoothing trend analysis
- EWMA-based anomaly scoring
- Component wear index computation
- Failure probability estimation (logistic-style scoring)
- Auto-healing actions (reboot, channel-hop, OTA trigger)
- Maintenance schedule generation
"""

import logging
import math
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Deque, Dict, List, Optional, Tuple

from orchestrator.agent import AgentBase
from orchestrator.device import ESP32Device

logger = logging.getLogger(__name__)

# Weights for the composite health score (0–100, higher = healthier)
HEALTH_WEIGHTS = {
    "rssi":       0.25,   # signal quality
    "heap":       0.20,   # memory health
    "uptime":     0.15,   # stability (longer = healthier, but resets score)
    "error_rate": 0.25,   # task failure rate
    "temp":       0.15,   # CPU temperature proxy (estimated from freq)
}


def _ewma(values: List[float], alpha: float = 0.3) -> float:
    """Exponentially weighted moving average."""
    if not values:
        return 0.0
    s = values[0]
    for v in values[1:]:
        s = alpha * v + (1 - alpha) * s
    return s


def _trend_slope(values: List[float]) -> float:
    """Linear slope of a time series (regression coefficient)."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    denom = sum((i - x_mean) ** 2 for i in range(n)) or 1
    return sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values)) / denom


def _logistic(x: float) -> float:
    """Sigmoid-style probability from a raw score."""
    try:
        return 1 / (1 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


class DeviceHealthRecord:
    """Per-device rolling telemetry record."""

    WINDOW = 100

    def __init__(self, device_id: str):
        self.device_id = device_id
        self.rssi_history: Deque[float] = deque(maxlen=self.WINDOW)
        self.heap_history: Deque[float] = deque(maxlen=self.WINDOW)
        self.uptime_history: Deque[float] = deque(maxlen=self.WINDOW)
        self.error_history: Deque[float] = deque(maxlen=self.WINDOW)
        self.health_history: Deque[float] = deque(maxlen=self.WINDOW)
        self.last_updated: Optional[str] = None
        self.reboot_count: int = 0
        self.ota_count: int = 0
        self.fault_events: List[Dict[str, Any]] = []

    def record(self, telemetry: Dict[str, Any], error_rate: float = 0.0) -> None:
        if "rssi" in telemetry:
            self.rssi_history.append(float(telemetry["rssi"]))
        if "free_heap_bytes" in telemetry:
            self.heap_history.append(float(telemetry["free_heap_bytes"]))
        if "uptime_sec" in telemetry:
            self.uptime_history.append(float(telemetry["uptime_sec"]))
        self.error_history.append(error_rate)
        self.last_updated = datetime.now(timezone.utc).isoformat()


class PredictiveMaintenanceAgent(AgentBase):
    """
    Agent that monitors device telemetry, scores device health,
    predicts failures before they happen, and initiates remedial actions.
    """

    TASKS = {
        "ingest_telemetry",     # push new telemetry into the health record
        "score_health",         # compute composite 0–100 health score
        "predict_failure",      # estimate time-to-failure
        "maintenance_schedule", # produce a prioritised maintenance list
        "auto_heal",            # trigger automatic remediation
        "fleet_health_report",  # health summary across all devices
        "anomaly_score",        # per-device anomaly severity (0–1)
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("predictive_maintenance_agent", config)
        self._records: Dict[str, DeviceHealthRecord] = {}

    # ------------------------------------------------------------------
    # AgentBase interface
    # ------------------------------------------------------------------

    async def _execute(
        self,
        task: str,
        params: Dict[str, Any],
        device: Optional[ESP32Device],
    ) -> Any:
        if task == "ingest_telemetry":
            return self._ingest(params, device)
        if task == "score_health":
            return self._score_health(device)
        if task == "predict_failure":
            return self._predict_failure(device)
        if task == "maintenance_schedule":
            return self._maintenance_schedule()
        if task == "auto_heal":
            return await self._auto_heal(params, device)
        if task == "fleet_health_report":
            return self._fleet_report()
        if task == "anomaly_score":
            return self._anomaly_score(device)
        raise ValueError(f"Unknown task: {task}")

    # ------------------------------------------------------------------
    # Telemetry ingestion
    # ------------------------------------------------------------------

    def _ingest(self, params: Dict[str, Any], device: Optional[ESP32Device]) -> Dict[str, Any]:
        device_id = device.device_id if device else params.get("device_id", "unknown")
        rec = self._records.setdefault(device_id, DeviceHealthRecord(device_id))
        telemetry = params.get("telemetry", device.telemetry if device else {})
        error_rate = params.get("error_rate", 0.0)
        rec.record(telemetry, error_rate)
        if device:
            device.update_telemetry(telemetry)
        return {"ingested": True, "device_id": device_id, "samples": len(rec.rssi_history)}

    # ------------------------------------------------------------------
    # Health scoring
    # ------------------------------------------------------------------

    def _score_health(self, device: Optional[ESP32Device]) -> Dict[str, Any]:
        """
        Compute a 0–100 composite health score.
        100 = perfectly healthy, 0 = critical failure.
        """
        device_id = device.device_id if device else "unknown"
        rec = self._records.get(device_id)
        if not rec:
            return {"device_id": device_id, "health_score": None, "reason": "no_data"}

        components: Dict[str, float] = {}

        # RSSI component: -50 dBm → 100, -100 dBm → 0
        if rec.rssi_history:
            avg_rssi = _ewma(list(rec.rssi_history))
            components["rssi"] = max(0, min(100, (avg_rssi + 100) * 2))
        else:
            components["rssi"] = 50  # neutral

        # Heap component: 250K → 100, 10K → 0
        if rec.heap_history:
            avg_heap = _ewma(list(rec.heap_history))
            components["heap"] = max(0, min(100, (avg_heap - 10_000) / 2400))
        else:
            components["heap"] = 75

        # Uptime stability: penalise frequent resets
        reboot_penalty = min(100, rec.reboot_count * 20)
        components["uptime"] = max(0, 100 - reboot_penalty)

        # Error rate: 0% → 100, 100% → 0
        if rec.error_history:
            avg_err = _ewma(list(rec.error_history))
            components["error_rate"] = max(0, 100 - avg_err * 100)
        else:
            components["error_rate"] = 100

        # Temperature proxy: estimated from CPU freq changes
        components["temp"] = 80  # default; real value from telemetry if available

        # Weighted composite
        score = sum(
            HEALTH_WEIGHTS.get(k, 0) * v for k, v in components.items()
        )
        score = round(score, 1)
        rec.health_history.append(score)

        trend = _trend_slope(list(rec.health_history)[-20:])
        status = (
            "critical" if score < 30 else
            "warning"  if score < 60 else
            "fair"     if score < 80 else
            "good"
        )

        return {
            "device_id": device_id,
            "health_score": score,
            "status": status,
            "components": components,
            "trend": round(trend, 3),
            "trend_direction": "improving" if trend > 0 else ("declining" if trend < 0 else "stable"),
        }

    # ------------------------------------------------------------------
    # Failure prediction
    # ------------------------------------------------------------------

    def _predict_failure(self, device: Optional[ESP32Device]) -> Dict[str, Any]:
        """
        Estimate time-to-failure using linear extrapolation of health trend.
        """
        device_id = device.device_id if device else "unknown"
        rec = self._records.get(device_id)
        if not rec or len(rec.health_history) < 5:
            return {"device_id": device_id, "prediction": "insufficient_data"}

        health = list(rec.health_history)
        slope = _trend_slope(health)
        current = health[-1]

        if slope >= 0:
            return {
                "device_id": device_id,
                "failure_risk": "low",
                "current_health": current,
                "prediction": "healthy_trend",
            }

        # Steps until health reaches critical threshold (30)
        if slope < 0:
            steps_to_critical = (current - 30) / abs(slope)
        else:
            steps_to_critical = float("inf")

        # Convert steps to estimated time (assume 5s telemetry interval)
        seconds_to_critical = steps_to_critical * 5
        eta = datetime.now(timezone.utc) + timedelta(seconds=seconds_to_critical)

        failure_prob = _logistic(-(current - 50) / 15)  # sigmoid centred at 50

        risk = "critical" if failure_prob > 0.75 else "high" if failure_prob > 0.5 else "medium"

        return {
            "device_id": device_id,
            "current_health": round(current, 1),
            "health_slope": round(slope, 3),
            "failure_probability": round(failure_prob, 3),
            "failure_risk": risk,
            "estimated_critical_at": eta.isoformat(),
            "steps_to_critical": round(steps_to_critical, 1),
            "recommendation": self._remediation_action(risk, current),
        }

    @staticmethod
    def _remediation_action(risk: str, health: float) -> str:
        if risk == "critical":
            return "Immediate action: reboot device or trigger OTA update"
        if risk == "high":
            return "Schedule OTA firmware update within 1 hour"
        return "Monitor closely; consider frequency re-scan to improve RSSI"

    # ------------------------------------------------------------------
    # Maintenance schedule
    # ------------------------------------------------------------------

    def _maintenance_schedule(self) -> Dict[str, Any]:
        """Generate a prioritised maintenance schedule for all known devices."""
        schedule = []
        for device_id, rec in self._records.items():
            if rec.health_history:
                health = rec.health_history[-1]
                schedule.append({
                    "device_id": device_id,
                    "health_score": round(health, 1),
                    "priority": "P1" if health < 30 else "P2" if health < 60 else "P3",
                    "recommended_action": self._remediation_action(
                        "critical" if health < 30 else "high" if health < 60 else "medium",
                        health,
                    ),
                })
        # Sort by priority then health score
        schedule.sort(key=lambda x: (x["priority"], x["health_score"]))
        return {
            "schedule": schedule,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Auto-heal
    # ------------------------------------------------------------------

    async def _auto_heal(
        self, params: Dict[str, Any], device: Optional[ESP32Device]
    ) -> Dict[str, Any]:
        """
        Automatically apply a remediation action based on the current health score.
        """
        if not device:
            return {"healed": False, "reason": "no_device"}

        score_result = self._score_health(device)
        score = score_result.get("health_score", 100)
        actions_taken = []

        if score is None:
            return {"healed": False, "reason": "no_health_data"}

        if score < 30:
            # Critical: attempt OTA update
            logger.warning("Auto-heal [CRITICAL] %s score=%.1f — triggering OTA", device.device_id, score)
            try:
                ota_url = params.get("ota_url", self.config.get("default_ota_url", ""))
                if ota_url:
                    resp = await device.send_command("ota_update", {"url": ota_url})
                    actions_taken.append({"action": "ota_update", "result": resp})
            except Exception as exc:  # pylint: disable=broad-except
                actions_taken.append({"action": "ota_update", "error": str(exc)})
            rec = self._records.get(device.device_id)
            if rec:
                rec.ota_count += 1

        elif score < 60:
            # Warning: re-scan frequency for better RSSI
            logger.info("Auto-heal [WARNING] %s score=%.1f — triggering freq re-scan", device.device_id, score)
            if self.orchestrator:
                freq_agents = self.orchestrator.get_agents_by_type("frequency_agent")
                if freq_agents:
                    await self.orchestrator.dispatch_task(
                        freq_agents[0].agent_id, "fine_tune",
                        {"step_hz": 1e6, "iterations": 3}, device.device_id
                    )
                    actions_taken.append({"action": "frequency_fine_tune"})

        return {
            "device_id": device.device_id,
            "health_score": score,
            "healed": len(actions_taken) > 0,
            "actions_taken": actions_taken,
        }

    # ------------------------------------------------------------------
    # Fleet report
    # ------------------------------------------------------------------

    def _fleet_report(self) -> Dict[str, Any]:
        """Return health summary across all known devices."""
        summaries = []
        for device_id, rec in self._records.items():
            health = rec.health_history[-1] if rec.health_history else None
            summaries.append({
                "device_id": device_id,
                "health_score": round(health, 1) if health is not None else None,
                "samples": len(rec.rssi_history),
                "reboots": rec.reboot_count,
                "ota_updates": rec.ota_count,
            })
        summaries.sort(key=lambda x: x.get("health_score") or 100)
        avg = (sum(s["health_score"] for s in summaries if s["health_score"] is not None)
               / max(len([s for s in summaries if s["health_score"] is not None]), 1))
        return {
            "fleet_health_avg": round(avg, 1),
            "total_devices": len(summaries),
            "critical_count": sum(1 for s in summaries if (s["health_score"] or 100) < 30),
            "warning_count": sum(1 for s in summaries if 30 <= (s["health_score"] or 100) < 60),
            "devices": summaries,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Anomaly scoring
    # ------------------------------------------------------------------

    def _anomaly_score(self, device: Optional[ESP32Device]) -> Dict[str, Any]:
        """
        Compute a 0–1 anomaly severity score using EWMA deviation.
        0 = nominal, 1 = severe anomaly.
        """
        device_id = device.device_id if device else "unknown"
        rec = self._records.get(device_id)
        if not rec or len(rec.rssi_history) < 5:
            return {"device_id": device_id, "anomaly_score": 0.0, "reason": "insufficient_data"}

        samples = list(rec.rssi_history)
        ewma_val = _ewma(samples)
        deviations = [abs(s - ewma_val) for s in samples[-10:]]
        avg_dev = sum(deviations) / len(deviations)
        # Normalise: deviation of 20 dB = score 1.0
        score = min(1.0, avg_dev / 20)
        return {
            "device_id": device_id,
            "anomaly_score": round(score, 3),
            "ewma_rssi": round(ewma_val, 1),
            "avg_deviation_db": round(avg_dev, 2),
        }
