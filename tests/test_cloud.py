"""
Tests for cloud connectors and the telemetry monitor.
"""

import asyncio
import pytest

from cloud.connector import CloudConnector, HTTPConnector
from logging_system.monitor import TelemetryMonitor, Alert


# ------------------------------------------------------------------
# CloudConnector factory
# ------------------------------------------------------------------

def test_factory_http():
    c = CloudConnector.create("http", "http://localhost/telemetry")
    assert isinstance(c, HTTPConnector)


def test_factory_unknown():
    with pytest.raises(ValueError, match="Unknown connector type"):
        CloudConnector.create("ftp", "ftp://example.com")


@pytest.mark.asyncio
async def test_http_connector_no_endpoint():
    """With an empty endpoint the HTTP connector should return True (dev mode)."""
    c = HTTPConnector("", {})
    ok = await c.push({"device_id": "test", "rssi": -70})
    assert ok is True


@pytest.mark.asyncio
async def test_http_connector_pull_no_endpoint():
    c = HTTPConnector("", {})
    result = await c.pull()
    assert result is None


# ------------------------------------------------------------------
# TelemetryMonitor
# ------------------------------------------------------------------

class _MockOrchestrator:
    """Minimal orchestrator stub for the monitor tests."""

    def __init__(self):
        self._devices = []

    def list_devices(self):
        return self._devices


def test_monitor_set_threshold():
    orch = _MockOrchestrator()
    monitor = TelemetryMonitor(orch)
    monitor.set_threshold("rssi", min_value=-85, max_value=0)
    assert monitor._thresholds["rssi"]["min"] == -85
    assert monitor._thresholds["rssi"]["max"] == 0


def test_monitor_alert_callback():
    orch = _MockOrchestrator()
    monitor = TelemetryMonitor(orch)
    alerts = []
    monitor.on_alert(lambda a: alerts.append(a))
    monitor._raise_alert("dev-1", "rssi", -95, -90, "rssi below minimum")
    assert len(alerts) == 1
    assert isinstance(alerts[0], Alert)
    assert alerts[0].metric == "rssi"


def test_monitor_get_alerts_empty():
    orch = _MockOrchestrator()
    monitor = TelemetryMonitor(orch)
    assert monitor.get_alerts() == []


def test_monitor_get_alerts_filtered():
    orch = _MockOrchestrator()
    monitor = TelemetryMonitor(orch)
    monitor._raise_alert("dev-1", "rssi", -95, -90, "rssi low")
    monitor._raise_alert("dev-2", "rssi", -95, -90, "rssi low")
    assert len(monitor.get_alerts("dev-1")) == 1
    assert len(monitor.get_alerts("dev-2")) == 1
    assert len(monitor.get_alerts()) == 2


def test_alert_to_dict():
    a = Alert("dev-1", "rssi", -95, -90, "test alert")
    d = a.to_dict()
    assert d["device_id"] == "dev-1"
    assert d["metric"] == "rssi"
    assert d["value"] == -95
    assert d["threshold"] == -90
