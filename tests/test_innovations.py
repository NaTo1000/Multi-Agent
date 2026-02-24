"""
Tests for Innovation Wave — Spectrum Analyzer, Discovery, Predictive Maintenance,
Device Simulator, LLM Client.
"""

import asyncio
import math
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ─────────────────────────────────────────────────────────────────────────────
# Spectrum Analyzer Agent
# ─────────────────────────────────────────────────────────────────────────────
from agents.spectrum_agent import SpectrumAnalyzerAgent, _fft, _power_db, BAND_CHANNELS


class TestFFT:
    def test_fft_trivial(self):
        result = _fft([1 + 0j])
        assert result == [1 + 0j]

    def test_fft_length_4(self):
        signal = [1+0j, 0+0j, 0+0j, 0+0j]
        result = _fft(signal)
        assert len(result) == 4
        assert abs(result[0] - (1+0j)) < 1e-9

    def test_fft_non_power_of_two_pads(self):
        signal = [1+0j, 1+0j, 1+0j]  # length 3 → pads to 4
        result = _fft(signal)
        assert len(result) == 4

    def test_power_db_zero_input(self):
        assert _power_db(0j) < 0   # log(epsilon) is very negative

    def test_power_db_unit(self):
        assert abs(_power_db(1+0j)) < 0.01   # |1| = 1 → 0 dB


class TestSpectrumAgent:
    @pytest.fixture
    def agent(self):
        return SpectrumAnalyzerAgent()

    @pytest.mark.asyncio
    async def test_sweep_synthetic(self, agent):
        result = await agent._execute("sweep", {"band": "2.4GHz"}, None)
        assert result["band"] == "2.4GHz"
        assert len(result["channels"]) == 13
        assert "psd" in result

    @pytest.mark.asyncio
    async def test_sweep_builds_waterfall(self, agent):
        await agent._execute("sweep", {"band": "2.4GHz"}, None)
        await agent._execute("sweep", {"band": "2.4GHz"}, None)
        wf = agent._get_waterfall(None)
        assert wf["depth"] == 2

    @pytest.mark.asyncio
    async def test_channel_occupancy(self, agent):
        result = await agent._execute("channel_occupancy", {"band": "2.4GHz"}, None)
        assert "channels" in result
        for ch in result["channels"]:
            assert "busy" in ch
            assert "busy_pct" in ch

    @pytest.mark.asyncio
    async def test_find_best_channels(self, agent):
        result = await agent._execute(
            "find_best_channels", {"band": "2.4GHz", "n": 3}, None
        )
        assert len(result["best_channels"]) == 3

    @pytest.mark.asyncio
    async def test_peak_interference(self, agent):
        result = await agent._execute("peak_interference", {"band": "2.4GHz"}, None)
        assert "peak_channel" in result
        assert "recommendation" in result

    @pytest.mark.asyncio
    async def test_waterfall_frame(self, agent):
        result = await agent._execute("waterfall_frame", {"band": "2.4GHz"}, None)
        assert result["type"] == "waterfall_frame"
        assert "psd" in result

    def test_synthetic_rssi_busy_channel(self, agent):
        # ch6 at 2437 MHz should be busier than an edge channel
        rssi_ch6  = agent._synthetic_rssi(2437e6)
        rssi_edge = agent._synthetic_rssi(2412e6)
        # Over many samples the busy channel should average higher
        avg_ch6  = sum(agent._synthetic_rssi(2437e6) for _ in range(50)) / 50
        avg_edge = sum(agent._synthetic_rssi(2412e6) for _ in range(50)) / 50
        assert avg_ch6 > avg_edge

    def test_band_channels_coverage(self):
        for band in ("2.4GHz", "5GHz", "915MHz", "868MHz", "433MHz"):
            assert len(BAND_CHANNELS[band]) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Discovery Agent
# ─────────────────────────────────────────────────────────────────────────────
from agents.discovery_agent import DiscoveryAgent


