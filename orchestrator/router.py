"""
Task Router — intelligent agent selection using a weighted multi-criteria
scoring algorithm.

Given a list of candidate agents of the same type, the router computes a
composite score for each agent across three independent criteria:

  availability  — how free is the agent right now?
  success_rate  — historical reliability (completed / total tasks)
  recency       — load-balancing bonus for agents that have been idle longest

Final score = w_avail * availability + w_sr * success_rate + w_rec * recency

All sub-scores are normalised to [0, 1] before weighting so that no single
criterion dominates purely due to scale.
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .agent import AgentBase

logger = logging.getLogger(__name__)


class TaskRouter:
    """
    Selects the optimal agent from a set of candidates using a weighted
    multi-criteria decision analysis (MCDA) approach.

    Weights can be overridden at construction time to tune the trade-off
    between latency (availability), reliability (success_rate), and
    load-balancing (recency).
    """

    DEFAULT_WEIGHTS: Dict[str, float] = {
        "availability": 0.50,   # primary driver: prefer idle agents
        "success_rate": 0.30,   # secondary: prefer historically reliable agents
        "recency": 0.20,        # tertiary: spread load across peers
    }

    # Agent-status → availability score mapping
    _AVAILABILITY: Dict[str, float] = {
        "idle": 1.0,
        "running": 0.5,
        "busy": 0.5,
        "error": 0.0,
        "stopped": 0.0,
    }

    # Seconds after which an idle agent is considered "fully rested"
    _RECENCY_WINDOW_SEC: float = 60.0

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        w = {**self.DEFAULT_WEIGHTS, **(weights or {})}
        total = sum(w.values()) or 1.0
        # Normalise so weights always sum to 1.0
        self._weights: Dict[str, float] = {k: v / total for k, v in w.items()}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def select(self, agents: List["AgentBase"]) -> Optional["AgentBase"]:
        """
        Return the highest-scoring agent from *agents*, or ``None`` if the
        list is empty.

        When two agents share the exact same score the one with the lower
        ``agent_id`` (lexicographic) is preferred for determinism.
        """
        if not agents:
            return None
        if len(agents) == 1:
            return agents[0]

        scored = sorted(
            ((self._score(a), a.agent_id, a) for a in agents),
            key=lambda t: (-t[0], t[1]),  # descending score, tie-break on id
        )
        best_score, _, best_agent = scored[0]
        logger.debug(
            "TaskRouter selected %s (score=%.3f) from %d candidates",
            best_agent.agent_id[:8],
            best_score,
            len(agents),
        )
        return best_agent

    def score(self, agent: "AgentBase") -> float:
        """Return the composite routing score for a single agent (0–1)."""
        return self._score(agent)

    # ------------------------------------------------------------------
    # Scoring sub-components
    # ------------------------------------------------------------------

    def _score(self, agent: "AgentBase") -> float:
        avail = self._availability(agent)
        sr = self._success_rate(agent)
        rec = self._recency(agent)
        w = self._weights
        return w["availability"] * avail + w["success_rate"] * sr + w["recency"] * rec

    def _availability(self, agent: "AgentBase") -> float:
        return self._AVAILABILITY.get(agent.status.value, 0.0)

    @staticmethod
    def _success_rate(agent: "AgentBase") -> float:
        completed: int = agent._metrics.get("tasks_completed", 0)
        failed: int = agent._metrics.get("tasks_failed", 0)
        total = completed + failed
        return completed / total if total > 0 else 1.0  # no history → assume perfect

    def _recency(self, agent: "AgentBase") -> float:
        last_task: Optional[Any] = agent._metrics.get("last_task_at")
        if last_task is None:
            return 1.0  # never used — fully fresh
        try:
            last_dt = datetime.fromisoformat(str(last_task))
            age_sec = (datetime.now(tz=timezone.utc) - last_dt).total_seconds()
            return min(age_sec / self._RECENCY_WINDOW_SEC, 1.0)
        except (ValueError, TypeError):
            return 1.0
