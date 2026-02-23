"""
Telemetry Monitor — real-time device monitoring with configurable
alert thresholds and callback hooks.
"""

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Callable, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


class Alert:
    def __init__(self, device_id: str, metric: str, value: Any, threshold: Any, message: str):
        self.device_id = device_id
        self.metric = metric
        self.value = value
        self.threshold = threshold
        self.message = message
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "metric": self.metric,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message,
            "timestamp": self.timestamp,
        }


class TelemetryMonitor:
    """
    Monitors device telemetry streams for threshold violations and emits alerts.

    Usage:
        monitor = TelemetryMonitor(orchestrator)
        monitor.set_threshold("rssi", min_value=-90)
        await monitor.start()
    """

    DEFAULT_THRESHOLDS = {
        "rssi": {"min": -90},
        "free_heap_bytes": {"min": 10_000},
        "uptime_sec": {"max": None},
    }

    def __init__(self, orchestrator: Any, poll_interval: float = 5.0):
        self.orchestrator = orchestrator
        self.poll_interval = poll_interval
        self._thresholds: Dict[str, Dict[str, Any]] = dict(self.DEFAULT_THRESHOLDS)
        self._alert_history: Deque[Alert] = deque(maxlen=1000)
        self._alert_callbacks: List[Callable[[Alert], None]] = []
        self._telemetry_history: Dict[str, Deque[Dict]] = defaultdict(lambda: deque(maxlen=200))
        self._running = False

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_threshold(self, metric: str, min_value: Optional[float] = None,
                      max_value: Optional[float] = None) -> None:
        self._thresholds[metric] = {"min": min_value, "max": max_value}

    def on_alert(self, callback: Callable[[Alert], None]) -> None:
        self._alert_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        asyncio.ensure_future(self._poll_loop())
        logger.info("TelemetryMonitor started (poll=%.1fs)", self.poll_interval)

    async def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        while self._running:
            for device in self.orchestrator.list_devices():
                try:
                    await self._poll_device(device)
                except Exception as exc:  # pylint: disable=broad-except
                    logger.debug("Monitor poll error for %s: %s", device.device_id, exc)
            await asyncio.sleep(self.poll_interval)

    async def _poll_device(self, device: Any) -> None:
        """Fetch latest telemetry from a device and check thresholds."""
        try:
            resp = await device.send_command("get_telemetry")
        except Exception:  # pylint: disable=broad-except
            return

        telemetry = {**resp, "timestamp": datetime.now(timezone.utc).isoformat()}
        device.update_telemetry(telemetry)
        self._telemetry_history[device.device_id].append(telemetry)

        for metric, bounds in self._thresholds.items():
            value = telemetry.get(metric)
            if value is None:
                continue
            min_v = bounds.get("min")
            max_v = bounds.get("max")
            if min_v is not None and value < min_v:
                self._raise_alert(device.device_id, metric, value, min_v,
                                  f"{metric} below minimum threshold")
            if max_v is not None and value > max_v:
                self._raise_alert(device.device_id, metric, value, max_v,
                                  f"{metric} exceeds maximum threshold")

    def _raise_alert(self, device_id: str, metric: str, value: Any,
                     threshold: Any, message: str) -> None:
        alert = Alert(device_id, metric, value, threshold, message)
        self._alert_history.append(alert)
        logger.warning("ALERT [%s] %s=%s (threshold=%s)", device_id, metric, value, threshold)
        for cb in self._alert_callbacks:
            try:
                cb(alert)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Alert callback error: %s", exc)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_alerts(self, device_id: Optional[str] = None) -> List[Dict[str, Any]]:
        alerts = list(self._alert_history)
        if device_id:
            alerts = [a for a in alerts if a.device_id == device_id]
        return [a.to_dict() for a in alerts]

    def get_telemetry_history(self, device_id: str) -> List[Dict[str, Any]]:
        return list(self._telemetry_history.get(device_id, []))
