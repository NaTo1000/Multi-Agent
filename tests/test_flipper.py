"""
Tests for the Flipper Zero module.

All tests run in simulated mode (no real hardware required).
"""

import asyncio
import pytest

from flipper import FlipperAgent, FlipperDevice, SubGHzProtocol, InfraredProtocol, NFCProtocol
from flipper.device import FlipperStatus, SubGHzSignal, NFCCard, FlipperConnectionError
from flipper.protocols import SUBGHZ_PRESETS, IR_PROTOCOLS, BadUSBProtocol


# ===========================================================================
# FlipperDevice (simulated)
# ===========================================================================

@pytest.fixture
def sim_device():
    """A simulated FlipperDevice (port=None)."""
    return FlipperDevice(port=None)


@pytest.mark.asyncio
async def test_device_connect_simulated(sim_device):
    await sim_device.connect()
    assert sim_device.status == FlipperStatus.SIMULATED


@pytest.mark.asyncio
async def test_device_disconnect_simulated(sim_device):
    await sim_device.connect()
    await sim_device.disconnect()
    # After disconnect status goes to DISCONNECTED (simulated has no real port to re-open)
    assert sim_device.status in (FlipperStatus.DISCONNECTED, FlipperStatus.SIMULATED)


@pytest.mark.asyncio
async def test_device_get_info_simulated(sim_device):
    await sim_device.connect()
    info = await sim_device.get_info()
    assert info.hardware_version != ""
    assert info.serial_number == "SIM000001"


@pytest.mark.asyncio
async def test_device_run_help_command(sim_device):
    await sim_device.connect()
    response = await sim_device.run_command("help")
    assert "subghz" in response.lower() or "Available" in response


@pytest.mark.asyncio
async def test_device_run_unknown_command_returns_ok(sim_device):
    await sim_device.connect()
    response = await sim_device.run_command("totally_unknown_command")
    assert "OK" in response


@pytest.mark.asyncio
async def test_device_to_dict(sim_device):
    await sim_device.connect()
    d = sim_device.to_dict()
    assert d["simulated"] is True
    assert d["status"] == FlipperStatus.SIMULATED.value


@pytest.mark.asyncio
async def test_device_context_manager():
    async with FlipperDevice(port=None) as dev:
        assert dev.status == FlipperStatus.SIMULATED
        info = await dev.get_info()
        assert info.serial_number == "SIM000001"


# ===========================================================================
# SubGHzProtocol
# ===========================================================================

@pytest.fixture
async def subghz_proto():
    dev = FlipperDevice(port=None)
    await dev.connect()
    return SubGHzProtocol(dev)


@pytest.mark.asyncio
async def test_subghz_receive_returns_signal(subghz_proto):
    signal = await subghz_proto.receive(frequency_hz=433_920_000)
    assert signal is not None
    assert signal.frequency_hz == 433_920_000


@pytest.mark.asyncio
async def test_subghz_transmit_returns_true(subghz_proto):
    signal = SubGHzSignal(
        frequency_hz=433_920_000,
        modulation="AM270",
        data=bytes([0xAB, 0xCD]),
    )
    ok = await subghz_proto.transmit(signal)
    assert ok is True


def test_subghz_parse_sub_file():
    content = (
        "Filetype: Flipper SubGhz Key File\n"
        "Version: 1\n"
        "Frequency: 433920000\n"
        "Preset: FuriHalSubGhzPresetOok270Async\n"
        "Protocol: CAME\n"
        "Key: AB CD EF\n"
    )
    signal = SubGHzProtocol._parse_sub_file(content)
    assert signal.frequency_hz == 433_920_000
    assert signal.modulation == "CAME"
    assert signal.data == bytes([0xAB, 0xCD, 0xEF])


def test_subghz_to_sub_file_roundtrip():
    signal = SubGHzSignal(
        frequency_hz=868_350_000,
        modulation="FM238",
        data=bytes([0x01, 0x02, 0x03]),
    )
    content = signal.to_sub_file()
    parsed = SubGHzProtocol._parse_sub_file(content)
    assert parsed.frequency_hz == signal.frequency_hz
    assert parsed.modulation == signal.modulation
    assert parsed.data == signal.data


