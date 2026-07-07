"""
Technical Learning Cortex (TLC) — domain knowledge accumulator for the
multi-agent orchestration system.

The TLC observes agent task outcomes and, using lightweight statistical
pattern recognition, derives reusable :class:`KnowledgeEntry` objects that
surface operational insights across sessions.

Architecture
------------
1. :class:`TechnicalObservation`    — one recorded agent task outcome.
2. :class:`KnowledgeEntry`          — a derived insight with confidence score.
3. :class:`TechnicalKnowledgeStore` — in-memory repository for observations
                                      and derived knowledge.
4. :class:`PatternRecognizer`       — analyses observation windows to produce
                                      :class:`KnowledgeEntry` objects.
5. :class:`TLCModule`               — high-level coordinator: record → analyse
                                      → enrich context.

Design principles
-----------------
* All signals are derived exclusively from recorded task outcomes.
  No simulated, fabricated, or hallucinated data is introduced.
* Confidence scores use elementary statistics: consistency ratio ×
  evidence-saturation factor (saturates at 1.0 after ``_MIN_EVIDENCE``
  observations).
* The module is stateless in itself — all persistent state lives in
  :class:`TechnicalKnowledgeStore`.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum observations before the evidence factor saturates at 1.0.
_MIN_EVIDENCE: int = 5

# Failure / success rate thresholds for pattern recognition.
_FAILURE_THRESHOLD: float = 0.6   # ≥ 60 % failures  → low-reliability entry
_SUCCESS_THRESHOLD: float = 0.8   # ≥ 80 % successes → high-reliability entry

# Parameter keys to track for value-level preference analysis.
_TRACKED_PARAMS: Tuple[str, ...] = ("band", "scheme", "template")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TechnicalObservation:
    """
    A single recorded agent task outcome.

    Attributes:
        domain:    Functional domain (e.g. ``"frequency"``, ``"firmware"``).
        task:      Task name within the domain (e.g. ``"scan"``, ``"build"``).
        params:    Parameters supplied to the task.
        outcome:   Result dict returned by the agent.
        success:   Whether the task completed successfully.
        device_id: Optional target device identifier.
        timestamp: UTC ISO-8601 creation timestamp.
    """

    domain: str
    task: str
    params: Dict[str, Any]
    outcome: Dict[str, Any]
    success: bool
    device_id: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "task": self.task,
            "params": self.params,
            "outcome": self.outcome,
            "success": self.success,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
        }


@dataclass
class KnowledgeEntry:
    """
    A derived technical insight with an evidence-weighted confidence score.

    Attributes:
        concept:        Human-readable description of the insight.
        domain:         Functional domain this insight belongs to.
        confidence:     0.0–1.0; product of consistency ratio and evidence
                        saturation (maximum after ``_MIN_EVIDENCE`` observations).
        evidence_count: Number of observations supporting this entry.
        tags:           Searchable labels (domain, task, device, pattern type).
        first_seen:     UTC ISO-8601 timestamp of first supporting observation.
        last_seen:      UTC ISO-8601 timestamp of most recent update.
    """

    concept: str
    domain: str
    confidence: float
    evidence_count: int
    tags: List[str] = field(default_factory=list)
    first_seen: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_seen: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept": self.concept,
            "domain": self.domain,
            "confidence": round(self.confidence, 3),
            "evidence_count": self.evidence_count,
            "tags": self.tags,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
        }


# ---------------------------------------------------------------------------
# Confidence helper
# ---------------------------------------------------------------------------


def _confidence(consistent: int, total: int) -> float:
    """
    Compute a confidence score in [0, 1].

    ``consistent`` — observations matching the pattern direction.
    ``total``      — all observations in the analysis window.

    score = (consistent / total) × min(1.0, total / _MIN_EVIDENCE)

    The evidence factor prevents premature high-confidence claims on small
    samples.  At ``_MIN_EVIDENCE`` observations the factor saturates to 1.0.
    """
    if total == 0:
        return 0.0
    ratio = consistent / total
    evidence_factor = min(1.0, total / _MIN_EVIDENCE)
    return round(ratio * evidence_factor, 3)


# ---------------------------------------------------------------------------
# TechnicalKnowledgeStore
# ---------------------------------------------------------------------------


class TechnicalKnowledgeStore:
    """
    In-memory repository for :class:`TechnicalObservation` objects and
    derived :class:`KnowledgeEntry` objects.

    Observations are maintained in two look-up indexes:
    * ``_domain_index``  — ``{domain: [observations]}``
    * ``_device_index``  — ``{device_id: [observations]}``

    Knowledge entries are keyed by a deterministic string so they are
    deduplicated and updatable across successive analyses.
    """

    def __init__(self) -> None:
        self._observations: List[TechnicalObservation] = []
        self._domain_index: Dict[str, List[TechnicalObservation]] = defaultdict(list)
        self._device_index: Dict[str, List[TechnicalObservation]] = defaultdict(list)
        self._knowledge: Dict[str, KnowledgeEntry] = {}

    # ------------------------------------------------------------------
    # Observation management
    # ------------------------------------------------------------------

    def add_observation(self, obs: TechnicalObservation) -> None:
        """Append *obs* to all relevant indexes."""
        self._observations.append(obs)
        self._domain_index[obs.domain].append(obs)
        if obs.device_id:
            self._device_index[obs.device_id].append(obs)
        logger.debug(
            "TLC observation | domain=%s task=%s success=%s device=%s",
            obs.domain, obs.task, obs.success, obs.device_id,
        )

    def get_observations(
        self,
        domain: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> List[TechnicalObservation]:
        """
        Return observations filtered by *domain* and/or *device_id*.
        When neither filter is set, all observations are returned.
        """
        if domain and device_id:
            return [
                o for o in self._domain_index.get(domain, [])
                if o.device_id == device_id
            ]
        if domain:
            return list(self._domain_index.get(domain, []))
        if device_id:
            return list(self._device_index.get(device_id, []))
        return list(self._observations)

    @property
    def observation_count(self) -> int:
        """Total number of recorded observations."""
        return len(self._observations)

    # ------------------------------------------------------------------
    # Knowledge management
    # ------------------------------------------------------------------

    def upsert_knowledge(self, key: str, entry: KnowledgeEntry) -> None:
        """Insert or replace the knowledge entry stored under *key*."""
        self._knowledge[key] = entry

    def get_knowledge(
        self,
        domain: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_confidence: float = 0.0,
    ) -> List[KnowledgeEntry]:
        """
        Return knowledge entries matching the optional filters, sorted by
        confidence descending.

        Args:
            domain:         Only entries in this domain (or all if None).
            tags:           Only entries that share at least one of these tags.
            min_confidence: Minimum confidence threshold (inclusive).
        """
        results = list(self._knowledge.values())
        if domain:
            results = [e for e in results if e.domain == domain]
        if tags:
            tag_set = set(tags)
            results = [e for e in results if tag_set.intersection(e.tags)]
        results = [e for e in results if e.confidence >= min_confidence]
        return sorted(results, key=lambda e: e.confidence, reverse=True)

    def get_device_summary(self, device_id: str) -> Dict[str, Any]:
        """
        Return a compact summary of task outcomes for *device_id*.

        Returns a dict with ``observation_count``, ``success_rate``, and
        ``dominant_failing_domain``.  Returns ``None`` for ``success_rate``
        and ``dominant_failing_domain`` when no observations exist.
        """
        obs = self.get_observations(device_id=device_id)
        if not obs:
            return {
                "device_id": device_id,
                "observation_count": 0,
                "success_rate": None,
                "dominant_failing_domain": None,
            }
        total = len(obs)
        successes = sum(1 for o in obs if o.success)
        failures_by_domain: Dict[str, int] = defaultdict(int)
        for o in obs:
            if not o.success:
                failures_by_domain[o.domain] += 1
        dominant_failing = (
            max(failures_by_domain, key=lambda k: failures_by_domain[k])
            if failures_by_domain else None
        )
        return {
            "device_id": device_id,
            "observation_count": total,
            "success_rate": round(successes / total, 3),
            "dominant_failing_domain": dominant_failing,
        }

    @property
    def knowledge_count(self) -> int:
        """Total number of derived knowledge entries."""
        return len(self._knowledge)


# ---------------------------------------------------------------------------
# PatternRecognizer
# ---------------------------------------------------------------------------


class PatternRecognizer:
    """
    Derives :class:`KnowledgeEntry` objects from accumulated
    :class:`TechnicalObservation` data using three pattern types.

    Recognised patterns
    -------------------
    1. **Task reliability** — a ``(domain, task)`` pair that consistently
       fails (rate ≥ ``_FAILURE_THRESHOLD``) or succeeds
       (rate ≥ ``_SUCCESS_THRESHOLD``).
    2. **Device health** — a device with a persistently high failure or
       success rate.
    3. **Parameter preference** — a specific value for a tracked parameter
       key that correlates with task success (≥ 2 supporting observations).
    """

    def analyse(self, store: TechnicalKnowledgeStore) -> None:
        """
        Scan all observations in *store*, derive knowledge entries, and
        write them back via :meth:`TechnicalKnowledgeStore.upsert_knowledge`.
        """
        self._analyse_task_reliability(store)
        self._analyse_device_health(store)
        self._analyse_parameter_preferences(store)

    # ------------------------------------------------------------------
    # Pattern 1: task reliability
    # ------------------------------------------------------------------

    def _analyse_task_reliability(self, store: TechnicalKnowledgeStore) -> None:
        groups: Dict[Tuple[str, str], List[TechnicalObservation]] = defaultdict(list)
        for obs in store.get_observations():
            groups[(obs.domain, obs.task)].append(obs)

        now = datetime.now(timezone.utc).isoformat()
        for (domain, task), obs_list in groups.items():
            total = len(obs_list)
            failures = sum(1 for o in obs_list if not o.success)
            successes = total - failures
            failure_rate = failures / total
            success_rate = successes / total

            if failure_rate >= _FAILURE_THRESHOLD:
                key = f"task_low_reliability:{domain}:{task}"
                conf = _confidence(failures, total)
                entry = KnowledgeEntry(
                    concept=(
                        f"'{task}' in the '{domain}' domain has low reliability "
                        f"({failures}/{total} failures)."
                    ),
                    domain=domain,
                    confidence=conf,
                    evidence_count=total,
                    tags=[domain, task, "low_reliability", "failure"],
                    last_seen=now,
                )
                existing = store._knowledge.get(key)
                if existing:
                    entry.first_seen = existing.first_seen
                store.upsert_knowledge(key, entry)

            elif success_rate >= _SUCCESS_THRESHOLD:
                key = f"task_high_reliability:{domain}:{task}"
                conf = _confidence(successes, total)
                entry = KnowledgeEntry(
                    concept=(
                        f"'{task}' in the '{domain}' domain is reliable "
                        f"({successes}/{total} successes)."
                    ),
                    domain=domain,
                    confidence=conf,
                    evidence_count=total,
                    tags=[domain, task, "high_reliability", "success"],
                    last_seen=now,
                )
                existing = store._knowledge.get(key)
                if existing:
                    entry.first_seen = existing.first_seen
                store.upsert_knowledge(key, entry)

    # ------------------------------------------------------------------
    # Pattern 2: device health
    # ------------------------------------------------------------------

    def _analyse_device_health(self, store: TechnicalKnowledgeStore) -> None:
        device_ids = {
            obs.device_id
            for obs in store.get_observations()
            if obs.device_id
        }
        now = datetime.now(timezone.utc).isoformat()
        for device_id in device_ids:
            obs_list = store.get_observations(device_id=device_id)
            total = len(obs_list)
            failures = sum(1 for o in obs_list if not o.success)
            successes = total - failures
            failure_rate = failures / total

            if failure_rate >= _FAILURE_THRESHOLD:
                key = f"device_health_poor:{device_id}"
                conf = _confidence(failures, total)
                entry = KnowledgeEntry(
                    concept=(
                        f"Device '{device_id}' has poor health "
                        f"({failures}/{total} task failures)."
                    ),
                    domain="device",
                    confidence=conf,
                    evidence_count=total,
                    tags=["device", device_id, "health_poor", "failure"],
                    last_seen=now,
                )
                existing = store._knowledge.get(key)
                if existing:
                    entry.first_seen = existing.first_seen
                store.upsert_knowledge(key, entry)

            elif successes / total >= _SUCCESS_THRESHOLD:
                key = f"device_health_good:{device_id}"
                conf = _confidence(successes, total)
                entry = KnowledgeEntry(
                    concept=(
                        f"Device '{device_id}' is healthy "
                        f"({successes}/{total} task successes)."
                    ),
                    domain="device",
                    confidence=conf,
                    evidence_count=total,
                    tags=["device", device_id, "health_good", "success"],
                    last_seen=now,
                )
                existing = store._knowledge.get(key)
                if existing:
                    entry.first_seen = existing.first_seen
                store.upsert_knowledge(key, entry)

    # ------------------------------------------------------------------
    # Pattern 3: parameter preferences
    # ------------------------------------------------------------------

    def _analyse_parameter_preferences(self, store: TechnicalKnowledgeStore) -> None:
        # Track (domain, task, param_key, param_value) → (success_count, total)
        groups: Dict[Tuple[str, str, str, str], List[bool]] = defaultdict(list)
        for obs in store.get_observations():
            for pkey in _TRACKED_PARAMS:
                pval = obs.params.get(pkey)
                if pval is None:
                    continue
                groups[(obs.domain, obs.task, pkey, str(pval))].append(obs.success)

        now = datetime.now(timezone.utc).isoformat()
        for (domain, task, pkey, pval), outcomes in groups.items():
            total = len(outcomes)
            successes = sum(outcomes)
            if total < 2:
                continue
            if successes / total >= _SUCCESS_THRESHOLD:
                key = f"param_preference:{domain}:{task}:{pkey}:{pval}"
                conf = _confidence(successes, total)
                entry = KnowledgeEntry(
                    concept=(
                        f"Parameter {pkey}={pval!r} for '{task}' in '{domain}' "
                        f"correlates with success ({successes}/{total})."
                    ),
                    domain=domain,
                    confidence=conf,
                    evidence_count=total,
                    tags=[domain, task, f"param:{pkey}", f"value:{pval}", "preference"],
                    last_seen=now,
                )
                existing = store._knowledge.get(key)
                if existing:
                    entry.first_seen = existing.first_seen
                store.upsert_knowledge(key, entry)


# ---------------------------------------------------------------------------
# TLCModule
# ---------------------------------------------------------------------------


class TLCModule:
    """
    Technical Learning Cortex — high-level coordinator.

    Instantiate once and reuse across requests.  All sub-system instances
    are owned by this module.

    Args:
        store:      Optional external :class:`TechnicalKnowledgeStore`.
                    Provide one to share state with other components.
        recognizer: Optional external :class:`PatternRecognizer`.
    """

    def __init__(
        self,
        store: Optional[TechnicalKnowledgeStore] = None,
        recognizer: Optional[PatternRecognizer] = None,
    ) -> None:
        self._store = store or TechnicalKnowledgeStore()
        self._recognizer = recognizer or PatternRecognizer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        domain: str,
        task: str,
        params: Dict[str, Any],
        outcome: Dict[str, Any],
        success: bool,
        device_id: Optional[str] = None,
    ) -> TechnicalObservation:
        """
        Record a technical task outcome and trigger pattern analysis.

        Args:
            domain:    Functional domain (e.g. ``"frequency"``).
            task:      Task identifier (e.g. ``"scan"``).
            params:    Task parameters supplied by the caller.
            outcome:   Task result dict.
            success:   Whether the task succeeded.
            device_id: Optional target device identifier.

        Returns:
            The recorded :class:`TechnicalObservation`.
        """
        obs = TechnicalObservation(
            domain=domain,
            task=task,
            params=params,
            outcome=outcome,
            success=success,
            device_id=device_id,
        )
        self._store.add_observation(obs)
        self._recognizer.analyse(self._store)
        logger.info(
            "TLC recorded | domain=%s task=%s success=%s knowledge_entries=%d",
            domain, task, success, self._store.knowledge_count,
        )
        return obs

    def query(
        self,
        domain: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_confidence: float = 0.0,
    ) -> List[KnowledgeEntry]:
        """
        Query derived knowledge entries.

        Args:
            domain:         Filter by domain (or all if None).
            tags:           Only entries that share at least one tag.
            min_confidence: Minimum confidence threshold.

        Returns:
            :class:`KnowledgeEntry` list sorted by confidence descending.
        """
        return self._store.get_knowledge(
            domain=domain, tags=tags, min_confidence=min_confidence
        )

    def get_context(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Build a structured technical context dict suitable for injection
        into a :class:`~ai.chaimera3sp.CHAiMERA3sp` query.

        Args:
            device_id: When supplied, includes a device-specific summary.

        Returns:
            A serialisable dict with ``technical_context`` containing
            observation count, knowledge count, top insights, and
            optionally a device summary.
        """
        top_knowledge = self._store.get_knowledge(min_confidence=0.3)[:10]
        ctx: Dict[str, Any] = {
            "technical_context": {
                "observation_count": self._store.observation_count,
                "knowledge_count": self._store.knowledge_count,
                "top_insights": [e.to_dict() for e in top_knowledge],
            }
        }
        if device_id:
            ctx["technical_context"]["device_summary"] = (
                self._store.get_device_summary(device_id)
            )
        return ctx

    def get_store(self) -> TechnicalKnowledgeStore:
        """Return the underlying :class:`TechnicalKnowledgeStore`."""
        return self._store
