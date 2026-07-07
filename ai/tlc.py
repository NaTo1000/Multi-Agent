"""
Technical Learning Cortex (TLC) — domain knowledge accumulator and
dream-state self-testing engine for the multi-agent orchestration system.

The TLC has two operating modes:

**Waking mode** — observes real agent task outcomes, accumulates
:class:`TechnicalObservation` records, and derives reusable
:class:`KnowledgeEntry` insights via :class:`PatternRecognizer`.

**Dream-state mode** — periodically enters a sandboxed self-test cycle in
which it deliberately applies guardrailed corruptions to a copy of its own
knowledge state, records the system's reactive measures, researches those
measures against a set of :ref:`AlgorithmicProtocols`, produces a
:class:`DreamEvaluation` with updated recommendations, evaluates the
quality of that output, and derives a :class:`MindStatus` that reflects
the overall cognitive health of the TLC.

Architecture
------------
Waking:

1. :class:`TechnicalObservation`    — one recorded agent task outcome.
2. :class:`KnowledgeEntry`          — a derived insight with confidence score.
3. :class:`TechnicalKnowledgeStore` — in-memory repository for observations
                                      and derived knowledge.
4. :class:`PatternRecognizer`       — analyses observation windows to produce
                                      :class:`KnowledgeEntry` objects.

Dream-state:

5. :class:`DreamCorruption`         — a guardrailed corruption specification.
6. :class:`ReactiveCapture`         — one system reaction to a corruption.
7. :class:`DreamResearch`           — resilience analysis across all captures.
8. :class:`DreamEvaluation`         — recommendations derived from activated
                                      :ref:`AlgorithmicProtocols`.
9. :class:`MindStatus`              — final cognitive health assessment.
10. :class:`DreamSession`           — complete record of one dream cycle.
11. :class:`DreamStateEngine`       — orchestrates the full dream loop.

Coordinator:

12. :class:`TLCModule`              — exposes ``record()``, ``query()``,
                                      ``get_context()``, and
                                      ``run_dream_cycle()``.

Design principles
-----------------
* All signals are derived exclusively from recorded observations or from
  deterministic computation on those observations.  No simulated,
  fabricated, or hallucinated data is introduced.
* Corruptions are applied only to a deep-copied sandbox — the live
  :class:`TechnicalKnowledgeStore` is never mutated during a dream cycle.
* Corruption magnitude is bounded by ``_DREAM_MAX_MAGNITUDE`` (0.5) so
  at most half of any observation set is corrupted in a single cycle.
* Protocol-triggered recommendations are advisory only; they do not
  automatically modify module constants.
"""

from __future__ import annotations

import copy
import logging
import uuid
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
# Dream-state constants
# ---------------------------------------------------------------------------

# Maximum fraction of observations that a single corruption may affect.
_DREAM_MAX_MAGNITUDE: float = 0.5

# Corruption type identifiers.
CORRUPT_NEGATE_SUCCESS: str = "negate_success"
CORRUPT_NULLIFY_PARAM: str = "nullify_param"
CORRUPT_INJECT_BAND_NOISE: str = "inject_band_noise"
CORRUPT_DEFLATE_CONFIDENCE: str = "deflate_confidence"
CORRUPT_DOMAIN_SWAP: str = "domain_swap"

# Mind-status thresholds (based on eval_score).
_MIND_STATUS_HEALTHY: float = 0.80
_MIND_STATUS_LEARNING: float = 0.60
_MIND_STATUS_STRESSED: float = 0.35

# Expected minimum knowledge entries for "coverage" calculation.
_EXPECTED_KNOWLEDGE_ENTRIES: int = 5

# ---------------------------------------------------------------------------
# Algorithmic Protocols
#
# Each protocol maps a vulnerability trigger to an advisory recommendation
# and a concrete parameter adjustment.  Triggered protocols are included in
# every DreamEvaluation produced by that dream cycle.
# ---------------------------------------------------------------------------