class TestDiscoveryAgent:
    @pytest.fixture
    def agent(self):
        return DiscoveryAgent()

    @pytest.mark.asyncio
    async def test_list_empty_initially(self, agent):
        result = await agent._execute("list_discovered", {}, None)
        assert result["devices"] == []

    @pytest.mark.asyncio
    async def test_clear_discovered(self, agent):
        agent._discovered["1.2.3.4"] = {"ip_address": "1.2.3.4"}
        result = await agent._execute("clear_discovered", {}, None)
        assert result["ok"] is True
        assert agent._discovered == {}

    @pytest.mark.asyncio
    async def test_arp_scan_invalid_subnet(self, agent):
        result = await agent._execute("arp_scan", {"subnet": "not-a-cidr"}, None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_arp_scan_loopback_no_crash(self, agent):
        # Scanning loopback /32 — only 1 host, connection refused, no crash
        result = await agent._execute("arp_scan", {"subnet": "127.0.0.1/32"}, None)
        assert "devices" in result

    @pytest.mark.asyncio
    async def test_file_import_yaml_missing(self, agent):
        result = await agent._execute(
            "file_import", {"path": "/nonexistent/devices.yaml"}, None
        )
        assert "devices" in result  # gracefully returns empty list

    @pytest.mark.asyncio
    async def test_discover_all_returns_structure(self, agent):
        result = await agent._execute("discover", {}, None)
        assert "discovered" in result
        assert "registered" in result
        assert "devices" in result

    def test_guess_local_subnet_format(self):
        subnet = DiscoveryAgent._guess_local_subnet()
        parts = subnet.split(".")
        assert len(parts) == 4
        assert "/24" in subnet


# ─────────────────────────────────────────────────────────────────────────────
# Predictive Maintenance Agent
# ─────────────────────────────────────────────────────────────────────────────
from agents.predictive_agent import (
    PredictiveMaintenanceAgent, DeviceHealthRecord, _ewma, _trend_slope, _logistic
)


class TestMathHelpers:
    def test_ewma_single_value(self):
        assert _ewma([42.0]) == 42.0

    def test_ewma_converges(self):
        result = _ewma([100.0] * 50, alpha=0.3)
        assert abs(result - 100.0) < 1.0

    def test_trend_slope_ascending(self):
        slope = _trend_slope([1.0, 2.0, 3.0, 4.0, 5.0])
        assert slope > 0

    def test_trend_slope_descending(self):
        slope = _trend_slope([5.0, 4.0, 3.0, 2.0, 1.0])
        assert slope < 0

    def test_trend_slope_flat(self):
        slope = _trend_slope([5.0, 5.0, 5.0, 5.0])
        assert abs(slope) < 1e-9

    def test_logistic_centre_is_half(self):
        assert abs(_logistic(0.0) - 0.5) < 1e-9

    def test_logistic_large_positive(self):
        assert _logistic(100) > 0.99

    def test_logistic_large_negative(self):
        assert _logistic(-100) < 0.01


class TestDeviceHealthRecord:
    def test_record_stores_rssi(self):
        rec = DeviceHealthRecord("dev-1")
        rec.record({"rssi": -65, "free_heap_bytes": 200_000, "uptime_sec": 100})
        assert list(rec.rssi_history) == [-65]

    def test_record_window_bounded(self):
        rec = DeviceHealthRecord("dev-1")
        for i in range(150):
            rec.record({"rssi": -60.0})
        assert len(rec.rssi_history) == rec.WINDOW


class TestPredictiveMaintenanceAgent:
    @pytest.fixture
    def agent(self):
        return PredictiveMaintenanceAgent()

    def _make_device(self, device_id="dev-test"):
        from orchestrator.device import ESP32Device
        dev = ESP32Device(device_id=device_id, name=device_id, ip_address="127.0.0.1")
        return dev

    @pytest.mark.asyncio
    async def test_ingest_creates_record(self, agent):
        dev = self._make_device()
        result = await agent._execute(
            "ingest_telemetry",
            {"telemetry": {"rssi": -65, "free_heap_bytes": 200_000, "uptime_sec": 10}},
            dev,
        )
        assert result["ingested"] is True
        assert result["samples"] == 1

    @pytest.mark.asyncio
    async def test_score_no_data(self, agent):
        dev = self._make_device("no-data")
        result = await agent._execute("score_health", {}, dev)
        assert result["health_score"] is None
        assert result["reason"] == "no_data"

    @pytest.mark.asyncio
    async def test_score_after_ingest(self, agent):
        dev = self._make_device("scored")
        for _ in range(10):
            await agent._execute(
                "ingest_telemetry",
                {"telemetry": {"rssi": -65, "free_heap_bytes": 200_000, "uptime_sec": 10}},
                dev,
            )
        result = await agent._execute("score_health", {}, dev)
        assert 0 <= result["health_score"] <= 100

    @pytest.mark.asyncio
    async def test_predict_insufficient_data(self, agent):
        dev = self._make_device("pred-no-data")
        result = await agent._execute("predict_failure", {}, dev)
        assert result["prediction"] == "insufficient_data"

    @pytest.mark.asyncio
    async def test_predict_declining_health(self, agent):
        dev = self._make_device("pred-declining")
        rec = agent._records.setdefault(dev.device_id, DeviceHealthRecord(dev.device_id))
        for i in range(20):
            rec.health_history.append(90.0 - i * 3)
        result = await agent._execute("predict_failure", {}, dev)
        assert result.get("health_slope", 0) < 0

    @pytest.mark.asyncio
    async def test_predict_good_health(self, agent):
        dev = self._make_device("pred-good")
        rec = agent._records.setdefault(dev.device_id, DeviceHealthRecord(dev.device_id))
        for i in range(20):
            rec.health_history.append(80.0 + i * 0.1)
        result = await agent._execute("predict_failure", {}, dev)
        assert result["failure_risk"] == "low"

    @pytest.mark.asyncio
    async def test_maintenance_schedule_empty(self, agent):
        result = await agent._execute("maintenance_schedule", {}, None)
        assert "schedule" in result
        assert isinstance(result["schedule"], list)

    @pytest.mark.asyncio
    async def test_fleet_health_report(self, agent):
        dev = self._make_device("fleet-dev")
        rec = agent._records.setdefault(dev.device_id, DeviceHealthRecord(dev.device_id))
        rec.health_history.append(75.0)
        result = await agent._execute("fleet_health_report", {}, None)
        assert result["total_devices"] >= 1
        assert "fleet_health_avg" in result

    @pytest.mark.asyncio
    async def test_anomaly_score_insufficient(self, agent):
        dev = self._make_device("anom-new")
        result = await agent._execute("anomaly_score", {}, dev)
        assert result["reason"] == "insufficient_data"

    @pytest.mark.asyncio
    async def test_anomaly_score_stable(self, agent):
        dev = self._make_device("anom-stable")
        rec = agent._records.setdefault(dev.device_id, DeviceHealthRecord(dev.device_id))
        for _ in range(20):
            rec.rssi_history.append(-65.0)
        result = await agent._execute("anomaly_score", {}, dev)
        assert result["anomaly_score"] < 0.1  # minimal deviation

    @pytest.mark.asyncio
    async def test_anomaly_score_noisy(self, agent):
        dev = self._make_device("anom-noisy")
        rec = agent._records.setdefault(dev.device_id, DeviceHealthRecord(dev.device_id))
        import random
        for _ in range(20):
            rec.rssi_history.append(-65 + random.uniform(-25, 25))
        result = await agent._execute("anomaly_score", {}, dev)
        assert 0.0 <= result["anomaly_score"] <= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Device Simulator
# ─────────────────────────────────────────────────────────────────────────────
from orchestrator.simulator import SimulatedESP32, SimulatorFleet


class TestSimulatedESP32:
    def test_handle_get_status(self):
        sim = SimulatedESP32("sim-1", "TestSim", port=19100)
        resp = sim.handle_command("get_status", {})
        assert resp["status"] == "ok"
        assert "firmware_version" in resp

    def test_handle_set_frequency(self):
        sim = SimulatedESP32("sim-1", "TestSim", port=19101)
        resp = sim.handle_command("set_frequency", {"frequency_hz": 2462e6})
        assert resp["status"] == "ok"
        assert sim._state["frequency_hz"] == 2462e6

    def test_handle_get_rssi(self):
        sim = SimulatedESP32("sim-1", "TestSim", port=19102)
        resp = sim.handle_command("get_rssi", {})
        assert resp["status"] == "ok"
        assert -120 <= resp["rssi"] <= -30

    def test_handle_set_modulation(self):
        sim = SimulatedESP32("sim-1", "TestSim", port=19103)
        resp = sim.handle_command("set_modulation", {"scheme": "LoRa"})
        assert resp["status"] == "ok"
        assert sim._state["modulation"] == "LoRa"

    def test_handle_gps(self):
        sim = SimulatedESP32("sim-1", "TestSim", port=19104)
        resp = sim.handle_command("get_gps", {})
        assert resp["status"] == "ok"
        assert "latitude" in resp

    def test_handle_wifi_scan(self):
        sim = SimulatedESP32("sim-1", "TestSim", port=19105)
        resp = sim.handle_command("wifi_scan", {})
        assert resp["status"] == "ok"
        assert len(resp["networks"]) >= 1

    def test_handle_diagnostics(self):
        sim = SimulatedESP32("sim-1", "TestSim", port=19106)
        resp = sim.handle_command("diagnostics", {})
        assert "uptime_sec" in resp

    def test_handle_ota_update(self):
        sim = SimulatedESP32("sim-1", "TestSim", port=19107)
        resp = sim.handle_command("ota_update", {"url": "http://server/fw.bin"})
        assert resp["status"] == "ok"
        assert sim._state["firmware_version"] == "sim-2.0.0"

    def test_fault_injection_error(self):
        sim = SimulatedESP32("sim-1", "TestSim", port=19108)
        sim.inject_fault("error_response")
        resp = sim.handle_command("get_status", {})
        assert resp["status"] == "error"

    def test_fault_clear(self):
        sim = SimulatedESP32("sim-1", "TestSim", port=19109)
        sim.inject_fault("error_response")
        sim.clear_fault()
        resp = sim.handle_command("get_status", {})
        assert resp["status"] == "ok"

    def test_noisy_scenario_higher_variance(self):
        sim_normal = SimulatedESP32("sim-n", "N", port=19110, scenario="normal")
        sim_noisy  = SimulatedESP32("sim-x", "X", port=19111, scenario="noisy")
        n_rssi = [sim_normal._simulate_rssi() for _ in range(100)]
        x_rssi = [sim_noisy._simulate_rssi()  for _ in range(100)]
        # Noisy scenario should average lower
        assert sum(x_rssi)/len(x_rssi) < sum(n_rssi)/len(n_rssi)

    def test_gps_path_circles(self):
        path = SimulatedESP32._default_path()
        assert len(path) == 36
        # All points within 0.01 degree of centre
        for lat, lon in path:
            assert abs(lat - 37.7749) < 0.01

    def test_simulator_fleet(self):
        fleet = SimulatorFleet()
        fleet.add("d1", "Dev1", 19120)
        fleet.add("d2", "Dev2", 19121)
        assert len(fleet.get_all_devices()) == 2
        fleet.inject_fault("d1", "error_response")
        assert fleet.get("d1")._fault == "error_response"


# ─────────────────────────────────────────────────────────────────────────────
# LLM Client
# ─────────────────────────────────────────────────────────────────────────────
from ai.llm_client import LLMClient, ConversationMemory, Message


class TestConversationMemory:
    def test_add_and_retrieve(self):
        mem = ConversationMemory(max_messages=10)
        mem.add("system", "You are helpful.")
        mem.add("user", "Hello")
        mem.add("assistant", "Hi!")
        msgs = mem.to_api_list()
        assert len(msgs) == 3
        assert msgs[0]["role"] == "system"

    def test_rolling_window(self):
        mem = ConversationMemory(max_messages=5)
        mem.add("system", "sys")
        for i in range(20):
            mem.add("user", f"msg {i}")
        msgs = mem.to_api_list()
        assert len(msgs) <= 5  # bounded

    def test_clear_keeps_system(self):
        mem = ConversationMemory()
        mem.add("system", "System prompt")
        mem.add("user", "Hello")
        mem.clear()
        msgs = mem.to_api_list()
        assert len(msgs) == 1
        assert msgs[0]["role"] == "system"


class TestLLMClientFactory:
    def test_from_config_ollama(self):
        client = LLMClient.from_config({"provider": "ollama"})
        assert client.provider == "ollama"
        assert "11434" in client.base_url

    def test_from_config_openai(self):
        client = LLMClient.from_config({"provider": "openai", "api_key": "test-key"})
        assert client.provider == "openai"
        assert client.base_url == "https://api.openai.com/v1"

    def test_from_config_groq(self):
        client = LLMClient.from_config({"provider": "groq"})
        assert client.base_url == "https://api.groq.com/openai/v1"

    def test_from_config_anthropic(self):
        client = LLMClient.from_config({"provider": "anthropic"})
        assert client.provider == "anthropic"

    def test_from_config_unknown_provider(self):
        client = LLMClient.from_config({"provider": "unknown-llm", "base_url": "http://x"})
        assert client.provider == "unknown-llm"


class TestLLMClientFallback:
    """Test that the client gracefully falls back when the LLM is unavailable."""

    @pytest.mark.asyncio
    async def test_chat_uses_fallback_on_connection_error(self):
        client = LLMClient(base_url="http://localhost:1")  # unreachable port
        result = await client.chat("What is the best LoRa SF for range?")
        assert result["provider"] in ("fallback", "ollama")
        assert "response" in result

    @pytest.mark.asyncio
    async def test_generate_firmware_fallback(self):
        client = LLMClient(base_url="http://localhost:1")
        result = await client.generate_firmware(
            "Temperature sensor with MQTT", features=["wifi", "mqtt"]
        )
        assert "response" in result

    @pytest.mark.asyncio
    async def test_diagnose_fallback(self):
        client = LLMClient(base_url="http://localhost:1")
        result = await client.diagnose({"rssi": -90, "free_heap_bytes": 5000})
        assert "response" in result

    @pytest.mark.asyncio
    async def test_recommend_rf_config_fallback(self):
        client = LLMClient(base_url="http://localhost:1")
        result = await client.recommend_rf_config("long-range agricultural sensor")
        assert "response" in result

    def test_get_history(self):
        client = LLMClient()
        history = client.get_history()
        assert history[0]["role"] == "system"

    def test_reset_memory(self):
        client = LLMClient()
        client._memory.add("user", "test")
        client.reset_memory()
        assert len(client.get_history()) == 1  # only system prompt remains