def test_subghz_presets_defined():
    assert "433.92MHz" in SUBGHZ_PRESETS
    assert "868.35MHz" in SUBGHZ_PRESETS
    assert SUBGHZ_PRESETS["433.92MHz"] == 433_920_000


def test_subghz_build_signal():
    proto = SubGHzProtocol(FlipperDevice(port=None))
    signal = proto.build_signal(315_000_000, "NEC", b"\xDE\xAD")
    assert signal.frequency_hz == 315_000_000
    assert signal.modulation == "NEC"
    assert signal.data == b"\xDE\xAD"


# ===========================================================================
# InfraredProtocol
# ===========================================================================

@pytest.fixture
async def ir_proto():
    dev = FlipperDevice(port=None)
    await dev.connect()
    return InfraredProtocol(dev)


@pytest.mark.asyncio
async def test_ir_transmit_nec(ir_proto):
    ok = await ir_proto.transmit("NEC", address=0x0000, command=0x0010)
    assert ok is True


@pytest.mark.asyncio
async def test_ir_transmit_samsung(ir_proto):
    ok = await ir_proto.transmit("Samsung32", address=0x0707, command=0x0200)
    assert ok is True


@pytest.mark.asyncio
async def test_ir_transmit_unknown_protocol_raises(ir_proto):
    with pytest.raises(ValueError, match="Unknown IR protocol"):
        await ir_proto.transmit("XYZ", address=0, command=0)


def test_ir_protocols_set_nonempty():
    assert "NEC" in IR_PROTOCOLS
    assert "RC6" in IR_PROTOCOLS
    assert "RAW" in IR_PROTOCOLS


# ===========================================================================
# NFCProtocol
# ===========================================================================

@pytest.fixture
async def nfc_proto():
    dev = FlipperDevice(port=None)
    await dev.connect()
    return NFCProtocol(dev)


@pytest.mark.asyncio
async def test_nfc_detect_returns_card(nfc_proto):
    card = await nfc_proto.detect()
    assert card is not None
    assert card.uid != ""
    assert card.technology != ""


@pytest.mark.asyncio
async def test_nfc_read_uid(nfc_proto):
    uid = await nfc_proto.read_uid()
    assert uid is not None
    assert len(uid) > 0


@pytest.mark.asyncio
async def test_nfc_emulate(nfc_proto):
    ok = await nfc_proto.emulate("04:AB:CD:EF", "Mifare Classic")
    assert ok is True


# ===========================================================================
# BadUSBProtocol
# ===========================================================================

@pytest.fixture
async def bad_usb_proto():
    dev = FlipperDevice(port=None)
    await dev.connect()
    return BadUSBProtocol(dev)


@pytest.mark.asyncio
async def test_bad_usb_type_string(bad_usb_proto):
    ok = await bad_usb_proto.type_string("hello world")
    assert ok is True


@pytest.mark.asyncio
async def test_bad_usb_send_keys(bad_usb_proto):
    ok = await bad_usb_proto.send_keys("CTRL ALT t")
    assert ok is True


# ===========================================================================
# FlipperAgent (orchestrator-integrated, simulated)
# ===========================================================================

@pytest.fixture
async def flipper_agent():
    agent = FlipperAgent({"port": None})  # simulated
    await agent.start()
    return agent


@pytest.mark.asyncio
async def test_flipper_agent_status(flipper_agent):
    result = await flipper_agent.execute("status", {}, None)
    assert "device" in result
    assert result["device"]["simulated"] is True
    assert "firmware" in result


@pytest.mark.asyncio
async def test_flipper_agent_subghz_receive(flipper_agent):
    result = await flipper_agent.execute(
        "subghz_receive", {"frequency_hz": 433_920_000}, None
    )
    assert result["captured"] is True
    assert result["frequency_hz"] == 433_920_000