_PROTOCOLS: Dict[str, Dict[str, Any]] = {
    "alpha": {
        "name": "ProtocolAlpha — Evidence Reinforcement",
        "trigger": CORRUPT_NEGATE_SUCCESS,
        "recommendation": (
            "Increase _MIN_EVIDENCE from 5 to 7 to require more observations "
            "before emitting high-confidence knowledge entries, improving "
            "resilience to short-term success-rate fluctuations."
        ),
        "adjustment": {"_MIN_EVIDENCE": 7},
    },
    "beta": {
        "name": "ProtocolBeta — Null-Parameter Guard",
        "trigger": CORRUPT_NULLIFY_PARAM,
        "recommendation": (
            "Add an explicit None-value guard in parameter-preference analysis "
            "so that observations with missing tracked parameters are skipped "
            "rather than propagating null entries into the knowledge base."
        ),
        "adjustment": {"null_param_guard": True},
    },
    "gamma": {
        "name": "ProtocolGamma — Confidence Floor Adjustment",
        "trigger": CORRUPT_DEFLATE_CONFIDENCE,
        "recommendation": (
            "Lower the default min_confidence floor in get_context() from 0.3 "
            "to 0.1 to retain informative but lower-confidence insights when "
            "confidence scores have been deflated by transient data quality issues."
        ),
        "adjustment": {"min_confidence_floor": 0.1},
    },
    "delta": {
        "name": "ProtocolDelta — Domain Isolation Hardening",
        "trigger": CORRUPT_DOMAIN_SWAP,
        "recommendation": (
            "Validate domain labels against a canonical domain registry before "
            "indexing observations to prevent cross-domain pattern contamination."
        ),
        "adjustment": {"domain_validation": True},
    },
    "epsilon": {
        "name": "ProtocolEpsilon — Band-Value Sanitisation",
        "trigger": CORRUPT_INJECT_BAND_NOISE,
        "recommendation": (
            "Sanitise 'band' parameter values against the known-good band list "
            "(2.4GHz, 5GHz, 868MHz, 915MHz, LoRa) before recording observations "
            "to prevent malformed band strings from polluting preference analysis."
        ),
        "adjustment": {"band_sanitisation": True},
    },
}


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
# Dream-state dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DreamCorruption:
    """
    Specification for one guardrailed corruption applied during a dream cycle.

    Attributes:
        corruption_type: One of the ``CORRUPT_*`` module constants.
        target:          What is being corrupted (domain name, param key, …).
        magnitude:       Fraction of items to corrupt, capped at
                         ``_DREAM_MAX_MAGNITUDE``.
        guardrail:       Human-readable description of the safety bound applied.
    """

    corruption_type: str
    target: str
    magnitude: float
    guardrail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "corruption_type": self.corruption_type,
            "target": self.target,
            "magnitude": self.magnitude,
            "guardrail": self.guardrail,
        }


@dataclass
class ReactiveCapture:
    """
    The system's recorded reaction to a single :class:`DreamCorruption`.

    Attributes:
        corruption:     The corruption that was applied.
        component:      Name of the component under test
                        (e.g. ``"PatternRecognizer"``, ``"KnowledgeStore"``).
        reaction:       ``"resilient"`` | ``"degraded"`` | ``"failed"``.
        baseline_count: Knowledge entries before corruption.
        post_count:     Knowledge entries after corruption.
        details:        Supplementary metrics (confidence deltas, etc.).
    """

    corruption: DreamCorruption
    component: str
    reaction: str          # "resilient" | "degraded" | "failed"
    baseline_count: int
    post_count: int
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "corruption": self.corruption.to_dict(),
            "component": self.component,
            "reaction": self.reaction,
            "baseline_count": self.baseline_count,
            "post_count": self.post_count,
            "details": self.details,
        }


@dataclass
class DreamResearch:
    """
    Resilience analysis derived from a list of :class:`ReactiveCapture` records.

    Attributes:
        total_corruptions:    Total corruptions applied in the dream cycle.
        resilient_count:      Corruptions the system withstood without degradation.
        degraded_count:       Corruptions that caused partial quality loss.
        failed_count:         Corruptions that caused total or critical failure.
        resilience_score:     ``resilient_count / total_corruptions`` (0–1).
        vulnerable_triggers:  Corruption types that caused degraded/failed reactions.
        stable_triggers:      Corruption types that were fully resilient.
        findings:             Human-readable research findings.
    """

    total_corruptions: int
    resilient_count: int
    degraded_count: int
    failed_count: int
    resilience_score: float
    vulnerable_triggers: List[str]
    stable_triggers: List[str]
    findings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_corruptions": self.total_corruptions,
            "resilient_count": self.resilient_count,
            "degraded_count": self.degraded_count,
            "failed_count": self.failed_count,
            "resilience_score": round(self.resilience_score, 3),
            "vulnerable_triggers": self.vulnerable_triggers,
            "stable_triggers": self.stable_triggers,
            "findings": self.findings,
        }


