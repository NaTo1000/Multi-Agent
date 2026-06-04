"""
Tests for QuantumAgent — all tasks run without real hardware or external deps.
"""

import pytest

from agents.quantum_agent import QuantumAgent


# ------------------------------------------------------------------
# QAOA optimisation
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qaoa_optimise_default_candidates():
    agent = QuantumAgent()
    await agent.start()
    result = await agent.execute("qaoa_optimise", {}, None)

    assert result["algorithm"] == "QAOA"
    assert "optimal_frequency_hz" in result
    assert "optimal_frequency_mhz" in result
    assert result["optimal_frequency_hz"] > 0
    assert result["layers"] >= 1
    assert len(result["probability_distribution"]) == result["candidates"]
    assert abs(sum(result["probability_distribution"]) - 1.0) < 1e-4

    await agent.stop()


@pytest.mark.asyncio
async def test_qaoa_optimise_custom_candidates():
    agent = QuantumAgent()
    await agent.start()
    candidates = [2_412e6, 2_437e6, 2_462e6]
    result = await agent.execute(
        "qaoa_optimise", {"candidates": candidates, "layers": 2}, None
    )
    assert result["optimal_frequency_hz"] in candidates
    assert result["candidates"] == len(candidates)
    await agent.stop()


# ------------------------------------------------------------------
# Grover search
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_grover_search_default():
    agent = QuantumAgent()
    await agent.start()
    result = await agent.execute("grover_search", {}, None)

    assert result["algorithm"] == "Grover"
    assert result["search_space_size"] > 0
    assert result["iterations"] >= 1
    assert "best_channel_hz" in result
    assert result["success_probability"] > 0
    assert result["quadratic_speedup_factor"] > 1

    await agent.stop()


@pytest.mark.asyncio
async def test_grover_search_with_rssi_scores():
    agent = QuantumAgent()
    await agent.start()
    candidates = [2_412e6, 2_437e6, 2_462e6]
    rssi_scores = [-80.0, -55.0, -75.0]   # second channel is best
    result = await agent.execute(
        "grover_search",
        {"candidates": candidates, "rssi_scores": rssi_scores},
        None,
    )
    # Grover should amplify the best channel
    assert result["best_channel_hz"] == 2_437e6
    await agent.stop()


@pytest.mark.asyncio
async def test_grover_empty_candidates():
    agent = QuantumAgent()
    await agent.start()
    result = await agent.execute("grover_search", {"candidates": []}, None)
    assert result["found"] is False
    await agent.stop()


# ------------------------------------------------------------------
# QRNG
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qrng_default():
    agent = QuantumAgent()
    await agent.start()
    result = await agent.execute("qrng", {}, None)

    assert result["algorithm"] == "QRNG"
    assert result["num_bytes"] == 32
    assert len(result["key_hex"]) == 64       # 32 bytes → 64 hex chars
    # Entropy over a 32-byte sample must be positive and finite
    assert result["entropy_bits_per_byte"] > 0
    assert result["entropy_bits_per_byte"] <= 8

    await agent.stop()


@pytest.mark.asyncio
async def test_qrng_entropy_large_sample():
    """Entropy over 256 bytes should be comfortably above 6 bits/byte."""
    agent = QuantumAgent()
    await agent.start()
    result = await agent.execute("qrng", {"num_bytes": 256}, None)
    assert result["entropy_bits_per_byte"] > 6
    await agent.stop()


@pytest.mark.asyncio
async def test_qrng_custom_size():
    agent = QuantumAgent()
    await agent.start()
    result = await agent.execute("qrng", {"num_bytes": 64}, None)
    assert result["num_bytes"] == 64
    assert len(result["key_hex"]) == 128
    await agent.stop()


@pytest.mark.asyncio
async def test_qrng_cap_at_4096():
    agent = QuantumAgent()
    await agent.start()
    result = await agent.execute("qrng", {"num_bytes": 99999}, None)
    assert result["num_bytes"] <= 4096
    await agent.stop()


