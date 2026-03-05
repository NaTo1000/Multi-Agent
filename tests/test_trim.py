"""
Tests for the Trim Orchestrator.

Validates strength assessment, agent stacking/ranking, multiplier
calculation, parallel ↔ series execution, monitoring loop, and
dynamic reordering.
"""

import asyncio
import pytest

from orchestrator import Orchestrator
from orchestrator.trim import (
    TrimOrchestrator,
    WorkflowMode,
    AgentStrength,
    TrimCycleResult,
)
from orchestrator.device import ESP32Device, DeviceCapability, DeviceStatus
from agents import FrequencyAgent, ModulationAgent, FirmwareAgent, AIAgent, CommsAgent


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def orchestrator():
    return Orchestrator({"health_check_interval": 999})


@pytest.fixture
def device():
    d = ESP32Device(
        device_id="trim-001",
        name="TrimDevice",
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


@pytest.fixture
def wired_orchestrator(orchestrator, all_agents):
    """Orchestrator with all agents registered."""
    for a in all_agents:
        orchestrator.register_agent(a)
    return orchestrator


@pytest.fixture
def trim(wired_orchestrator):
    return TrimOrchestrator(wired_orchestrator, monitor_interval=1)


# ------------------------------------------------------------------
# Strength assessment
# ------------------------------------------------------------------

def test_assess_strengths_returns_all_agents(trim, wired_orchestrator):
    profiles = trim.assess_strengths()
    assert len(profiles) == len(wired_orchestrator.list_agents())


def test_assess_strengths_ranked_by_score(trim):
    profiles = trim.assess_strengths()
    scores = [p.score for p in profiles]
    assert scores == sorted(scores, reverse=True)


def test_assess_strengths_rank_numbers(trim):
    profiles = trim.assess_strengths()
    ranks = [p.rank for p in profiles]
    assert ranks == list(range(1, len(profiles) + 1))


def test_assess_strengths_multiplier_positive(trim):
    profiles = trim.assess_strengths()
    for p in profiles:
        assert p.multiplier >= 0.1


def test_assess_strengths_empty_orchestrator():
    orch = Orchestrator({"health_check_interval": 999})
    trim = TrimOrchestrator(orch)
    profiles = trim.assess_strengths()
    assert profiles == []


def test_get_strength_returns_cached(trim):
    profiles = trim.assess_strengths()
    for p in profiles:
        cached = trim.get_strength(p.agent_id)
        assert cached is not None
        assert cached.score == p.score


def test_get_strength_unknown_agent(trim):
    assert trim.get_strength("nonexistent") is None


# ------------------------------------------------------------------
# Agent ranking / stacking
# ------------------------------------------------------------------

def test_get_ranked_agents_returns_all(trim, wired_orchestrator):
    ranked = trim.get_ranked_agents()
    assert len(ranked) == len(wired_orchestrator.list_agents())


def test_get_ranked_agents_order_matches_strength(trim):
    ranked = trim.get_ranked_agents()
    agent_ids = [a.agent_id for a in ranked]
    profiles = sorted(
        [trim.get_strength(aid) for aid in agent_ids if trim.get_strength(aid)],
        key=lambda s: s.score,
        reverse=True,
    )
    assert [a.agent_id for a in ranked] == [p.agent_id for p in profiles]


@pytest.mark.asyncio
async def test_ranking_changes_after_task_execution(trim, wired_orchestrator):
    """After one agent completes tasks, its ranking may change."""
    await wired_orchestrator.start()

    # Get initial order
    initial_ranked = trim.get_ranked_agents()
    initial_ids = [a.agent_id for a in initial_ranked]

    # Execute several tasks on the last-ranked agent to boost its metrics
    last_agent = initial_ranked[-1]
    for _ in range(5):
        try:
            await wired_orchestrator.dispatch_task(
                last_agent.agent_id, "get_frequency", {}, None,
            )
        except (ValueError, Exception):
            pass

    # Re-rank
    new_ranked = trim.get_ranked_agents()
    new_ids = [a.agent_id for a in new_ranked]
    # The rankings should be re-assessed (may or may not change)
    assert len(new_ids) == len(initial_ids)

    await wired_orchestrator.stop()


# ------------------------------------------------------------------
# Trim cycle execution
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trim_cycle_runs(trim, wired_orchestrator):
    await wired_orchestrator.start()
    result = await trim.run_trim_cycle("get_frequency", {}, num_phases=2)
    assert isinstance(result, TrimCycleResult)
    assert result.cycle_id == 1
    assert len(result.phases) == 2
    assert result.total_duration_ms > 0
    await wired_orchestrator.stop()


@pytest.mark.asyncio
async def test_trim_cycle_alternates_modes(trim, wired_orchestrator):
    await wired_orchestrator.start()
    result = await trim.run_trim_cycle("get_frequency", {}, num_phases=4)
    assert result.mode_sequence == ["parallel", "series", "parallel", "series"]
    await wired_orchestrator.stop()


@pytest.mark.asyncio
async def test_trim_cycle_increments_counter(trim, wired_orchestrator):
    await wired_orchestrator.start()
    await trim.run_trim_cycle("get_frequency", {}, num_phases=2)
    assert trim.cycle_count == 1
    await trim.run_trim_cycle("get_frequency", {}, num_phases=2)
    assert trim.cycle_count == 2
    await wired_orchestrator.stop()


@pytest.mark.asyncio
async def test_trim_cycle_contains_agent_results(trim, wired_orchestrator):
    await wired_orchestrator.start()
    result = await trim.run_trim_cycle("get_frequency", {}, num_phases=2)
    for phase in result.phases:
        assert "agent_results" in phase
        assert "mode" in phase
        assert phase["mode"] in ("parallel", "series")
    await wired_orchestrator.stop()


@pytest.mark.asyncio
async def test_trim_cycle_agent_results_have_multiplier(trim, wired_orchestrator):
    await wired_orchestrator.start()
    result = await trim.run_trim_cycle("get_frequency", {}, num_phases=1)
    phase = result.phases[0]
    for ar in phase["agent_results"]:
        assert "multiplier" in ar
        assert ar["multiplier"] >= 0.1
    await wired_orchestrator.stop()


@pytest.mark.asyncio
async def test_trim_cycle_records_history(trim, wired_orchestrator):
    await wired_orchestrator.start()
    await trim.run_trim_cycle("get_frequency", {}, num_phases=2)
    history = trim.get_cycle_history()
    assert len(history) == 1
    assert history[0].cycle_id == 1
    await wired_orchestrator.stop()


# ------------------------------------------------------------------
# Parallel vs series execution
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_phase_dispatches_to_all(trim, wired_orchestrator):
    await wired_orchestrator.start()
    result = await trim.run_trim_cycle("get_frequency", {}, num_phases=1)
    # Phase 0 is parallel
    parallel_phase = result.phases[0]
    assert parallel_phase["mode"] == "parallel"
    # Should have results from all agents (some may fail if task not supported)
    assert len(parallel_phase["agent_results"]) == len(wired_orchestrator.list_agents())
    await wired_orchestrator.stop()


@pytest.mark.asyncio
async def test_series_phase_dispatches_sequentially(trim, wired_orchestrator):
    await wired_orchestrator.start()
    result = await trim.run_trim_cycle("get_frequency", {}, num_phases=2)
    # Phase 1 is series
    series_phase = result.phases[1]
    assert series_phase["mode"] == "series"
    assert len(series_phase["agent_results"]) == len(wired_orchestrator.list_agents())
    await wired_orchestrator.stop()


# ------------------------------------------------------------------
# Monitoring
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_stop_monitoring(trim):
    await trim.start_monitoring()
    assert trim.monitoring is True
    await trim.stop_monitoring()
    assert trim.monitoring is False


@pytest.mark.asyncio
async def test_start_monitoring_idempotent(trim):
    await trim.start_monitoring()
    await trim.start_monitoring()  # should not create a second task
    assert trim.monitoring is True
    await trim.stop_monitoring()


@pytest.mark.asyncio
async def test_stop_monitoring_idempotent(trim):
    await trim.stop_monitoring()  # should not raise
    assert trim.monitoring is False


@pytest.mark.asyncio
async def test_monitoring_reassesses_strengths(trim, wired_orchestrator):
    """Monitoring loop should update strengths over time."""
    await wired_orchestrator.start()
    await trim.start_monitoring()
    # Let the monitor run at least one cycle
    await asyncio.sleep(1.5)
    assert len(trim._strengths) > 0
    await trim.stop_monitoring()
    await wired_orchestrator.stop()


# ------------------------------------------------------------------
# Workflow mode
# ------------------------------------------------------------------

def test_initial_mode_is_parallel(trim):
    assert trim.current_mode == WorkflowMode.PARALLEL


@pytest.mark.asyncio
async def test_mode_switches_during_cycle(trim, wired_orchestrator):
    await wired_orchestrator.start()
    await trim.run_trim_cycle("get_frequency", {}, num_phases=3)
    # After 3 phases (P, S, P) the last mode should be PARALLEL
    assert trim.current_mode == WorkflowMode.PARALLEL
    await wired_orchestrator.stop()


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

def test_get_status_structure(trim):
    trim.assess_strengths()
    status = trim.get_status()
    assert "monitoring" in status
    assert "current_mode" in status
    assert "cycle_count" in status
    assert "agent_rankings" in status
    assert "timestamp" in status


def test_get_status_rankings_sorted(trim):
    trim.assess_strengths()
    status = trim.get_status()
    ranks = [r["rank"] for r in status["agent_rankings"]]
    assert ranks == sorted(ranks)


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trim_cycle_with_failing_tasks(trim, wired_orchestrator):
    """
    When agents can't handle a task (e.g., 'nonexistent'),
    the trim cycle should still complete with error info.
    """
    await wired_orchestrator.start()
    result = await trim.run_trim_cycle("nonexistent_task_xyz", {}, num_phases=1)
    assert result.cycle_id == 1
    phase = result.phases[0]
    # Some agents should report failure
    failures = [r for r in phase["agent_results"] if not r["success"]]
    assert len(failures) > 0
    for f in failures:
        assert "error" in f
    await wired_orchestrator.stop()
