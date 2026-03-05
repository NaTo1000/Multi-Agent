"""
Trim Orchestrator — stacks agents by strength, applies multipliers,
and dynamically switches between parallel and series execution.

The "trim" system:
1. Assess each agent's strength (success rate, speed, reliability)
2. Stack agents in ranked order (strongest first)
3. Apply multiplier weights — stronger agents carry more influence
4. Execute workflows in alternating parallel ↔ series phases
5. Monitor performance continuously and rearrange agent order

This orchestrates multiple AI agents on top of each other, leveraging
their combined capability like a multiplier for the overall system.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .agent import AgentBase, AgentStatus
from .core import Orchestrator

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Enums & data classes
# ------------------------------------------------------------------

class WorkflowMode(Enum):
    """Current execution mode within the trim workflow."""
    PARALLEL = "parallel"
    SERIES = "series"


@dataclass
class AgentStrength:
    """Computed strength profile for a single agent."""
    agent_id: str
    agent_type: str
    score: float = 0.0                # composite 0–100
    success_rate: float = 1.0         # 0.0–1.0
    avg_execution_ms: float = 0.0     # average task duration
    tasks_completed: int = 0
    tasks_failed: int = 0
    multiplier: float = 1.0           # derived from score
    rank: int = 0                     # 1 = strongest
    last_assessed: str = ""

    def total_tasks(self) -> int:
        return self.tasks_completed + self.tasks_failed


@dataclass
class TrimCycleResult:
    """Outcome of a single trim workflow cycle."""
    cycle_id: int
    phases: List[Dict[str, Any]] = field(default_factory=list)
    agent_order: List[str] = field(default_factory=list)
    mode_sequence: List[str] = field(default_factory=list)
    total_duration_ms: float = 0.0
    timestamp: str = ""


# ------------------------------------------------------------------
# TrimOrchestrator
# ------------------------------------------------------------------

class TrimOrchestrator:
    """
    Trim layer that sits on top of the base :class:`Orchestrator`.

    It ranks every registered agent by a composite *strength score*,
    stacks them in order, and dispatches a workflow that alternates
    between parallel and series phases — re-ordering agents between
    phases based on live performance feedback.

    Usage::

        trim = TrimOrchestrator(orchestrator)
        await trim.start_monitoring()
        result = await trim.run_trim_cycle(task, params)
        await trim.stop_monitoring()
    """

    # Weights for the composite strength score
    _W_SUCCESS = 50.0
    _W_SPEED = 30.0
    _W_VOLUME = 20.0

    # Monitoring defaults
    _DEFAULT_MONITOR_INTERVAL = 5  # seconds

    def __init__(
        self,
        orchestrator: Orchestrator,
        *,
        monitor_interval: int = _DEFAULT_MONITOR_INTERVAL,
    ):
        self._orchestrator = orchestrator
        self._strengths: Dict[str, AgentStrength] = {}
        self._current_mode = WorkflowMode.PARALLEL
        self._cycle_count = 0
        self._monitor_task: Optional[asyncio.Task] = None
        self._monitor_interval = monitor_interval
        self._monitoring = False
        self._cycle_history: List[TrimCycleResult] = []
        self._execution_times: Dict[str, List[float]] = {}
        logger.info("TrimOrchestrator created (monitor_interval=%ds)", monitor_interval)

    # ------------------------------------------------------------------
    # Strength assessment
    # ------------------------------------------------------------------

    def assess_strengths(self) -> List[AgentStrength]:
        """
        Evaluate every registered agent and return a ranked list of
        :class:`AgentStrength` profiles.

        The composite score is::

            score = W_SUCCESS × success_rate
                  + W_SPEED   × speed_factor    (faster = higher)
                  + W_VOLUME  × volume_factor   (more tasks = higher)

        The *multiplier* is then ``score / 50`` so that an average
        agent contributes 1× and the best contribute ~2×.
        """
        agents = self._orchestrator.list_agents()
        if not agents:
            return []

        now = datetime.now(timezone.utc).isoformat()
        profiles: List[AgentStrength] = []

        # Gather raw metrics for normalisation
        max_completed = max(
            (a.get_metrics()["tasks_completed"] for a in agents), default=1
        ) or 1

        for agent in agents:
            metrics = agent.get_metrics()
            completed = metrics["tasks_completed"]
            failed = metrics["tasks_failed"]
            total = completed + failed

            success_rate = completed / total if total > 0 else 1.0

            # Estimate average execution speed from metrics
            last_task_at = metrics.get("last_task_at")
            avg_ms = self._estimate_avg_ms(agent)

            speed_factor = 1.0 / (1.0 + avg_ms / 1000.0)  # faster → higher
            volume_factor = completed / max_completed if max_completed else 0.0

            score = (
                self._W_SUCCESS * success_rate
                + self._W_SPEED * speed_factor
                + self._W_VOLUME * volume_factor
            )
            score = max(0.0, min(100.0, score))
            multiplier = max(0.1, score / 50.0)

            profile = AgentStrength(
                agent_id=agent.agent_id,
                agent_type=agent.agent_type,
                score=round(score, 2),
                success_rate=round(success_rate, 4),
                avg_execution_ms=round(avg_ms, 2),
                tasks_completed=completed,
                tasks_failed=failed,
                multiplier=round(multiplier, 3),
                last_assessed=now,
            )
            profiles.append(profile)

        # Rank by score descending — strongest first
        profiles.sort(key=lambda p: p.score, reverse=True)
        for rank, profile in enumerate(profiles, start=1):
            profile.rank = rank

        # Cache
        for p in profiles:
            self._strengths[p.agent_id] = p

        logger.info(
            "Assessed %d agent(s): top=%s (score=%.1f, mult=%.2f)",
            len(profiles),
            profiles[0].agent_type if profiles else "n/a",
            profiles[0].score if profiles else 0,
            profiles[0].multiplier if profiles else 0,
        )
        return profiles

    def get_strength(self, agent_id: str) -> Optional[AgentStrength]:
        """Return the cached strength profile for an agent."""
        return self._strengths.get(agent_id)

    def get_ranked_agents(self) -> List[AgentBase]:
        """Return agents ordered by current strength (strongest first)."""
        self.assess_strengths()
        ranked_ids = [s.agent_id for s in sorted(
            self._strengths.values(), key=lambda s: s.score, reverse=True
        )]
        agents = []
        for aid in ranked_ids:
            agent = self._orchestrator.get_agent(aid)
            if agent:
                agents.append(agent)
        return agents

    # ------------------------------------------------------------------
    # Trim workflow execution
    # ------------------------------------------------------------------

    async def run_trim_cycle(
        self,
        task: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        device_id: Optional[str] = None,
        num_phases: int = 4,
    ) -> TrimCycleResult:
        """
        Execute a full trim cycle:

        1. Assess agent strengths and rank them.
        2. For each phase, alternate PARALLEL → SERIES → PARALLEL → …
        3. Within each phase, dispatch the task to agents in ranked order.
        4. Re-assess strengths between phases and potentially reorder.

        Returns a :class:`TrimCycleResult` summarising the cycle.
        """
        self._cycle_count += 1
        cycle_id = self._cycle_count
        params = params or {}
        cycle_start = time.monotonic()
        result = TrimCycleResult(
            cycle_id=cycle_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        logger.info("=== Trim cycle %d starting (%d phases) ===", cycle_id, num_phases)

        for phase_idx in range(num_phases):
            # Alternate execution mode each phase
            mode = WorkflowMode.PARALLEL if phase_idx % 2 == 0 else WorkflowMode.SERIES
            self._current_mode = mode
            result.mode_sequence.append(mode.value)

            # Re-rank agents before each phase
            ranked = self.get_ranked_agents()
            agent_order = [a.agent_id for a in ranked]
            result.agent_order = agent_order  # latest order

            logger.info(
                "  Phase %d/%d [%s] — %d agent(s)",
                phase_idx + 1, num_phases, mode.value, len(ranked),
            )

            phase_result = await self._execute_phase(
                mode, ranked, task, params, device_id
            )
            result.phases.append(phase_result)

        result.total_duration_ms = round(
            (time.monotonic() - cycle_start) * 1000, 2
        )

        self._cycle_history.append(result)
        logger.info(
            "=== Trim cycle %d complete (%.1f ms) ===",
            cycle_id, result.total_duration_ms,
        )
        return result

    async def _execute_phase(
        self,
        mode: WorkflowMode,
        agents: List[AgentBase],
        task: str,
        params: Dict[str, Any],
        device_id: Optional[str],
    ) -> Dict[str, Any]:
        """Run a single phase — either PARALLEL or SERIES."""
        phase_start = time.monotonic()
        agent_results: List[Dict[str, Any]] = []

        if mode == WorkflowMode.PARALLEL:
            agent_results = await self._run_parallel(agents, task, params, device_id)
        else:
            agent_results = await self._run_series(agents, task, params, device_id)

        duration_ms = round((time.monotonic() - phase_start) * 1000, 2)
        return {
            "mode": mode.value,
            "duration_ms": duration_ms,
            "agent_results": agent_results,
        }

    async def _run_parallel(
        self,
        agents: List[AgentBase],
        task: str,
        params: Dict[str, Any],
        device_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Dispatch task to all agents concurrently, weighted by multiplier."""
        async def _dispatch_one(agent: AgentBase) -> Dict[str, Any]:
            strength = self._strengths.get(agent.agent_id)
            multiplier = strength.multiplier if strength else 1.0
            weighted_params = {**params, "_trim_multiplier": multiplier}
            start = time.monotonic()
            try:
                task_id = await self._orchestrator.dispatch_task(
                    agent.agent_id, task, weighted_params, device_id
                )
                elapsed = round((time.monotonic() - start) * 1000, 2)
                self._record_execution(agent.agent_id, elapsed)
                return {
                    "agent_id": agent.agent_id,
                    "agent_type": agent.agent_type,
                    "task_id": task_id,
                    "multiplier": multiplier,
                    "duration_ms": elapsed,
                    "success": True,
                }
            except Exception as exc:
                elapsed = round((time.monotonic() - start) * 1000, 2)
                self._record_execution(agent.agent_id, elapsed, failed=True)
                logger.warning(
                    "Parallel dispatch failed for %s: %s", agent.agent_type, exc
                )
                return {
                    "agent_id": agent.agent_id,
                    "agent_type": agent.agent_type,
                    "multiplier": multiplier,
                    "duration_ms": elapsed,
                    "success": False,
                    "error": str(exc),
                }

        results = await asyncio.gather(
            *[_dispatch_one(a) for a in agents],
            return_exceptions=False,
        )
        return list(results)

    async def _run_series(
        self,
        agents: List[AgentBase],
        task: str,
        params: Dict[str, Any],
        device_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Dispatch task to agents one-by-one in ranked order."""
        results: List[Dict[str, Any]] = []
        for agent in agents:
            strength = self._strengths.get(agent.agent_id)
            multiplier = strength.multiplier if strength else 1.0
            weighted_params = {**params, "_trim_multiplier": multiplier}
            start = time.monotonic()
            try:
                task_id = await self._orchestrator.dispatch_task(
                    agent.agent_id, task, weighted_params, device_id
                )
                elapsed = round((time.monotonic() - start) * 1000, 2)
                self._record_execution(agent.agent_id, elapsed)
                results.append({
                    "agent_id": agent.agent_id,
                    "agent_type": agent.agent_type,
                    "task_id": task_id,
                    "multiplier": multiplier,
                    "duration_ms": elapsed,
                    "success": True,
                })
            except Exception as exc:
                elapsed = round((time.monotonic() - start) * 1000, 2)
                self._record_execution(agent.agent_id, elapsed, failed=True)
                logger.warning(
                    "Series dispatch failed for %s: %s", agent.agent_type, exc
                )
                results.append({
                    "agent_id": agent.agent_id,
                    "agent_type": agent.agent_type,
                    "multiplier": multiplier,
                    "duration_ms": elapsed,
                    "success": False,
                    "error": str(exc),
                })
        return results

    # ------------------------------------------------------------------
    # Monitoring loop
    # ------------------------------------------------------------------

    async def start_monitoring(self) -> None:
        """Begin background monitoring that reassesses agent strengths."""
        if self._monitoring:
            return
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Trim monitoring started (interval=%ds)", self._monitor_interval)

    async def stop_monitoring(self) -> None:
        """Stop the background monitoring loop."""
        if not self._monitoring:
            return
        self._monitoring = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Trim monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Periodically re-assess strengths and log rank changes."""
        prev_order: List[str] = []
        while self._monitoring:
            await asyncio.sleep(self._monitor_interval)
            ranked = self.assess_strengths()
            new_order = [s.agent_id for s in ranked]
            if prev_order and new_order != prev_order:
                logger.info(
                    "Trim monitor: agent order changed — reranked %d agent(s)",
                    len(ranked),
                )
                self._orchestrator._emit_event("trim_reranked", {
                    "previous_order": prev_order,
                    "new_order": new_order,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            prev_order = new_order

    # ------------------------------------------------------------------
    # Execution tracking & helpers
    # ------------------------------------------------------------------

    def _record_execution(
        self, agent_id: str, duration_ms: float, *, failed: bool = False
    ) -> None:
        """Record an execution time for speed estimation."""
        times = self._execution_times.setdefault(agent_id, [])
        times.append(duration_ms)
        # Keep a bounded window
        if len(times) > 100:
            times.pop(0)

    def _estimate_avg_ms(self, agent: AgentBase) -> float:
        """Estimate average execution time in milliseconds."""
        times = self._execution_times.get(agent.agent_id, [])
        if times:
            return sum(times) / len(times)
        return 0.0

    # ------------------------------------------------------------------
    # Status / introspection
    # ------------------------------------------------------------------

    @property
    def current_mode(self) -> WorkflowMode:
        return self._current_mode

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def monitoring(self) -> bool:
        return self._monitoring

    def get_status(self) -> Dict[str, Any]:
        """Return a snapshot of the trim orchestrator's state."""
        ranked = sorted(
            self._strengths.values(), key=lambda s: s.score, reverse=True
        )
        return {
            "monitoring": self._monitoring,
            "current_mode": self._current_mode.value,
            "cycle_count": self._cycle_count,
            "agent_rankings": [
                {
                    "rank": s.rank,
                    "agent_id": s.agent_id,
                    "agent_type": s.agent_type,
                    "score": s.score,
                    "multiplier": s.multiplier,
                    "success_rate": s.success_rate,
                    "tasks_completed": s.tasks_completed,
                }
                for s in ranked
            ],
            "cycle_history_count": len(self._cycle_history),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_cycle_history(self) -> List[TrimCycleResult]:
        """Return the list of completed trim cycle results."""
        return list(self._cycle_history)
