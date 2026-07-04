"""
Agent Ratings System.

After each task execution, peer agents submit a 0–100 percentage score for
the performing agent.  The system maintains a running weighted average
(tally) for every agent and exposes a competitive leaderboard so agents
can race to stay at the top.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_HISTORY = 500  # rating entries kept per agent


class RatingEntry:
    """A single peer rating submitted after one task."""

    __slots__ = ("agent_id", "rated_by", "task", "score", "comment", "timestamp")

    def __init__(
        self,
        agent_id: str,
        rated_by: str,
        task: str,
        score: float,
        comment: str = "",
    ) -> None:
        if not (0.0 <= score <= 100.0):
            raise ValueError(f"Score must be 0–100, got {score}")
        self.agent_id = agent_id
        self.rated_by = rated_by
        self.task = task
        self.score = round(score, 2)
        self.comment = comment
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "rated_by": self.rated_by,
            "task": self.task,
            "score": self.score,
            "comment": self.comment,
            "timestamp": self.timestamp,
        }


class AgentRatingTally:
    """Running tally of ratings for one agent."""

    def __init__(self, agent_id: str, agent_type: str) -> None:
        self.agent_id = agent_id
        self.agent_type = agent_type
        self._history: List[RatingEntry] = []

    # ------------------------------------------------------------------

    def add(self, entry: RatingEntry) -> None:
        self._history.append(entry)
        if len(self._history) > _MAX_HISTORY:
            self._history.pop(0)

    @property
    def total_ratings(self) -> int:
        return len(self._history)

    @property
    def average_score(self) -> float:
        if not self._history:
            return 0.0
        return round(sum(e.score for e in self._history) / len(self._history), 2)

    @property
    def last_score(self) -> Optional[float]:
        return self._history[-1].score if self._history else None

    @property
    def trend(self) -> str:
        """Compare last 5 ratings to the 5 before that."""
        if len(self._history) < 2:
            return "neutral"
        recent = [e.score for e in self._history[-5:]]
        older = [e.score for e in self._history[-10:-5]] or recent
        delta = sum(recent) / len(recent) - sum(older) / len(older)
        if delta > 2:
            return "up"
        if delta < -2:
            return "down"
        return "neutral"

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._history[-limit:]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "average_score": self.average_score,
            "last_score": self.last_score,
            "total_ratings": self.total_ratings,
            "trend": self.trend,
        }


class RatingSystem:
    """
    Singleton-style ratings registry.

    Usage inside the orchestrator::

        ratings = RatingSystem()

        # After agent X finishes a task, all other agents rate it:
        ratings.submit_peer_ratings(
            performing_agent_id="agent-x",
            performing_agent_type="ai_agent",
            task="auto_optimise",
            peer_agents=[("agent-y", "frequency_agent"), ...],
        )

        leaderboard = ratings.get_leaderboard()
    """

    def __init__(self) -> None:
        self._tallies: Dict[str, AgentRatingTally] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ensure_agent(self, agent_id: str, agent_type: str) -> AgentRatingTally:
        if agent_id not in self._tallies:
            self._tallies[agent_id] = AgentRatingTally(agent_id, agent_type)
        return self._tallies[agent_id]

    def submit_rating(
        self,
        agent_id: str,
        agent_type: str,
        rated_by: str,
        task: str,
        score: float,
        comment: str = "",
    ) -> RatingEntry:
        """Submit one peer rating for *agent_id*."""
        tally = self.ensure_agent(agent_id, agent_type)
        entry = RatingEntry(
            agent_id=agent_id,
            rated_by=rated_by,
            task=task,
            score=score,
            comment=comment,
        )
        tally.add(entry)
        logger.debug(
            "Rating submitted: %s → %s task=%s score=%.1f",
            rated_by, agent_id, task, score,
        )
        return entry

    def submit_peer_ratings(
        self,
        performing_agent_id: str,
        performing_agent_type: str,
        task: str,
        peer_agents: List[Dict[str, str]],
        result: Any = None,
    ) -> List[RatingEntry]:
        """
        Ask each peer agent to rate the *performing* agent.

        Scoring heuristic (peers don't have real subjective opinions, so we
        use a deterministic proxy based on task name and result content):
        - Base score 75
        - +10 if result is a non-empty dict with no "error" key
        - +5  if the task succeeded (result truthy)
        - +10 if result indicates an optimised/tuned outcome
        - −20 if result contains an obvious failure indicator
        """
        entries: List[RatingEntry] = []
        base = _score_result(task, result)

        for peer in peer_agents:
            peer_id = peer.get("agent_id", "unknown")
            peer_type = peer.get("agent_type", "unknown")
            if peer_id == performing_agent_id:
                continue  # agents don't rate themselves

            # Add a small deterministic jitter per peer so scores differ
            jitter = (hash(peer_id + task) % 11) - 5  # −5 … +5
            score = max(0.0, min(100.0, base + jitter))

            comment = _build_comment(peer_type, task, score)
            entry = self.submit_rating(
                agent_id=performing_agent_id,
                agent_type=performing_agent_type,
                rated_by=peer_id,
                task=task,
                score=score,
                comment=comment,
            )
            entries.append(entry)

        return entries

    def get_tally(self, agent_id: str) -> Optional[AgentRatingTally]:
        return self._tallies.get(agent_id)

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Return all agents sorted by average score (highest first)."""
        board = [t.to_dict() for t in self._tallies.values()]
        board.sort(key=lambda x: (-x["average_score"], -x["total_ratings"]))
        for rank, entry in enumerate(board, start=1):
            entry["rank"] = rank
        return board

    def get_agent_history(self, agent_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        tally = self._tallies.get(agent_id)
        return tally.get_history(limit) if tally else []

    def get_stats(self) -> Dict[str, Any]:
        tallies = list(self._tallies.values())
        if not tallies:
            return {"total_agents": 0, "total_ratings": 0, "global_average": 0.0}
        total_ratings = sum(t.total_ratings for t in tallies)
        all_scores = [e.score for t in tallies for e in t._history]
        global_avg = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0
        return {
            "total_agents": len(tallies),
            "total_ratings": total_ratings,
            "global_average": global_avg,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score_result(task: str, result: Any) -> float:
    score = 75.0

    if result is None:
        return score - 15.0

    if isinstance(result, dict):
        if "error" in result or result.get("reason", "").endswith("failed"):
            return score - 20.0
        if result.get("optimised") or result.get("tuned"):
            score += 10.0
        if result.get("interference") is False:
            score += 5.0
        if isinstance(result.get("steps"), list) and len(result["steps"]) > 0:
            score += 5.0
        if "anomalies" in result and len(result["anomalies"]) == 0:
            score += 5.0
    elif result:
        score += 5.0

    return min(score, 100.0)


def _build_comment(peer_type: str, task: str, score: float) -> str:
    if score >= 90:
        return f"{peer_type}: excellent performance on {task}"
    if score >= 75:
        return f"{peer_type}: solid execution of {task}"
    if score >= 60:
        return f"{peer_type}: acceptable result for {task}"
    return f"{peer_type}: suboptimal outcome on {task}"