@dataclass
class DreamEvaluation:
    """
    Advisory evaluation produced from :class:`DreamResearch`, including
    activated :ref:`AlgorithmicProtocols`.

    Attributes:
        research:              The underlying resilience research.
        activated_protocols:   Protocol names whose trigger conditions were met.
        recommendations:       Advisory strings from activated protocols.
        protocol_adjustments:  Concrete parameter-change suggestions, keyed
                               by protocol name.
        eval_score:            0–1 overall quality score for this dream cycle.
                               Computed as ``resilience_score`` weighted by
                               the fraction of protocols that were *not*
                               triggered (fewer triggers → healthier system).
    """

    research: DreamResearch
    activated_protocols: List[str]
    recommendations: List[str]
    protocol_adjustments: Dict[str, Dict[str, Any]]
    eval_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "research": self.research.to_dict(),
            "activated_protocols": self.activated_protocols,
            "recommendations": self.recommendations,
            "protocol_adjustments": self.protocol_adjustments,
            "eval_score": round(self.eval_score, 3),
        }


@dataclass
class MindStatus:
    """
    Final cognitive health assessment of the TLC after a dream cycle.

    Attributes:
        status:             ``"healthy"`` | ``"learning"`` | ``"stressed"``
                            | ``"degraded"``.
        eval_score:         Dream-cycle evaluation score (0–1).
        resilience_score:   Fraction of corruptions withstood (0–1).
        knowledge_coverage: Fraction of expected knowledge entries present (0–1).
        diagnosis:          Plain-English summary for operators.
        timestamp:          UTC ISO-8601 assessment timestamp.
    """

    status: str
    eval_score: float
    resilience_score: float
    knowledge_coverage: float
    diagnosis: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "eval_score": round(self.eval_score, 3),
            "resilience_score": round(self.resilience_score, 3),
            "knowledge_coverage": round(self.knowledge_coverage, 3),
            "diagnosis": self.diagnosis,
            "timestamp": self.timestamp,
        }


@dataclass
class DreamSession:
    """
    Complete record of one TLC dream cycle.

    Attributes:
        session_id:    Unique identifier for this cycle.
        corruptions:   Corruption specifications that were applied.
        captures:      Reactive captures (one per corruption).
        research:      Resilience analysis.
        evaluation:    Protocol-driven evaluation and recommendations.
        mind_status:   Final cognitive health assessment.
        started_at:    UTC ISO-8601 timestamp when the cycle began.
        completed_at:  UTC ISO-8601 timestamp when the cycle finished.
    """

    session_id: str
    corruptions: List[DreamCorruption]
    captures: List[ReactiveCapture]
    research: DreamResearch
    evaluation: DreamEvaluation
    mind_status: MindStatus
    started_at: str
    completed_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "corruptions": [c.to_dict() for c in self.corruptions],
            "captures": [c.to_dict() for c in self.captures],
            "research": self.research.to_dict(),
            "evaluation": self.evaluation.to_dict(),
            "mind_status": self.mind_status.to_dict(),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


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


# ---------------------------------------------------------------------------
# DreamStateEngine
# ---------------------------------------------------------------------------


