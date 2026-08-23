"""
Tests for cloud connectors, compute backends, and the telemetry monitor.
"""

import asyncio
import pytest

from cloud.connector import CloudConnector, HTTPConnector
from cloud.compute import (
    ComputeBackend,
    LocalComputeBackend,
    AWSComputeBackend,
    GCPComputeBackend,
    compute_config_from_dict,
)
from logging_system.monitor import TelemetryMonitor, Alert


# ------------------------------------------------------------------
# CloudConnector factory
# ------------------------------------------------------------------

def test_factory_http():
    c = CloudConnector.create("http", "http://localhost/telemetry")
    assert isinstance(c, HTTPConnector)


def test_factory_vps_and_local_aliases():
    """vps/local connector types map to the generic HTTP webhook connector."""
    assert isinstance(CloudConnector.create("vps", "https://my-vps.example.com"), HTTPConnector)
    assert isinstance(CloudConnector.create("local", "http://192.168.1.10:9000"), HTTPConnector)


def test_factory_nested_backend_config():
    """Nested style {backend: ..., endpoint: ...} resolves via config."""
    c = CloudConnector.create("cloud_connector", "", {"backend": "vps", "endpoint": "http://x"})
    assert isinstance(c, HTTPConnector)
    assert c.endpoint == "http://x"


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


def test_http_connector_url_building():
    c = HTTPConnector("https://vps.example.com/", {"path_prefix": "/telemetry"})
    assert c._url() == "https://vps.example.com/telemetry"
    assert c._url("messages") == "https://vps.example.com/telemetry/messages"


def test_http_connector_headers_include_bearer():
    c = HTTPConnector("https://vps.example.com", {"api_key": "secret-key"})
    headers = c._headers()
    assert headers["Authorization"] == "******"
    assert headers["Content-Type"] == "application/json"


def test_http_connector_headers_no_key():
    c = HTTPConnector("https://vps.example.com", {})
    assert "Authorization" not in c._headers()


# ------------------------------------------------------------------
# ComputeBackend factory
# ------------------------------------------------------------------

def test_compute_factory_local_and_vps():
    assert isinstance(ComputeBackend.create("local"), LocalComputeBackend)
    assert isinstance(ComputeBackend.create("vps"), LocalComputeBackend)


def test_compute_factory_aws_gcp():
    assert isinstance(ComputeBackend.create("aws", {"function": "f"}), AWSComputeBackend)
    assert isinstance(ComputeBackend.create("gcp", {"endpoint": "http://x"}), GCPComputeBackend)


def test_compute_factory_unknown():
    with pytest.raises(ValueError, match="Unknown compute backend"):
        ComputeBackend.create("quantum")


def test_compute_config_from_dict_nested():
    cfg = compute_config_from_dict({"compute": {"backend": "aws", "function": "f"}})
    assert cfg == {"backend": "aws", "function": "f"}


def test_compute_config_from_dict_flat_prefixed():
    cfg = compute_config_from_dict({"compute_backend": "gcp", "compute_endpoint": "http://x"})
    assert cfg == {"backend": "gcp", "endpoint": "http://x"}


def test_compute_config_from_dict_empty():
    assert compute_config_from_dict({}) == {}
    assert compute_config_from_dict(None) == {}


@pytest.mark.asyncio
async def test_local_compute_in_process():
    """Without an endpoint, local compute acknowledges in-process execution."""
    b = LocalComputeBackend({})
    result = await b.run("firmware_build", {"features": ["wifi"]})
    assert result["ok"] is True
    assert result["backend"] == "local"
    assert result["mode"] == "in-process"


@pytest.mark.asyncio
async def test_local_compute_endpoint_unreachable():
    """An unreachable VPS endpoint returns a clean failure, not an exception."""
    b = LocalComputeBackend({"endpoint": "http://127.0.0.1:1/unreachable"})
    result = await b.run("ai_batch", {})
    assert result["ok"] is False
    assert result["backend"] == "local"
    assert "error" in result


@pytest.mark.asyncio
async def test_aws_compute_requires_function():
    b = AWSComputeBackend({})
    result = await b.run("job", {})
    assert result["ok"] is False
    assert result["error"] == "function_required"


@pytest.mark.asyncio
async def test_gcp_compute_requires_endpoint():
    b = GCPComputeBackend({})
    result = await b.run("job", {})
    assert result["ok"] is False
    assert result["error"] == "endpoint_required"


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
