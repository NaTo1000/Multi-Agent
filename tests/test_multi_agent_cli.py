"""
Tests for cli/multi_agent_cli.py
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cli.multi_agent_cli import (
    SKILLS_REGISTRY,
    TaskStatus,
    WorkTask,
    Worker,
    decompose_prompt,
    deliberate,
    MultiAgentSession,
)


# ---------------------------------------------------------------------------
# decompose_prompt
# ---------------------------------------------------------------------------

class TestDecomposePrompt:
    def test_always_has_research(self):
        tasks = decompose_prompt("hello world")
        names = [t.name for t in tasks]
        assert "research" in names

    def test_wifi_keyword(self):
        tasks = decompose_prompt("scan wifi networks")
        names = [t.name for t in tasks]
        assert "wifi_scan" in names

    def test_firmware_keyword(self):
        tasks = decompose_prompt("build firmware image")
        names = [t.name for t in tasks]
        assert "build" in names

    def test_frequency_keyword(self):
        tasks = decompose_prompt("check frequency band")
        names = [t.name for t in tasks]
        assert "get_frequency" in names

    def test_multi_keyword_dedup(self):
        tasks = decompose_prompt("scan wifi and check wifi again")
        names = [t.name for t in tasks]
        # wifi_scan should appear only once
        assert names.count("wifi_scan") == 1

    def test_research_prompt_sets_query_param(self):
        prompt = "what is the best modulation?"
        tasks = decompose_prompt(prompt)
        research = next((t for t in tasks if t.name == "research"), None)
        assert research is not None
        assert research.params.get("query") == prompt

    def test_complex_prompt_multiple_tasks(self):
        tasks = decompose_prompt("optimise frequency and diagnose wifi")
        names = [t.name for t in tasks]
        assert "auto_optimise" in names
        assert "diagnostics" in names

    def test_returns_list_of_work_tasks(self):
        tasks = decompose_prompt("research ESP32 best practices")
        assert all(isinstance(t, WorkTask) for t in tasks)
        assert all(t.task_id for t in tasks)
        assert all(t.status == TaskStatus.PENDING for t in tasks)


# ---------------------------------------------------------------------------
# deliberate
# ---------------------------------------------------------------------------

class TestDeliberate:
    def _make_workers(self):
        return [
            Worker(name="kai9000", skills=["frequency_agent", "modulation_agent"]),
            Worker(name="builtin", skills=["ai_agent", "frequency_agent",
                                           "modulation_agent", "firmware_agent",
                                           "comms_agent"]),
        ]

    def test_all_tasks_get_claimed(self):
        workers = self._make_workers()
        tasks = decompose_prompt("scan wifi and check frequency")
        deliberate(workers, tasks)
        assert all(t.status == TaskStatus.CLAIMED for t in tasks)
        assert all(t.claimed_by for t in tasks)

    def test_skilled_worker_preferred(self):
        workers = self._make_workers()
        tasks = [WorkTask(task_id="1", name="get_frequency",
                          agent_type="frequency_agent",
                          params={}, description="freq")]
        deliberate(workers, tasks)
        # kai9000 has frequency_agent skill and should be preferred
        assert tasks[0].claimed_by == "kai9000"

    def test_fallback_when_no_skilled_worker(self):
        workers = [Worker(name="only", skills=["ai_agent"])]
        tasks = [WorkTask(task_id="x", name="build",
                          agent_type="firmware_agent",
                          params={}, description="fw")]
        deliberate(workers, tasks)
        # Only one worker available; must be assigned to it
        assert tasks[0].claimed_by == "only"

    def test_load_balanced_across_workers(self):
        workers = [
            Worker(name="a", skills=["ai_agent"]),
            Worker(name="b", skills=["ai_agent"]),
        ]
        tasks = [
            WorkTask(task_id=str(i), name="research",
                     agent_type="ai_agent", params={}, description=f"t{i}")
            for i in range(4)
        ]
        deliberate(workers, tasks)
        a_count = sum(1 for t in tasks if t.claimed_by == "a")
        b_count = sum(1 for t in tasks if t.claimed_by == "b")
        # Should be distributed, not all on one worker
        assert a_count == 2
        assert b_count == 2


# ---------------------------------------------------------------------------
# SKILLS_REGISTRY
# ---------------------------------------------------------------------------

class TestSkillsRegistry:
    def test_all_expected_providers_present(self):
        for name in ("watsonx", "kimi", "kai9000", "manus", "builtin"):
            assert name in SKILLS_REGISTRY
            assert isinstance(SKILLS_REGISTRY[name], list)
            assert len(SKILLS_REGISTRY[name]) > 0

    def test_builtin_covers_all_agent_types(self):
        all_types = {"ai_agent", "frequency_agent", "modulation_agent",
                     "firmware_agent", "comms_agent"}
        assert all_types.issubset(set(SKILLS_REGISTRY["builtin"]))


# ---------------------------------------------------------------------------
# MultiAgentSession
# ---------------------------------------------------------------------------

def _mock_orchestrator():
    orch = MagicMock()
    orch.get_agents_by_type.return_value = []       # no real agents → fallback
    orch.get_task_result.return_value = None
    orch.dispatch_task = AsyncMock(return_value="task-id-123")
    orch.start = AsyncMock()
    orch.stop = AsyncMock()
    return orch


class TestMultiAgentSession:
    def _session(self, config=None):
        return MultiAgentSession(_mock_orchestrator(), config or {})

    def test_builtin_worker_always_present(self):
        session = self._session()
        names = [w.name for w in session._workers]
        assert "builtin" in names

    def test_workers_have_skills(self):
        session = self._session()
        for w in session._workers:
            assert len(w.skills) > 0

    @pytest.mark.asyncio
    async def test_process_completes(self):
        session = self._session()
        # Should not raise even with no real AI configured
        await session.process("research best ESP32 frequency")

    @pytest.mark.asyncio
    async def test_work_stealing_all_tasks_done(self):
        """All tasks must reach DONE or FAILED after process() regardless of worker count."""
        session = self._session()
        tasks = decompose_prompt("scan wifi optimise frequency build firmware")
        await session._execute(tasks)
        assert all(t.status in (TaskStatus.DONE, TaskStatus.FAILED) for t in tasks)

    @pytest.mark.asyncio
    async def test_research_fallback_builtin(self):
        session = self._session()
        task = WorkTask(
            task_id="t1", name="research",
            agent_type="ai_agent",
            params={"query": "best modulation"},
            description="research",
        )
        builtin = next(w for w in session._workers if w.name == "builtin")
        result = await session._run_task(task, builtin)
        assert isinstance(result, dict)
        assert "response" in result
        assert "builtin" in result.get("provider", "")

    @pytest.mark.asyncio
    async def test_orchestrator_dispatch_called_when_agent_present(self):
        orch = _mock_orchestrator()
        agent_mock = MagicMock()
        agent_mock.agent_id = "agent-001"
        orch.get_agents_by_type.return_value = [agent_mock]
        orch.get_task_result.return_value = {"result": {"status": "ok"}}

        session = MultiAgentSession(orch, {})
        task = WorkTask(
            task_id="t2", name="wifi_scan",
            agent_type="comms_agent",
            params={}, description="wifi",
        )
        builtin = next(w for w in session._workers if w.name == "builtin")
        result = await session._run_task(task, builtin)
        orch.dispatch_task.assert_awaited_once()
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_worker_stats_tracked(self):
        session = self._session()
        tasks = decompose_prompt("research and diagnose")
        deliberate(session._workers, tasks)
        await session._execute(tasks)
        total = sum(w.tasks_completed + w.tasks_helped for w in session._workers)
        assert total == len(tasks)