class DreamStateEngine:
    """
    Orchestrates one TLC dream-state cycle.

    The engine operates entirely on a deep-copied sandbox — the live
    :class:`TechnicalKnowledgeStore` is never mutated.

    Cycle steps
    -----------
    1. Record the baseline knowledge state from the live store.
    2. Plan a fixed set of guardrailed corruptions.
    3. For each corruption: build a sandboxed store → apply corruption →
       run :class:`PatternRecognizer` → compare to baseline →
       record :class:`ReactiveCapture`.
    4. Research all captures → produce :class:`DreamResearch`.
    5. Match vulnerable triggers to :ref:`AlgorithmicProtocols` →
       produce :class:`DreamEvaluation`.
    6. Evaluate the evaluation output itself (self-referential quality check).
    7. Assess :class:`MindStatus` from eval_score + knowledge coverage.
    8. Return :class:`DreamSession`.
    """

    def __init__(self) -> None:
        self._recognizer = PatternRecognizer()

    def run(self, live_store: TechnicalKnowledgeStore) -> DreamSession:
        """
        Execute a complete dream cycle against *live_store*.

        Args:
            live_store: The active :class:`TechnicalKnowledgeStore`.

        Returns:
            A :class:`DreamSession` with full cycle details.
        """
        started_at = datetime.now(timezone.utc).isoformat()
        session_id = str(uuid.uuid4())

        # Step 1 — baseline
        baseline_entries = live_store.get_knowledge()
        baseline_count = len(baseline_entries)
        live_obs = live_store.get_observations()

        # Step 2 — plan corruptions (guardrailed)
        corruptions = self._plan_corruptions(live_obs, baseline_entries)

        # Step 3 — apply each corruption in its own sandbox and capture reaction
        captures: List[ReactiveCapture] = []
        for corruption in corruptions:
            capture = self._apply_and_capture(live_obs, corruption, baseline_count)
            captures.append(capture)

        # Step 4 — research
        research = self._research(captures)

        # Step 5 & 6 — evaluate (includes self-referential quality check)
        evaluation = self._evaluate(research)

        # Step 7 — assess mind status
        mind_status = self._assess_mind_status(evaluation, live_store)

        completed_at = datetime.now(timezone.utc).isoformat()

        session = DreamSession(
            session_id=session_id,
            corruptions=corruptions,
            captures=captures,
            research=research,
            evaluation=evaluation,
            mind_status=mind_status,
            started_at=started_at,
            completed_at=completed_at,
        )
        logger.info(
            "TLC dream cycle complete | session=%s | mind_status=%s | eval_score=%.3f",
            session_id, mind_status.status, evaluation.eval_score,
        )
        return session

    # ------------------------------------------------------------------
    # Step 2: plan corruptions
    # ------------------------------------------------------------------

    def _plan_corruptions(
        self,
        observations: List[TechnicalObservation],
        baseline: List[KnowledgeEntry],
    ) -> List[DreamCorruption]:
        """
        Build a guardrailed corruption plan for the current state.

        Returns one corruption per type that is applicable given the
        available observations and knowledge entries.
        """
        planned: List[DreamCorruption] = []
        n_obs = len(observations)

        # CORRUPT_NEGATE_SUCCESS — only useful if there are any observations
        if n_obs > 0:
            mag = min(_DREAM_MAX_MAGNITUDE, max(0.1, 2 / n_obs))
            planned.append(DreamCorruption(
                corruption_type=CORRUPT_NEGATE_SUCCESS,
                target="success_flag",
                magnitude=mag,
                guardrail=(
                    f"At most {mag:.0%} of observations are flipped; "
                    "applied to sandbox copy only."
                ),
            ))

        # CORRUPT_NULLIFY_PARAM — only useful if tracked params are present
        has_tracked = any(
            any(o.params.get(p) is not None for p in _TRACKED_PARAMS)
            for o in observations
        )
        if has_tracked and n_obs > 0:
            mag = min(_DREAM_MAX_MAGNITUDE, max(0.1, 2 / n_obs))
            planned.append(DreamCorruption(
                corruption_type=CORRUPT_NULLIFY_PARAM,
                target=",".join(_TRACKED_PARAMS),
                magnitude=mag,
                guardrail=(
                    f"At most {mag:.0%} of tracked-param values are nullified; "
                    "applied to sandbox copy only."
                ),
            ))

        # CORRUPT_INJECT_BAND_NOISE — only useful if band param exists
        has_band = any(o.params.get("band") is not None for o in observations)
        if has_band and n_obs > 0:
            mag = min(_DREAM_MAX_MAGNITUDE, max(0.1, 2 / n_obs))
            planned.append(DreamCorruption(
                corruption_type=CORRUPT_INJECT_BAND_NOISE,
                target="band",
                magnitude=mag,
                guardrail=(
                    f"At most {mag:.0%} of 'band' values replaced with "
                    "'INVALID_BAND'; applied to sandbox copy only."
                ),
            ))

        # CORRUPT_DEFLATE_CONFIDENCE — only useful if knowledge entries exist
        if baseline:
            planned.append(DreamCorruption(
                corruption_type=CORRUPT_DEFLATE_CONFIDENCE,
                target="knowledge_entries",
                magnitude=0.5,
                guardrail=(
                    "All knowledge entry confidence values halved in sandbox; "
                    "live store is not modified."
                ),
            ))

        # CORRUPT_DOMAIN_SWAP — only useful if ≥ 2 distinct domains
        domains = {o.domain for o in observations}
        if len(domains) >= 2 and n_obs > 0:
            mag = min(_DREAM_MAX_MAGNITUDE, max(0.1, 2 / n_obs))
            planned.append(DreamCorruption(
                corruption_type=CORRUPT_DOMAIN_SWAP,
                target="domain_label",
                magnitude=mag,
                guardrail=(
                    f"At most {mag:.0%} of observations have their domain "
                    "label swapped; applied to sandbox copy only."
                ),
            ))

        return planned

    # ------------------------------------------------------------------
    # Step 3: apply one corruption and capture the reaction
    # ------------------------------------------------------------------

    def _apply_and_capture(
        self,
        observations: List[TechnicalObservation],
        corruption: DreamCorruption,
        baseline_count: int,
    ) -> ReactiveCapture:
        """
        Build a sandboxed store, apply *corruption*, run pattern recognition,
        and compare the result to *baseline_count*.
        """
        try:
            sandboxed_obs = self._corrupt_observations(observations, corruption)
            sandbox_store = TechnicalKnowledgeStore()
            for obs in sandboxed_obs:
                sandbox_store.add_observation(obs)

            # For confidence deflation, also seed the sandbox with corrupted entries
            if corruption.corruption_type == CORRUPT_DEFLATE_CONFIDENCE:
                self._seed_deflated_knowledge(sandbox_store, baseline_count)
            else:
                self._recognizer.analyse(sandbox_store)

            post_count = sandbox_store.knowledge_count
            avg_conf_post = self._avg_confidence(sandbox_store)

            reaction = self._classify_reaction(baseline_count, post_count)
            details: Dict[str, Any] = {
                "baseline_knowledge_count": baseline_count,
                "post_knowledge_count": post_count,
                "avg_confidence_post": round(avg_conf_post, 3),
            }
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("DreamStateEngine: corruption %s raised: %s",
                           corruption.corruption_type, exc)
            reaction = "failed"
            post_count = 0
            details = {"error": str(exc)}

        return ReactiveCapture(
            corruption=corruption,
            component="PatternRecognizer",
            reaction=reaction,
            baseline_count=baseline_count,
            post_count=post_count,
            details=details,
        )

    # ------------------------------------------------------------------
    # Corruption applicators
    # ------------------------------------------------------------------

    def _corrupt_observations(
        self,
        observations: List[TechnicalObservation],
        corruption: DreamCorruption,
    ) -> List[TechnicalObservation]:
        """Return a deep-copied, corrupted list of observations."""
        sandboxed = copy.deepcopy(observations)
        n = len(sandboxed)
        if n == 0:
            return sandboxed

        # Number of items to affect (at least 1)
        n_corrupt = max(1, int(n * corruption.magnitude))

        ctype = corruption.corruption_type

        if ctype == CORRUPT_NEGATE_SUCCESS:
            for obs in sandboxed[:n_corrupt]:
                obs.success = not obs.success

        elif ctype == CORRUPT_NULLIFY_PARAM:
            for obs in sandboxed[:n_corrupt]:
                for pkey in _TRACKED_PARAMS:
                    if pkey in obs.params:
                        obs.params[pkey] = None

        elif ctype == CORRUPT_INJECT_BAND_NOISE:
            for obs in sandboxed[:n_corrupt]:
                if "band" in obs.params:
                    obs.params["band"] = "INVALID_BAND"

        elif ctype == CORRUPT_DOMAIN_SWAP:
            domains = list({o.domain for o in sandboxed})
            if len(domains) >= 2:
                # Rotate domain labels among the first n_corrupt observations
                for i, obs in enumerate(sandboxed[:n_corrupt]):
                    obs.domain = domains[(domains.index(obs.domain) + 1) % len(domains)]

        # CORRUPT_DEFLATE_CONFIDENCE acts on the knowledge store, not observations
        return sandboxed

    def _seed_deflated_knowledge(
        self,
        store: TechnicalKnowledgeStore,
        baseline_count: int,
    ) -> None:
        """
        Populate the sandbox store with synthetic entries at half confidence
        to test whether confidence-deflated knowledge still surfaces in queries.
        """
        self._recognizer.analyse(store)
        deflated: Dict[str, KnowledgeEntry] = {}
        for key, entry in store._knowledge.items():
            e = copy.deepcopy(entry)
            e.confidence = round(e.confidence * 0.5, 3)
            deflated[key] = e
        store._knowledge = deflated

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _avg_confidence(store: TechnicalKnowledgeStore) -> float:
        entries = store.get_knowledge()
        if not entries:
            return 0.0
        return sum(e.confidence for e in entries) / len(entries)

    @staticmethod
    def _classify_reaction(baseline: int, post: int) -> str:
        """
        Classify the system's reaction to a corruption.

        - ``"resilient"``  : knowledge count unchanged or increased.
        - ``"degraded"``   : knowledge count dropped but not to zero
                             (or baseline was zero and post is also zero).
        - ``"failed"``     : knowledge count dropped to zero when baseline > 0.
        """
        if baseline == 0:
            return "resilient"
        if post >= baseline:
            return "resilient"
        if post == 0:
            return "failed"
        return "degraded"

    # ------------------------------------------------------------------
    # Step 4: research
    # ------------------------------------------------------------------

    def _research(self, captures: List[ReactiveCapture]) -> DreamResearch:
        """Analyse captures and produce a :class:`DreamResearch`."""
        total = len(captures)
        resilient = sum(1 for c in captures if c.reaction == "resilient")
        degraded = sum(1 for c in captures if c.reaction == "degraded")
        failed = sum(1 for c in captures if c.reaction == "failed")

        resilience_score = resilient / total if total > 0 else 1.0

        vulnerable_triggers = [
            c.corruption.corruption_type
            for c in captures
            if c.reaction in ("degraded", "failed")
        ]
        stable_triggers = [
            c.corruption.corruption_type
            for c in captures
            if c.reaction == "resilient"
        ]

        findings: List[str] = []
        if resilient == total:
            findings.append(
                "All corruptions were withstood without degradation — "
                "pattern recognition is robust across this test set."
            )
        if failed > 0:
            failed_types = [
                c.corruption.corruption_type for c in captures if c.reaction == "failed"
            ]
            findings.append(
                f"Critical failures detected for corruption types: "
                f"{', '.join(failed_types)}. Immediate protocol review recommended."
            )
        if degraded > 0:
            deg_types = [
                c.corruption.corruption_type for c in captures if c.reaction == "degraded"
            ]
            findings.append(
                f"Partial degradation detected for: {', '.join(deg_types)}. "
                "Advisory protocols have been activated."
            )
        if not findings:
            findings.append("No significant findings from this dream cycle.")

        return DreamResearch(
            total_corruptions=total,
            resilient_count=resilient,
            degraded_count=degraded,
            failed_count=failed,
            resilience_score=round(resilience_score, 3),
            vulnerable_triggers=vulnerable_triggers,
            stable_triggers=stable_triggers,
            findings=findings,
        )

    # ------------------------------------------------------------------
    # Step 5 & 6: evaluate
    # ------------------------------------------------------------------

    def _evaluate(self, research: DreamResearch) -> DreamEvaluation:
        """
        Match vulnerable triggers to :ref:`AlgorithmicProtocols` and
        produce a :class:`DreamEvaluation`.

        The ``eval_score`` is computed as::

            eval_score = resilience_score
                         × (1 − failed_fraction)
                         × protocol_health_factor

        where ``protocol_health_factor`` = 1 − (activated / total_protocols).
        """
        activated_protocols: List[str] = []
        recommendations: List[str] = []
        protocol_adjustments: Dict[str, Dict[str, Any]] = {}

        # Activate protocols whose trigger is in the vulnerable set
        vulnerable_set = set(research.vulnerable_triggers)
        for proto_key, proto in _PROTOCOLS.items():
            if proto["trigger"] in vulnerable_set:
                activated_protocols.append(proto["name"])
                recommendations.append(proto["recommendation"])
                protocol_adjustments[proto["name"]] = proto["adjustment"]

        # Compute eval_score
        total = research.total_corruptions
        failed_fraction = research.failed_count / total if total > 0 else 0.0
        n_protocols = len(_PROTOCOLS)
        n_activated = len(activated_protocols)
        protocol_health = 1.0 - (n_activated / n_protocols) if n_protocols > 0 else 1.0

        # Self-referential quality check: if no recommendations were produced
        # despite failures, that is itself a quality deficit.
        if research.failed_count > 0 and not recommendations:
            recommendations.append(
                "Failed reactions were recorded but no protocol covered them — "
                "review and extend the AlgorithmicProtocol registry."
            )
            protocol_health = max(0.0, protocol_health - 0.1)

        eval_score = round(
            research.resilience_score * (1.0 - failed_fraction) * protocol_health,
            3,
        )

        return DreamEvaluation(
            research=research,
            activated_protocols=activated_protocols,
            recommendations=recommendations,
            protocol_adjustments=protocol_adjustments,
            eval_score=eval_score,
        )

    # ------------------------------------------------------------------
    # Step 7: mind status
    # ------------------------------------------------------------------

    def _assess_mind_status(
        self,
        evaluation: DreamEvaluation,
        live_store: TechnicalKnowledgeStore,
    ) -> MindStatus:
        """
        Derive :class:`MindStatus` from *evaluation* and live knowledge coverage.
        """
        eval_score = evaluation.eval_score
        resilience = evaluation.research.resilience_score
        coverage = min(
            1.0,
            live_store.knowledge_count / _EXPECTED_KNOWLEDGE_ENTRIES,
        )

        if eval_score >= _MIND_STATUS_HEALTHY:
            status = "healthy"
        elif eval_score >= _MIND_STATUS_LEARNING:
            status = "learning"
        elif eval_score >= _MIND_STATUS_STRESSED:
            status = "stressed"
        else:
            status = "degraded"

        # Build a diagnostic narrative
        parts: List[str] = [
            f"Mind status: {status.upper()}.",
            f"Eval score {eval_score:.2f}, resilience {resilience:.2f}, "
            f"knowledge coverage {coverage:.2f}.",
        ]
        if evaluation.activated_protocols:
            parts.append(
                f"{len(evaluation.activated_protocols)} protocol(s) activated: "
                + "; ".join(evaluation.activated_protocols) + "."
            )
        if status == "healthy":
            parts.append(
                "The TLC is operating within normal parameters."
            )
        elif status == "learning":
            parts.append(
                "The TLC is accumulating knowledge but resilience margins "
                "have room for improvement."
            )
        elif status == "stressed":
            parts.append(
                "Significant vulnerabilities detected. Review activated "
                "protocol recommendations."
            )
        else:
            parts.append(
                "Critical resilience failures. Immediate protocol intervention required."
            )

        return MindStatus(
            status=status,
            eval_score=eval_score,
            resilience_score=resilience,
            knowledge_coverage=coverage,
            diagnosis="  ".join(parts),
        )


