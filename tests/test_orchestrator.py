"""
Tests for the core Orchestrator.
"""

import asyncio
import pytest

from orchestrator import Orchestrator
from orchestrator.device import ESP32Device, DeviceCapability, DeviceStatus
from agents import FrequencyAgent, ModulationAgent, FirmwareAgent, AIAgent, CommsAgent


@pytest.fixture
def orchestrator():
    return Orchestrator({"health_check_interval": 999})


@pytest.fixture
def device():
    d = ESP32Device(
        device_id="test-001",
        name="TestDevice",
        ip_address="127.0.0.1",
        capabilities=[DeviceCapability.WIFI, DeviceCapability.BLE],
    )
    d.status = DeviceStatus.ONLINE
    return d


@pytest.fixture
def all_agents():
    return [
        FrequencyAgent(),
        ModulationAgent(),
        FirmwareAgent(),
        CommsAgent(),
        AIAgent(),
    ]


# ------------------------------------------------------------------
# Device registration
# ------------------------------------------------------------------

def test_register_device(orchestrator, device):
    device_id = orchestrator.register_device(device)
    assert device_id == "test-001"
    assert orchestrator.get_device(device_id) is device


def test_register_duplicate_device(orchestrator, device):
    orchestrator.register_device(device)
    orchestrator.register_device(device)  # should not raise
    assert len(orchestrator.list_devices()) == 1


def test_unregister_device(orchestrator, device):
    orchestrator.register_device(device)
    assert orchestrator.unregister_device("test-001")
    assert orchestrator.get_device("test-001") is None


def test_unregister_nonexistent_device(orchestrator):
    assert not orchestrator.unregister_device("nonexistent")


def test_get_online_devices(orchestrator, device):
    orchestrator.register_device(device)
    online = orchestrator.get_online_devices()
    assert device in online

    device.status = DeviceStatus.OFFLINE
    assert device not in orchestrator.get_online_devices()


# ------------------------------------------------------------------
# Agent registration
# ------------------------------------------------------------------

def test_register_agent(orchestrator):
    agent = FrequencyAgent()
    orchestrator.register_agent(agent)
    assert orchestrator.get_agent(agent.agent_id) is agent


def test_register_multiple_agents(orchestrator, all_agents):
    for agent in all_agents:
        orchestrator.register_agent(agent)
    assert len(orchestrator.list_agents()) == len(all_agents)


def test_get_agents_by_type(orchestrator):
    a1 = FrequencyAgent()
    a2 = FrequencyAgent()
    mod = ModulationAgent()
    orchestrator.register_agent(a1)
    orchestrator.register_agent(a2)
    orchestrator.register_agent(mod)
    freq = orchestrator.get_agents_by_type("frequency_agent")
    assert len(freq) == 2
    assert len(orchestrator.get_agents_by_type("modulation_agent")) == 1


# ------------------------------------------------------------------
# Event system
# ------------------------------------------------------------------

def test_event_listener(orchestrator, device):
    received = []
    orchestrator.on("device_registered", lambda d: received.append(d))
    orchestrator.register_device(device)
    assert len(received) == 1
    assert received[0]["device_id"] == "test-001"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

def test_get_status_structure(orchestrator, device, all_agents):
    orchestrator.register_device(device)
    for a in all_agents:
        orchestrator.register_agent(a)
    status = orchestrator.get_status()
    assert "running" in status
    assert "agents" in status
    assert "devices" in status
    assert len(status["devices"]) == 1
    assert len(status["agents"]) == len(all_agents)


# ------------------------------------------------------------------
# Async lifecycle
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_stop(orchestrator, all_agents):
    for a in all_agents:
        orchestrator.register_agent(a)
    await orchestrator.start()
    assert orchestrator._running
    await orchestrator.stop()
    assert not orchestrator._running


# ------------------------------------------------------------------
# Task dispatch (uses frequency agent with no real device)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_task_no_device(orchestrator):
    agent = FrequencyAgent()
    orchestrator.register_agent(agent)
    await orchestrator.start()
    task_id = await orchestrator.dispatch_task(
        agent.agent_id, "get_frequency", {}, None
    )
    result = orchestrator.get_task_result(task_id)
    assert result is not None
    assert result["task"] == "get_frequency"
    await orchestrator.stop()


@pytest.mark.asyncio
async def test_dispatch_task_unknown_agent(orchestrator):
    await orchestrator.start()
    with pytest.raises(ValueError):
        await orchestrator.dispatch_task("nonexistent", "scan")
    await orchestrator.stop()