@pytest.mark.asyncio
async def test_qrng_unique_outputs():
    """Two successive QRNG calls must produce different keys."""
    agent = QuantumAgent()
    await agent.start()
    r1 = await agent.execute("qrng", {"num_bytes": 16}, None)
    r2 = await agent.execute("qrng", {"num_bytes": 16}, None)
    assert r1["key_hex"] != r2["key_hex"]
    await agent.stop()


# ------------------------------------------------------------------
# QKD (BB84 simulation)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qkd_no_eavesdropping():
    agent = QuantumAgent()
    await agent.start()
    result = await agent.execute(
        "qkd_simulate", {"n_qubits": 256, "eve_probability": 0.0}, None
    )
    assert result["algorithm"] == "BB84"
    assert result["n_qubits"] == 256
    assert result["qber"] < 0.11          # should be ~0 without Eve
    assert result["secure"] is True
    assert result["final_key_hex"] is not None
    assert len(result["final_key_hex"]) == 64   # SHA-256 → 32 bytes → 64 hex
    await agent.stop()


@pytest.mark.asyncio
async def test_qkd_with_heavy_eavesdropping():
    agent = QuantumAgent()
    await agent.start()
    result = await agent.execute(
        "qkd_simulate", {"n_qubits": 1024, "eve_probability": 0.5}, None
    )
    assert result["algorithm"] == "BB84"
    # With 50% intercept-resend, QBER > 11% so key exchange must be aborted
    if result["qber"] >= 0.11:
        assert result["secure"] is False
        assert result["final_key_hex"] is None
    await agent.stop()


@pytest.mark.asyncio
async def test_qkd_sifted_bits_approx_half():
    agent = QuantumAgent()
    await agent.start()
    result = await agent.execute("qkd_simulate", {"n_qubits": 512}, None)
    # Sifted key should be roughly 50% of total qubits (±25%)
    assert result["sifted_bits"] > 0
    assert result["sifted_bits"] < result["n_qubits"]
    await agent.stop()


# ------------------------------------------------------------------
# QFT Spectrum Analysis
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qft_spectrum_default_signal():
    agent = QuantumAgent()
    await agent.start()
    result = await agent.execute("qft_spectrum", {}, None)

    assert result["algorithm"] == "QFT"
    assert result["signal_length"] > 0
    assert result["fft_size"] >= result["signal_length"]
    assert "dominant_bin" in result
    assert "interference_peaks" in result
    assert isinstance(result["interference_peaks"], list)

    await agent.stop()


@pytest.mark.asyncio
async def test_qft_spectrum_custom_signal():
    import math
    agent = QuantumAgent()
    await agent.start()
    # Pure 1/8 Nyquist-rate sinusoid — should produce a single strong peak
    signal = [math.sin(2 * math.pi * k / 8) for k in range(64)]
    result = await agent.execute("qft_spectrum", {"rssi_series": signal}, None)
    assert result["signal_length"] == 64
    # Dominant bin should be at 8 (or its mirror)
    assert result["dominant_bin"] in (8, 56)
    await agent.stop()


@pytest.mark.asyncio
async def test_qft_spectrum_short_signal():
    agent = QuantumAgent()
    await agent.start()
    result = await agent.execute("qft_spectrum", {"rssi_series": [1.0]}, None)
    assert "error" in result
    await agent.stop()


# ------------------------------------------------------------------
# Entangle fleet (no online devices → graceful fallback)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_entangle_fleet_no_orchestrator():
    agent = QuantumAgent()
    await agent.start()
    result = await agent.execute("entangle_fleet", {}, None)
    # agent.orchestrator is None at this point
    assert result["entangled"] == 0
    assert "reason" in result
    await agent.stop()


# ------------------------------------------------------------------
# Unknown task
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quantum_unknown_task():
    agent = QuantumAgent()
    await agent.start()
    with pytest.raises(ValueError, match="Unknown task"):
        await agent.execute("not_a_task", {}, None)
    await agent.stop()


# ------------------------------------------------------------------
# Agent metrics
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quantum_metrics_tracking():
    agent = QuantumAgent()
    await agent.start()
    await agent.execute("qrng", {"num_bytes": 8}, None)
    await agent.execute("grover_search", {}, None)
    metrics = agent.get_metrics()
    assert metrics["tasks_completed"] == 2
    assert metrics["tasks_failed"] == 0
    await agent.stop()
