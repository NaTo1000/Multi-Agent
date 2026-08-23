"""
Tests for individual agent implementations.
Agents are tested with None device (no real hardware needed).
"""

import asyncio
import pytest

from agents import FrequencyAgent, ModulationAgent, FirmwareAgent, AIAgent, CommsAgent
from orchestrator.agent import AgentStatus


# ------------------------------------------------------------------
# FrequencyAgent
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_frequency_get_no_device():
    agent = FrequencyAgent()
    await agent.start()
    result = await agent.execute("get_frequency", {}, None)
    assert "frequency_hz" in result
    assert result["frequency_hz"] is None
    await agent.stop()


@pytest.mark.asyncio
async def test_frequency_scan_no_device():
    agent = FrequencyAgent()
    await agent.start()
    result = await agent.execute("scan", {"band": "2.4GHz"}, None)
    assert "channels" in result
    assert result["band"] == "2.4GHz"
    assert len(result["channels"]) > 0
    await agent.stop()


@pytest.mark.asyncio
async def test_frequency_scan_bad_band():
    agent = FrequencyAgent()
    await agent.start()
    with pytest.raises(ValueError):
        await agent.execute("scan", {"band": "99GHz"}, None)
    await agent.stop()


@pytest.mark.asyncio
async def test_frequency_lock_no_device():
    agent = FrequencyAgent()
    await agent.start()
    result = await agent.execute("lock", {"target_hz": 2.4e9}, None)
    assert result["locked"] is False
    await agent.stop()


@pytest.mark.asyncio
async def test_frequency_unknown_task():
    agent = FrequencyAgent()
    await agent.start()
    with pytest.raises(ValueError):
        await agent.execute("nonexistent_task", {}, None)
    await agent.stop()


# ------------------------------------------------------------------
# ModulationAgent
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_modulation_list_schemes():
    agent = ModulationAgent()
    await agent.start()
    result = await agent.execute("list_schemes", {}, None)
    assert "schemes" in result
    assert "GFSK" in result["schemes"]
    assert "LoRa" in result["schemes"]
    await agent.stop()


@pytest.mark.asyncio
async def test_modulation_set_no_device():
    agent = ModulationAgent()
    await agent.start()
    result = await agent.execute("set_modulation", {"scheme": "GFSK"}, None)
    assert result["ok"] is False
    assert result["reason"] == "no_device"
    await agent.stop()


@pytest.mark.asyncio
async def test_modulation_bad_scheme():
    agent = ModulationAgent()
    await agent.start()
    with pytest.raises(ValueError, match="Unsupported scheme"):
        await agent.execute("set_modulation", {"scheme": "XYZ"}, None)
    await agent.stop()


# ------------------------------------------------------------------
# FirmwareAgent
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_firmware_build():
    agent = FirmwareAgent()
    await agent.start()
    result = await agent.execute(
        "build",
        {"template": "base", "features": ["wifi"], "version": "test-1.0"},
        None,
    )
    assert result["success"] is True
    assert "build_id" in result
    assert result["version"] == "test-1.0"
    await agent.stop()


@pytest.mark.asyncio
async def test_firmware_build_cached():
    agent = FirmwareAgent()
    await agent.start()
    params = {"template": "base", "features": ["wifi"], "version": "cached-1.0"}
    r1 = await agent.execute("build", params, None)
    r2 = await agent.execute("build", params, None)
    assert r1["build_id"] == r2["build_id"]
    await agent.stop()


@pytest.mark.asyncio
async def test_firmware_list_builds():
    agent = FirmwareAgent()
    await agent.start()
    await agent.execute("build", {"features": ["wifi"], "version": "list-test"}, None)
    result = await agent.execute("list_builds", {}, None)
    assert "builds" in result
    assert len(result["builds"]) >= 1
    await agent.stop()


@pytest.mark.asyncio
async def test_firmware_flash_no_device():
    agent = FirmwareAgent()
    await agent.start()
    result = await agent.execute("flash", {"firmware_url": "http://example.com/fw.bin"}, None)
    assert result["ok"] is False
    await agent.stop()


# ------------------------------------------------------------------
# AIAgent
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_research_builtin():
    agent = AIAgent()
    await agent.start()
    result = await agent.execute("research", {"query": "best modulation for ESP32"}, None)
    assert "response" in result
    assert result["source"] == "builtin_heuristics"
    await agent.stop()


@pytest.mark.asyncio
async def test_ai_anomaly_no_device():
    agent = AIAgent()
    await agent.start()
    result = await agent.execute("anomaly_detect", {}, None)
    assert "anomalies" in result
    assert result["anomalies"] == []
    await agent.stop()


# ------------------------------------------------------------------
# CommsAgent
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_comms_wifi_scan_no_device():
    agent = CommsAgent()
    await agent.start()
    result = await agent.execute("wifi_scan", {}, None)
    assert result["reason"] == "no_device"
    await agent.stop()


@pytest.mark.asyncio
async def test_comms_gps_no_device():
    agent = CommsAgent()
    await agent.start()
    result = await agent.execute("get_gps", {}, None)
    assert result["fix"] is False
    await agent.stop()


@pytest.mark.asyncio
async def test_comms_cloud_push_nested_connector_config():
    """Nested cloud_connector {backend: ...} config resolves to the right connector."""
    agent = CommsAgent({"cloud_connector": {"backend": "vps", "endpoint": ""}})
    await agent.start()
    result = await agent.execute("cloud_push", {"payload": {"k": 1}}, None)
    assert result["ok"] is True  # empty endpoint → dev-mode success
    assert result["connector"] == "vps"
    await agent.stop()


@pytest.mark.asyncio
async def test_comms_compute_offload_defaults_to_local():
    agent = CommsAgent()
    await agent.start()
    result = await agent.execute(
        "compute_offload", {"job": "firmware_build", "payload": {}}, None
    )
    assert result["ok"] is True
    assert result["backend"] == "local"
    await agent.stop()


@pytest.mark.asyncio
async def test_comms_compute_offload_uses_config_section():
    agent = CommsAgent({"compute": {"backend": "local"}})
    await agent.start()
    result = await agent.execute("compute_offload", {"job": "j"}, None)
    assert result["backend"] == "local"
    await agent.stop()


@pytest.mark.asyncio
async def test_comms_compute_offload_per_request_override():
    """Per-request backend override wins over config; aws without function fails cleanly."""
    agent = CommsAgent({"compute": {"backend": "local"}})
    await agent.start()
    result = await agent.execute(
        "compute_offload", {"backend": "aws", "job": "j"}, None
    )
    assert result["backend"] == "aws"
    assert result["ok"] is False
    assert result["error"] == "function_required"
    await agent.stop()


# ------------------------------------------------------------------
# Agent metrics
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_metrics_track_completion():
    agent = FrequencyAgent()
    await agent.start()
    await agent.execute("get_frequency", {}, None)
    metrics = agent.get_metrics()
    assert metrics["tasks_completed"] == 1
    assert metrics["tasks_failed"] == 0
    await agent.stop()


@pytest.mark.asyncio
async def test_agent_metrics_track_failure():
    agent = FrequencyAgent()
    await agent.start()
    with pytest.raises(ValueError):
        await agent.execute("bad_task", {}, None)
    metrics = agent.get_metrics()
    assert metrics["tasks_failed"] == 1
    await agent.stop()
