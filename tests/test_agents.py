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


@pytest.mark.asyncio
async def test_ai_full_series_single_pass_no_device():
    """full_series with passes=1 returns correct structure when no device is present."""
    agent = AIAgent()
    await agent.start()
    result = await agent.execute("full_series", {"passes": 1}, None)
    assert result["task"] == "full_series"
    assert result["passes"] == 1
    assert len(result["rounds"]) == 1
    round0 = result["rounds"][0]
    assert round0["round"] == 1
    assert "interference" in round0
    assert "anomaly" in round0
    assert "recommendations" in round0
    assert "timestamp" in result
    await agent.stop()


@pytest.mark.asyncio
async def test_ai_full_series_double_pass_no_device():
    """full_series with passes=2 produces two rounds."""
    agent = AIAgent()
    await agent.start()
    result = await agent.execute("full_series", {"passes": 2}, None)
    assert result["passes"] == 2
    assert len(result["rounds"]) == 2
    assert result["rounds"][0]["round"] == 1
    assert result["rounds"][1]["round"] == 2
    await agent.stop()


@pytest.mark.asyncio
async def test_ai_full_series_triple_pass_no_device():
    """full_series with passes=3 produces three rounds."""
    agent = AIAgent()
    await agent.start()
    result = await agent.execute("full_series", {"passes": 3}, None)
    assert result["passes"] == 3
    assert len(result["rounds"]) == 3
    await agent.stop()


@pytest.mark.asyncio
async def test_ai_full_series_chaimera_summary():
    """full_series queries CHAiMERA3sp for a summary when a provider is configured."""
    from unittest.mock import patch, AsyncMock

    agent = AIAgent({
        "chaimera3sp": {
            "strategy": "first",
            "providers": {"kimi": {"api_key": "kimi-key"}},
        }
    })
    await agent.start()
    mock_resp = {
        "provider": "kimi",
        "response": "RF health looks good.",
        "model": "kimi-2.6",
        "timestamp": "2026-01-01T00:00:00+00:00",
    }
    with patch.object(agent._chaimera, "query", new_callable=AsyncMock, return_value=mock_resp):
        result = await agent.execute("full_series", {"passes": 1}, None)
    assert result["rounds"][0].get("chaimera_summary") == "RF health looks good."
    assert result["rounds"][0].get("chaimera_provider") == "kimi"
    await agent.stop()


# ------------------------------------------------------------------
# AIAgent — pipeline_sim (Series → Parallel → Series)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_sim_structure_no_device():
    """pipeline_sim returns all three phase keys with no device attached."""
    agent = AIAgent()
    await agent.start()
    result = await agent.execute("pipeline_sim", {}, None)

    assert result["task"] == "pipeline_sim"
    assert "phase1" in result
    assert "phase2" in result
    assert "phase3" in result
    assert "timestamp" in result
    await agent.stop()


@pytest.mark.asyncio
async def test_pipeline_sim_phase1_series_order():
    """Phase 1 contains all three series commands."""
    agent = AIAgent()
    await agent.start()
    result = await agent.execute("pipeline_sim", {}, None)

    p1 = result["phase1"]
    assert "interference" in p1
    assert "anomaly" in p1
    assert "congestion" in p1
    await agent.stop()


@pytest.mark.asyncio
async def test_pipeline_sim_phase2_parallel_keys():
    """Phase 2 contains results for all parallel workloads."""
    agent = AIAgent()
    await agent.start()
    result = await agent.execute("pipeline_sim", {}, None)

    p2 = result["phase2"]
    assert "recommendations" in p2
    assert "optimise" in p2
    assert "local_compute" in p2
    assert "chaimera" in p2
    assert isinstance(p2["chaimera"], list)
    await agent.stop()


@pytest.mark.asyncio
async def test_pipeline_sim_phase3_transmission():
    """Phase 3 produces a transmission payload with expected keys."""
    agent = AIAgent()
    await agent.start()
    result = await agent.execute("pipeline_sim", {}, None)

    p3 = result["phase3"]
    assert "payload_size_bytes" in p3
    assert isinstance(p3["payload_size_bytes"], int)
    assert p3["payload_size_bytes"] > 0
    assert p3["record_count"] == 1
    assert "transmission" in p3
    tx = p3["transmission"]
    assert tx["format"] == "json"
    assert tx["encoding"] == "utf-8"
    assert "record" in tx
    await agent.stop()


@pytest.mark.asyncio
async def test_pipeline_sim_transmission_record_fields():
    """Transmission record carries all pipeline-1 and pipeline-2 summary fields."""
    agent = AIAgent()
    await agent.start()
    result = await agent.execute("pipeline_sim", {}, None)

    record = result["phase3"]["transmission"]["record"]
    assert "pipeline_version" in record
    assert "timestamp" in record
    assert "phase1_interference" in record
    assert "phase1_anomaly_count" in record
    assert "phase1_congestion_risk" in record
    assert "phase2_recommendations" in record
    assert "phase2_optimised" in record
    assert "phase2_devices_analysed" in record
    assert "phase2_chaimera_responses" in record
    await agent.stop()


@pytest.mark.asyncio
async def test_pipeline_sim_chaimera_parallel_queries():
    """When a CHAiMERA3sp provider is configured, phase 2 includes its response."""
    from unittest.mock import patch, AsyncMock

    agent = AIAgent({
        "chaimera3sp": {
            "strategy": "first",
            "providers": {"kimi": {"api_key": "kimi-key"}},
        }
    })
    await agent.start()
    mock_resp = {
        "provider": "kimi",
        "response": "Parallel compute recommendation.",
        "model": "kimi-2.6",
        "timestamp": "2026-01-01T00:00:00+00:00",
    }
    with patch.object(agent._chaimera, "query", new_callable=AsyncMock, return_value=mock_resp):
        result = await agent.execute("pipeline_sim", {}, None)

    chaimera_list = result["phase2"]["chaimera"]
    assert len(chaimera_list) >= 1
    responses = [r.get("response", "") for r in chaimera_list]
    assert any("Parallel compute recommendation." in r for r in responses)
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