@pytest.mark.asyncio
async def test_flipper_agent_subghz_transmit(flipper_agent):
    result = await flipper_agent.execute(
        "subghz_transmit",
        {"frequency_hz": 433_920_000, "modulation": "AM270", "data": [0xAB, 0xCD]},
        None,
    )
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_flipper_agent_nfc_detect(flipper_agent):
    result = await flipper_agent.execute("nfc_detect", {}, None)
    assert result["detected"] is True
    assert "uid" in result


@pytest.mark.asyncio
async def test_flipper_agent_nfc_emulate(flipper_agent):
    result = await flipper_agent.execute(
        "nfc_emulate", {"uid": "04:AB:CD:EF"}, None
    )
    assert result["ok"] is True
    assert result["uid"] == "04:AB:CD:EF"


@pytest.mark.asyncio
async def test_flipper_agent_ir_transmit(flipper_agent):
    result = await flipper_agent.execute(
        "ir_transmit", {"protocol": "NEC", "address": 0, "command": 16}, None
    )
    assert result["ok"] is True
    assert result["protocol"] == "NEC"


@pytest.mark.asyncio
async def test_flipper_agent_bad_usb_type(flipper_agent):
    result = await flipper_agent.execute(
        "bad_usb_type", {"text": "hello"}, None
    )
    assert result["ok"] is True
    assert result["text_length"] == 5


@pytest.mark.asyncio
async def test_flipper_agent_run_command(flipper_agent):
    result = await flipper_agent.execute(
        "run_command", {"command": "help"}, None
    )
    assert "output" in result
    assert result["command"] == "help"


@pytest.mark.asyncio
async def test_flipper_agent_unknown_task_raises(flipper_agent):
    with pytest.raises(ValueError, match="Unknown FlipperAgent task"):
        await flipper_agent.execute("does_not_exist", {}, None)


@pytest.mark.asyncio
async def test_flipper_agent_metrics(flipper_agent):
    await flipper_agent.execute("status", {}, None)
    metrics = flipper_agent.get_metrics()
    assert metrics["tasks_completed"] >= 1
    assert metrics["agent_type"] == "flipper_agent"


# ===========================================================================
# Standalone operation
# ===========================================================================

@pytest.mark.asyncio
async def test_flipper_agent_run_standalone():
    agent = FlipperAgent({"port": None})
    tasks = [
        {"task": "status", "params": {}},
        {"task": "nfc_detect", "params": {}},
        {"task": "subghz_receive", "params": {"frequency_hz": 433_920_000}},
    ]
    results = await agent.run_standalone(tasks)
    assert len(results) == 3
    assert results[0]["task"] == "status"
    assert "device" in results[0]["result"]
    assert results[1]["task"] == "nfc_detect"
    assert results[2]["task"] == "subghz_receive"


@pytest.mark.asyncio
async def test_flipper_agent_standalone_error_captured():
    """Errors in individual tasks are captured, not raised."""
    agent = FlipperAgent({"port": None})
    tasks = [{"task": "nonexistent_task", "params": {}}]
    results = await agent.run_standalone(tasks)
    assert len(results) == 1
    assert "error" in results[0]["result"]


# ===========================================================================
# Orchestrator integration
# ===========================================================================

@pytest.mark.asyncio
async def test_flipper_agent_registered_in_orchestrator():
    from orchestrator import Orchestrator
    orch = Orchestrator()
    agent = FlipperAgent({"port": None})
    orch.register_agent(agent)
    assert orch.get_agent(agent.agent_id) is agent
    assert orch.get_agents_by_type("flipper_agent") == [agent]


@pytest.mark.asyncio
async def test_flipper_agent_dispatch_via_orchestrator():
    from orchestrator import Orchestrator
    orch = Orchestrator()
    agent = FlipperAgent({"port": None})
    orch.register_agent(agent)
    await orch.start()
    task_id = await orch.dispatch_task(agent.agent_id, "status", {})
    result = orch.get_task_result(task_id)
    assert result is not None
    assert result["task"] == "status"
    await orch.stop()