# ---------------------------------------------------------------------------
# TLCModule
# ---------------------------------------------------------------------------


class TLCModule:
    """
    Technical Learning Cortex — high-level coordinator.

    Exposes both waking-mode observation recording and dream-state
    self-testing in a single, reusable interface.

    Args:
        store:        Optional external :class:`TechnicalKnowledgeStore`.
                      Provide one to share state with other components.
        recognizer:   Optional external :class:`PatternRecognizer`.
        dream_engine: Optional external :class:`DreamStateEngine`.
    """

    def __init__(
        self,
        store: Optional[TechnicalKnowledgeStore] = None,
        recognizer: Optional[PatternRecognizer] = None,
        dream_engine: Optional[DreamStateEngine] = None,
    ) -> None:
        self._store = store or TechnicalKnowledgeStore()
        self._recognizer = recognizer or PatternRecognizer()
        self._dream_engine = dream_engine or DreamStateEngine()

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

    def run_dream_cycle(self) -> DreamSession:
        """
        Execute one dream-state learning cycle against the current knowledge state.

        The cycle:
        1. Snapshots the live :class:`TechnicalKnowledgeStore` as a baseline.
        2. Plans a set of guardrailed corruptions applicable to the current data.
        3. Applies each corruption to a sandboxed copy, runs
           :class:`PatternRecognizer`, and records a :class:`ReactiveCapture`.
        4. Researches all captures to produce :class:`DreamResearch`.
        5. Matches vulnerable triggers to :ref:`AlgorithmicProtocols` and
           produces a :class:`DreamEvaluation` with recommendations.
        6. Evaluates the evaluation output itself (self-referential quality check).
        7. Derives :class:`MindStatus` from eval score and knowledge coverage.

        Returns:
            A :class:`DreamSession` containing the full cycle record including
            the :class:`MindStatus` cognitive health assessment.
        """
        return self._dream_engine.run(self._store)

    def get_store(self) -> TechnicalKnowledgeStore:
        """Return the underlying :class:`TechnicalKnowledgeStore`."""
        return self._store
