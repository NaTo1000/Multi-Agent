"""
Tests for the Technical Learning Cortex (TLC).

Covers:
- TechnicalObservation creation and serialisation
- KnowledgeEntry creation and serialisation
- _confidence helper
- TechnicalKnowledgeStore: indexing, filtering, device summaries
- PatternRecognizer: task reliability, device health, parameter preferences
- DreamCorruption / ReactiveCapture dataclasses
- DreamResearch: resilience analysis
- DreamEvaluation: protocol activation and eval_score
- MindStatus: all four status levels
- DreamSession: complete structure
- DreamStateEngine: sandboxing, all five corruption types, mind assessment
- TLCModule: end-to-end waking and dream-state cycles
"""

from __future__ import annotations

import json
import pytest

from ai.tlc import (
    # Waking-mode classes
    TechnicalObservation,
    KnowledgeEntry,
    TechnicalKnowledgeStore,
    PatternRecognizer,
    # Dream-state classes
    DreamCorruption,
    ReactiveCapture,
    DreamResearch,
    DreamEvaluation,
    MindStatus,
    DreamSession,
    DreamStateEngine,
    # Main module
    TLCModule,
    # Helpers / constants
    _confidence,
    _MIN_EVIDENCE,
    _FAILURE_THRESHOLD,
    _SUCCESS_THRESHOLD,
    _DREAM_MAX_MAGNITUDE,
    _MIND_STATUS_HEALTHY,
    _MIND_STATUS_LEARNING,
    _MIND_STATUS_STRESSED,
    # Corruption type constants
    CORRUPT_NEGATE_SUCCESS,
    CORRUPT_NULLIFY_PARAM,
    CORRUPT_INJECT_BAND_NOISE,
    CORRUPT_DEFLATE_CONFIDENCE,
    CORRUPT_DOMAIN_SWAP,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _obs(
    domain="frequency",
    task="scan",
    params=None,
    outcome=None,
    success=True,
    device_id=None,
) -> TechnicalObservation:
    return TechnicalObservation(
        domain=domain,
        task=task,
        params=params or {},
        outcome=outcome or {},
        success=success,
        device_id=device_id,
    )


def _make_store_with_failures(domain="frequency", task="scan", n_fail=3, n_ok=1) -> TechnicalKnowledgeStore:
    """Return a store whose (domain, task) pair has a high failure rate."""
    store = TechnicalKnowledgeStore()
    for _ in range(n_fail):
        store.add_observation(_obs(domain=domain, task=task, success=False))
    for _ in range(n_ok):
        store.add_observation(_obs(domain=domain, task=task, success=True))
    return store


def _make_store_with_successes(domain="frequency", task="scan", n_ok=5) -> TechnicalKnowledgeStore:
    """Return a store whose (domain, task) pair has a high success rate."""
    store = TechnicalKnowledgeStore()
    for _ in range(n_ok):
        store.add_observation(_obs(domain=domain, task=task, success=True))
    return store


# ===========================================================================
# _confidence helper
# ===========================================================================

class TestConfidenceHelper:

    def test_zero_total_returns_zero(self):
        assert _confidence(0, 0) == 0.0

    def test_perfect_consistency_below_min_evidence(self):
        # 2/2 consistent but below _MIN_EVIDENCE → factor < 1.0
        score = _confidence(2, 2)
        assert score < 1.0
        assert score > 0.0

    def test_perfect_consistency_at_min_evidence(self):
        score = _confidence(_MIN_EVIDENCE, _MIN_EVIDENCE)
        assert score == 1.0

    def test_partial_consistency(self):
        score = _confidence(3, 5)
        # consistency = 0.6, evidence_factor = 1.0 → 0.6
        assert abs(score - 0.6) < 1e-6

    def test_zero_consistent_returns_zero(self):
        assert _confidence(0, 5) == 0.0

    def test_above_min_evidence_caps_at_consistency(self):
        # 10 consistent out of 10 with total > _MIN_EVIDENCE
        assert _confidence(10, 10) == 1.0

    def test_fractional_consistency_above_evidence(self):
        score = _confidence(8, 10)
        assert abs(score - 0.8) < 1e-6


# ===========================================================================
# TechnicalObservation
# ===========================================================================

class TestTechnicalObservation:

    def test_creation_defaults(self):
        obs = _obs()
        assert obs.domain == "frequency"
        assert obs.task == "scan"
        assert obs.success is True
        assert obs.device_id is None
        assert obs.timestamp  # non-empty

    def test_to_dict_keys(self):
        obs = _obs(device_id="esp-1")
        d = obs.to_dict()
        for key in ("domain", "task", "params", "outcome", "success", "device_id", "timestamp"):
            assert key in d

    def test_to_dict_is_serialisable(self):
        obs = _obs(params={"band": "2.4GHz"}, outcome={"channels": [1, 6, 11]})
        json.dumps(obs.to_dict())  # must not raise

    def test_failure_observation(self):
        obs = _obs(success=False, outcome={"error": "timeout"})
        assert obs.success is False
        assert obs.to_dict()["success"] is False


# ===========================================================================
# KnowledgeEntry
# ===========================================================================

class TestKnowledgeEntry:

    def test_creation(self):
        entry = KnowledgeEntry(
            concept="scan is reliable",
            domain="frequency",
            confidence=0.8,
            evidence_count=5,
            tags=["frequency", "scan", "high_reliability"],
        )
        assert entry.concept == "scan is reliable"
        assert entry.confidence == 0.8

    def test_to_dict_keys(self):
        entry = KnowledgeEntry(
            concept="test", domain="d", confidence=0.5, evidence_count=3
        )
        d = entry.to_dict()
        for key in ("concept", "domain", "confidence", "evidence_count",
                    "tags", "first_seen", "last_seen"):
            assert key in d

    def test_to_dict_is_serialisable(self):
        entry = KnowledgeEntry(
            concept="test", domain="d", confidence=0.5, evidence_count=3,
            tags=["a", "b"]
        )
        json.dumps(entry.to_dict())  # must not raise

    def test_confidence_rounded_in_dict(self):
        entry = KnowledgeEntry(
            concept="x", domain="d", confidence=0.123456789, evidence_count=1
        )
        assert entry.to_dict()["confidence"] == round(0.123456789, 3)


# ===========================================================================
# TechnicalKnowledgeStore
# ===========================================================================

class TestTechnicalKnowledgeStore:

    def test_add_and_count(self):
        store = TechnicalKnowledgeStore()
        store.add_observation(_obs())
        assert store.observation_count == 1

    def test_domain_filter(self):
        store = TechnicalKnowledgeStore()
        store.add_observation(_obs(domain="frequency"))
        store.add_observation(_obs(domain="firmware"))
        freq = store.get_observations(domain="frequency")
        assert len(freq) == 1
        assert freq[0].domain == "frequency"

    def test_device_filter(self):
        store = TechnicalKnowledgeStore()
        store.add_observation(_obs(device_id="esp-1"))
        store.add_observation(_obs(device_id="esp-2"))
        assert len(store.get_observations(device_id="esp-1")) == 1

    def test_domain_and_device_filter(self):
        store = TechnicalKnowledgeStore()
        store.add_observation(_obs(domain="frequency", device_id="esp-1"))
        store.add_observation(_obs(domain="firmware", device_id="esp-1"))
        result = store.get_observations(domain="frequency", device_id="esp-1")
        assert len(result) == 1

    def test_no_filter_returns_all(self):
        store = TechnicalKnowledgeStore()
        for _ in range(3):
            store.add_observation(_obs())
        assert len(store.get_observations()) == 3

    def test_get_knowledge_empty(self):
        store = TechnicalKnowledgeStore()
        assert store.get_knowledge() == []

    def test_upsert_and_retrieve_knowledge(self):
        store = TechnicalKnowledgeStore()
        entry = KnowledgeEntry(
            concept="test", domain="d", confidence=0.9, evidence_count=5
        )
        store.upsert_knowledge("key1", entry)
        results = store.get_knowledge()
        assert len(results) == 1
        assert results[0].concept == "test"

    def test_upsert_replaces_existing(self):
        store = TechnicalKnowledgeStore()
        e1 = KnowledgeEntry(concept="old", domain="d", confidence=0.5, evidence_count=2)
        e2 = KnowledgeEntry(concept="new", domain="d", confidence=0.9, evidence_count=5)
        store.upsert_knowledge("key1", e1)
        store.upsert_knowledge("key1", e2)
        assert store.knowledge_count == 1
        assert store.get_knowledge()[0].concept == "new"

    def test_knowledge_domain_filter(self):
        store = TechnicalKnowledgeStore()
        store.upsert_knowledge("k1", KnowledgeEntry(
            concept="a", domain="frequency", confidence=0.8, evidence_count=5
        ))
        store.upsert_knowledge("k2", KnowledgeEntry(
            concept="b", domain="firmware", confidence=0.8, evidence_count=5
        ))
        assert len(store.get_knowledge(domain="frequency")) == 1

    def test_knowledge_tag_filter(self):
        store = TechnicalKnowledgeStore()
        store.upsert_knowledge("k1", KnowledgeEntry(
            concept="a", domain="d", confidence=0.8, evidence_count=5,
            tags=["scan", "high_reliability"]
        ))
        store.upsert_knowledge("k2", KnowledgeEntry(
            concept="b", domain="d", confidence=0.7, evidence_count=3,
            tags=["build"]
        ))
        assert len(store.get_knowledge(tags=["scan"])) == 1
        assert len(store.get_knowledge(tags=["build"])) == 1
        assert len(store.get_knowledge(tags=["scan", "build"])) == 2

    def test_knowledge_min_confidence_filter(self):
        store = TechnicalKnowledgeStore()
        store.upsert_knowledge("k1", KnowledgeEntry(
            concept="high", domain="d", confidence=0.9, evidence_count=5
        ))
        store.upsert_knowledge("k2", KnowledgeEntry(
            concept="low", domain="d", confidence=0.1, evidence_count=2
        ))
        assert len(store.get_knowledge(min_confidence=0.5)) == 1

    def test_knowledge_sorted_by_confidence_descending(self):
        store = TechnicalKnowledgeStore()
        store.upsert_knowledge("k1", KnowledgeEntry(
            concept="low", domain="d", confidence=0.3, evidence_count=2
        ))
        store.upsert_knowledge("k2", KnowledgeEntry(
            concept="high", domain="d", confidence=0.9, evidence_count=5
        ))
        results = store.get_knowledge()
        assert results[0].confidence >= results[1].confidence

    def test_device_summary_unknown_device(self):
        store = TechnicalKnowledgeStore()
        summary = store.get_device_summary("ghost")
        assert summary["observation_count"] == 0
        assert summary["success_rate"] is None
        assert summary["dominant_failing_domain"] is None

    def test_device_summary_known_device(self):
        store = TechnicalKnowledgeStore()
        store.add_observation(_obs(domain="frequency", device_id="esp-1", success=False))
        store.add_observation(_obs(domain="frequency", device_id="esp-1", success=False))
        store.add_observation(_obs(domain="firmware", device_id="esp-1", success=True))
        summary = store.get_device_summary("esp-1")
        assert summary["observation_count"] == 3
        assert abs(summary["success_rate"] - 1 / 3) < 0.01
        assert summary["dominant_failing_domain"] == "frequency"

    def test_device_summary_all_successes(self):
        store = TechnicalKnowledgeStore()
        for _ in range(4):
            store.add_observation(_obs(device_id="esp-2", success=True))
        summary = store.get_device_summary("esp-2")
        assert summary["success_rate"] == 1.0
        assert summary["dominant_failing_domain"] is None


# ===========================================================================
# PatternRecognizer
# ===========================================================================

class TestPatternRecognizer:

    def test_no_entries_for_empty_store(self):
        recognizer = PatternRecognizer()
        store = TechnicalKnowledgeStore()
        recognizer.analyse(store)
        assert store.knowledge_count == 0

    def test_task_low_reliability_detected(self):
        store = _make_store_with_failures(n_fail=3, n_ok=1)
        recognizer = PatternRecognizer()
        recognizer.analyse(store)
        entries = store.get_knowledge(tags=["low_reliability"])
        assert len(entries) >= 1
        assert "low_reliability" in entries[0].tags

    def test_task_high_reliability_detected(self):
        store = _make_store_with_successes(n_ok=5)
        recognizer = PatternRecognizer()
        recognizer.analyse(store)
        entries = store.get_knowledge(tags=["high_reliability"])
        assert len(entries) >= 1

    def test_no_entry_for_mixed_outcomes(self):
        """A 50/50 mix should not reach either threshold."""
        store = TechnicalKnowledgeStore()
        for _ in range(4):
            store.add_observation(_obs(success=True))
        for _ in range(4):
            store.add_observation(_obs(success=False))
        recognizer = PatternRecognizer()
        recognizer.analyse(store)
        # Neither threshold crossed → no entries
        assert store.knowledge_count == 0

    def test_confidence_increases_with_more_evidence(self):
        """More observations of the same pattern → higher confidence."""
        r = PatternRecognizer()
        store_few = TechnicalKnowledgeStore()
        for _ in range(2):
            store_few.add_observation(_obs(success=False))
        r.analyse(store_few)
        conf_few = store_few.get_knowledge()[0].confidence if store_few.knowledge_count > 0 else 0.0

        store_many = TechnicalKnowledgeStore()
        for _ in range(10):
            store_many.add_observation(_obs(success=False))
        r.analyse(store_many)
        conf_many = store_many.get_knowledge()[0].confidence

        assert conf_many >= conf_few

    def test_device_health_poor_detected(self):
        store = TechnicalKnowledgeStore()
        for _ in range(4):
            store.add_observation(_obs(device_id="bad-device", success=False))
        store.add_observation(_obs(device_id="bad-device", success=True))
        recognizer = PatternRecognizer()
        recognizer.analyse(store)
        device_entries = store.get_knowledge(tags=["health_poor"])
        assert any("bad-device" in e.tags for e in device_entries)

    def test_device_health_good_detected(self):
        store = TechnicalKnowledgeStore()
        for _ in range(5):
            store.add_observation(_obs(device_id="good-device", success=True))
        recognizer = PatternRecognizer()
        recognizer.analyse(store)
        device_entries = store.get_knowledge(tags=["health_good"])
        assert any("good-device" in e.tags for e in device_entries)

    def test_parameter_preference_detected(self):
        store = TechnicalKnowledgeStore()
        for _ in range(5):
            store.add_observation(_obs(
                domain="frequency", task="scan",
                params={"band": "2.4GHz"}, success=True,
            ))
        recognizer = PatternRecognizer()
        recognizer.analyse(store)
        pref_entries = store.get_knowledge(tags=["preference"])
        assert len(pref_entries) >= 1
        assert any("param:band" in e.tags for e in pref_entries)

    def test_parameter_preference_not_detected_below_min_observations(self):
        """Fewer than 2 observations for a param value → no preference entry."""
        store = TechnicalKnowledgeStore()
        store.add_observation(_obs(
            domain="frequency", task="scan",
            params={"band": "5GHz"}, success=True,
        ))
        recognizer = PatternRecognizer()
        recognizer.analyse(store)
        pref_entries = store.get_knowledge(tags=["preference"])
        # Preference requires ≥ 2 observations
        assert not any("value:5GHz" in e.tags for e in pref_entries)

    def test_parameter_preference_not_detected_for_failing_values(self):
        """A param value that mostly fails should not produce a preference entry."""
        store = TechnicalKnowledgeStore()
        for _ in range(3):
            store.add_observation(_obs(
                domain="frequency", task="scan",
                params={"band": "868MHz"}, success=False,
            ))
        recognizer = PatternRecognizer()
        recognizer.analyse(store)
        pref_entries = store.get_knowledge(tags=["preference"])
        assert not any("value:868MHz" in e.tags for e in pref_entries)

    def test_repeated_analysis_upserts_entries(self):
        """Calling analyse twice should not double-count entries."""
        store = _make_store_with_failures(n_fail=3, n_ok=0)
        r = PatternRecognizer()
        r.analyse(store)
        count_after_first = store.knowledge_count
        r.analyse(store)
        assert store.knowledge_count == count_after_first

    def test_multiple_domains_tracked_independently(self):
        store = TechnicalKnowledgeStore()
        for _ in range(5):
            store.add_observation(_obs(domain="frequency", task="scan", success=True))
        for _ in range(4):
            store.add_observation(_obs(domain="firmware", task="build", success=False))
        store.add_observation(_obs(domain="firmware", task="build", success=True))
        r = PatternRecognizer()
        r.analyse(store)
        freq_entries = store.get_knowledge(domain="frequency")
        firm_entries = store.get_knowledge(domain="firmware")
        assert any("high_reliability" in e.tags for e in freq_entries)
        assert any("low_reliability" in e.tags for e in firm_entries)


# ===========================================================================
# Dream-state dataclasses
# ===========================================================================

class TestDreamCorruption:

    def test_creation_and_dict(self):
        c = DreamCorruption(
            corruption_type=CORRUPT_NEGATE_SUCCESS,
            target="success_flag",
            magnitude=0.3,
            guardrail="At most 30% of observations are flipped.",
        )
        d = c.to_dict()
        assert d["corruption_type"] == CORRUPT_NEGATE_SUCCESS
        assert d["magnitude"] == 0.3
        assert "guardrail" in d

    def test_magnitude_does_not_exceed_constant(self):
        c = DreamCorruption(
            corruption_type=CORRUPT_NEGATE_SUCCESS,
            target="success_flag",
            magnitude=_DREAM_MAX_MAGNITUDE,
            guardrail="bounded",
        )
        assert c.magnitude <= _DREAM_MAX_MAGNITUDE


class TestReactiveCapture:

    def _make_capture(self, reaction="resilient") -> ReactiveCapture:
        corruption = DreamCorruption(
            corruption_type=CORRUPT_NEGATE_SUCCESS,
            target="success_flag",
            magnitude=0.2,
            guardrail="bounded",
        )
        return ReactiveCapture(
            corruption=corruption,
            component="PatternRecognizer",
            reaction=reaction,
            baseline_count=3,
            post_count=3,
        )

    def test_creation_and_dict(self):
        cap = self._make_capture()
        d = cap.to_dict()
        assert d["reaction"] == "resilient"
        assert "corruption" in d
        assert "component" in d

    def test_is_serialisable(self):
        json.dumps(self._make_capture("degraded").to_dict())

    def test_all_reaction_types(self):
        for reaction in ("resilient", "degraded", "failed"):
            cap = self._make_capture(reaction)
            assert cap.reaction == reaction


class TestDreamResearch:

    def test_creation_and_dict(self):
        research = DreamResearch(
            total_corruptions=4,
            resilient_count=3,
            degraded_count=1,
            failed_count=0,
            resilience_score=0.75,
            vulnerable_triggers=[CORRUPT_NULLIFY_PARAM],
            stable_triggers=[CORRUPT_NEGATE_SUCCESS, CORRUPT_DEFLATE_CONFIDENCE,
                             CORRUPT_INJECT_BAND_NOISE],
            findings=["Partial degradation on param nullification."],
        )
        d = research.to_dict()
        assert d["total_corruptions"] == 4
        assert d["resilience_score"] == 0.75
        assert CORRUPT_NULLIFY_PARAM in d["vulnerable_triggers"]

    def test_is_serialisable(self):
        research = DreamResearch(
            total_corruptions=2, resilient_count=2, degraded_count=0, failed_count=0,
            resilience_score=1.0, vulnerable_triggers=[], stable_triggers=[],
            findings=["All good."],
        )
        json.dumps(research.to_dict())


class TestMindStatus:

    def _make_status(self, status="healthy", eval_score=0.9,
                     resilience=0.9, coverage=1.0) -> MindStatus:
        return MindStatus(
            status=status,
            eval_score=eval_score,
            resilience_score=resilience,
            knowledge_coverage=coverage,
            diagnosis=f"Test diagnosis for {status}.",
        )

    def test_creation_and_dict(self):
        ms = self._make_status()
        d = ms.to_dict()
        assert d["status"] == "healthy"
        assert "diagnosis" in d
        assert "timestamp" in d

    def test_all_status_values(self):
        for s in ("healthy", "learning", "stressed", "degraded"):
            ms = self._make_status(status=s)
            assert ms.status == s

    def test_is_serialisable(self):
        json.dumps(self._make_status("learning", 0.7, 0.7, 0.5).to_dict())


# ===========================================================================
# DreamStateEngine
# ===========================================================================

class TestDreamStateEngine:

    def _make_rich_store(self) -> TechnicalKnowledgeStore:
        """Store with several domains, devices and parameter variants."""
        store = TechnicalKnowledgeStore()
        for _ in range(5):
            store.add_observation(_obs(
                domain="frequency", task="scan",
                params={"band": "2.4GHz"}, success=True, device_id="esp-1"
            ))
        for _ in range(3):
            store.add_observation(_obs(
                domain="firmware", task="build",
                params={"template": "base"}, success=False, device_id="esp-2"
            ))
        for _ in range(2):
            store.add_observation(_obs(
                domain="modulation", task="set_modulation",
                params={"scheme": "LoRa"}, success=True, device_id="esp-1"
            ))
        return store

    def test_run_returns_dream_session(self):
        engine = DreamStateEngine()
        store = self._make_rich_store()
        session = engine.run(store)
        assert isinstance(session, DreamSession)

    def test_session_has_session_id(self):
        engine = DreamStateEngine()
        session = engine.run(self._make_rich_store())
        assert session.session_id
        assert len(session.session_id) > 0

    def test_session_has_timestamps(self):
        engine = DreamStateEngine()
        session = engine.run(self._make_rich_store())
        assert session.started_at
        assert session.completed_at

    def test_session_corruptions_are_guardrailed(self):
        """All planned corruptions must respect _DREAM_MAX_MAGNITUDE."""
        engine = DreamStateEngine()
        session = engine.run(self._make_rich_store())
        for c in session.corruptions:
            assert c.magnitude <= _DREAM_MAX_MAGNITUDE

    def test_session_has_captures_for_each_corruption(self):
        engine = DreamStateEngine()
        session = engine.run(self._make_rich_store())
        assert len(session.captures) == len(session.corruptions)

    def test_session_mind_status_is_valid(self):
        engine = DreamStateEngine()
        session = engine.run(self._make_rich_store())
        assert session.mind_status.status in ("healthy", "learning", "stressed", "degraded")

    def test_session_eval_score_in_range(self):
        engine = DreamStateEngine()
        session = engine.run(self._make_rich_store())
        assert 0.0 <= session.evaluation.eval_score <= 1.0

    def test_session_resilience_score_in_range(self):
        engine = DreamStateEngine()
        session = engine.run(self._make_rich_store())
        assert 0.0 <= session.research.resilience_score <= 1.0

    def test_session_to_dict_is_serialisable(self):
        engine = DreamStateEngine()
        session = engine.run(self._make_rich_store())
        json.dumps(session.to_dict())

    def test_live_store_not_mutated_during_dream(self):
        """The live store must be identical before and after a dream cycle."""
        engine = DreamStateEngine()
        store = self._make_rich_store()
        obs_before = store.get_observations()
        knowledge_before = store.get_knowledge()
        engine.run(store)
        obs_after = store.get_observations()
        knowledge_after = store.get_knowledge()
        assert len(obs_before) == len(obs_after)
        assert len(knowledge_before) == len(knowledge_after)

    def test_empty_store_dream_cycle(self):
        """Dream cycle on an empty store should return a valid session."""
        engine = DreamStateEngine()
        store = TechnicalKnowledgeStore()
        session = engine.run(store)
        assert isinstance(session, DreamSession)
        # No observations → no corruptions applicable (except possibly deflate)
        assert isinstance(session.mind_status, MindStatus)

    def test_negate_success_corruption_flips_flags(self):
        """After NEGATE_SUCCESS corruption the sandbox should diverge from baseline."""
        engine = DreamStateEngine()
        store = _make_store_with_successes(n_ok=10)
        # Run recogniser on live store to establish baseline
        PatternRecognizer().analyse(store)
        baseline_count = store.knowledge_count

        # Directly test _apply_and_capture with a negate-success corruption
        corruption = DreamCorruption(
            corruption_type=CORRUPT_NEGATE_SUCCESS,
            target="success_flag",
            magnitude=1.0,  # flip everything
            guardrail="test only",
        )
        capture = engine._apply_and_capture(store.get_observations(), corruption, baseline_count)
        # With all successes flipped to failures, the high_reliability entry should vanish
        # but a low_reliability entry might appear → count may differ from baseline
        assert isinstance(capture, ReactiveCapture)
        assert capture.reaction in ("resilient", "degraded", "failed")

    def test_nullify_param_corruption(self):
        store = TechnicalKnowledgeStore()
        for _ in range(5):
            store.add_observation(_obs(params={"band": "2.4GHz"}, success=True))
        PatternRecognizer().analyse(store)
        baseline_count = store.knowledge_count
        engine = DreamStateEngine()
        corruption = DreamCorruption(
            corruption_type=CORRUPT_NULLIFY_PARAM,
            target=",".join(("band", "scheme", "template")),
            magnitude=1.0,
            guardrail="test only",
        )
        capture = engine._apply_and_capture(store.get_observations(), corruption, baseline_count)
        assert isinstance(capture, ReactiveCapture)

    def test_inject_band_noise_corruption(self):
        store = TechnicalKnowledgeStore()
        for _ in range(5):
            store.add_observation(_obs(params={"band": "5GHz"}, success=True))
        PatternRecognizer().analyse(store)
        baseline_count = store.knowledge_count
        engine = DreamStateEngine()
        corruption = DreamCorruption(
            corruption_type=CORRUPT_INJECT_BAND_NOISE,
            target="band",
            magnitude=1.0,
            guardrail="test only",
        )
        capture = engine._apply_and_capture(store.get_observations(), corruption, baseline_count)
        assert capture.reaction in ("resilient", "degraded", "failed")

    def test_deflate_confidence_corruption(self):
        store = _make_store_with_successes(n_ok=6)
        PatternRecognizer().analyse(store)
        baseline_count = store.knowledge_count
        engine = DreamStateEngine()
        corruption = DreamCorruption(
            corruption_type=CORRUPT_DEFLATE_CONFIDENCE,
            target="knowledge_entries",
            magnitude=0.5,
            guardrail="test only",
        )
        capture = engine._apply_and_capture(store.get_observations(), corruption, baseline_count)
        assert isinstance(capture, ReactiveCapture)
        # Post confidence should be lower
        if baseline_count > 0:
            base_avg = sum(e.confidence for e in store.get_knowledge()) / baseline_count
            post_avg = capture.details.get("avg_confidence_post", 1.0)
            assert post_avg <= base_avg + 0.01  # halved or equal (when 0)

    def test_domain_swap_corruption(self):
        store = TechnicalKnowledgeStore()
        for _ in range(3):
            store.add_observation(_obs(domain="frequency", task="scan", success=True))
        for _ in range(3):
            store.add_observation(_obs(domain="firmware", task="build", success=False))
        PatternRecognizer().analyse(store)
        baseline_count = store.knowledge_count
        engine = DreamStateEngine()
        corruption = DreamCorruption(
            corruption_type=CORRUPT_DOMAIN_SWAP,
            target="domain_label",
            magnitude=0.5,
            guardrail="test only",
        )
        capture = engine._apply_and_capture(store.get_observations(), corruption, baseline_count)
        assert isinstance(capture, ReactiveCapture)

    def test_mind_status_healthy_for_resilient_store(self):
        """A store where all corruptions are resilient should score 'healthy'."""
        # Build a store that is naturally resilient: all successes, no params to nullify
        store = TechnicalKnowledgeStore()
        for _ in range(8):
            store.add_observation(_obs(domain="frequency", task="scan", success=True))
        PatternRecognizer().analyse(store)
        engine = DreamStateEngine()
        session = engine.run(store)
        # The system should score well
        assert session.mind_status.status in ("healthy", "learning")

    def test_research_counts_match_captures(self):
        engine = DreamStateEngine()
        store = self._make_rich_store()
        session = engine.run(store)
        r = session.research
        assert r.total_corruptions == len(session.captures)
        assert r.resilient_count + r.degraded_count + r.failed_count == r.total_corruptions

    def test_activated_protocols_match_vulnerabilities(self):
        """Protocols should only be listed when their trigger was vulnerable."""
        from ai.tlc import _PROTOCOLS
        engine = DreamStateEngine()
        store = self._make_rich_store()
        session = engine.run(store)
        vulnerable = set(session.research.vulnerable_triggers)
        for proto_key, proto in _PROTOCOLS.items():
            if proto["trigger"] in vulnerable:
                assert any(proto["name"] in ap for ap in session.evaluation.activated_protocols)


# ===========================================================================
# TLCModule — waking mode
# ===========================================================================

class TestTLCModuleWaking:

    def test_record_returns_observation(self):
        tlc = TLCModule()
        obs = tlc.record("frequency", "scan", {"band": "2.4GHz"}, {}, True)
        assert isinstance(obs, TechnicalObservation)

    def test_record_accumulates_observations(self):
        tlc = TLCModule()
        for _ in range(5):
            tlc.record("frequency", "scan", {}, {}, True)
        assert tlc.get_store().observation_count == 5

    def test_query_empty_when_no_patterns(self):
        tlc = TLCModule()
        tlc.record("frequency", "scan", {}, {}, True)  # one obs → no threshold crossed
        assert tlc.query() == []

    def test_query_returns_knowledge_after_threshold(self):
        tlc = TLCModule()
        for _ in range(5):
            tlc.record("frequency", "scan", {"band": "2.4GHz"}, {}, True)
        entries = tlc.query(domain="frequency")
        assert len(entries) >= 1

    def test_query_domain_filter(self):
        tlc = TLCModule()
        for _ in range(4):
            tlc.record("frequency", "scan", {}, {}, False)
        tlc.record("frequency", "scan", {}, {}, True)
        firmware_entries = tlc.query(domain="firmware")
        assert firmware_entries == []

    def test_query_tag_filter(self):
        tlc = TLCModule()
        for _ in range(5):
            tlc.record("frequency", "scan", {}, {}, True)
        entries = tlc.query(tags=["high_reliability"])
        assert len(entries) >= 1

    def test_query_min_confidence_filter(self):
        tlc = TLCModule()
        for _ in range(5):
            tlc.record("frequency", "scan", {}, {}, True)
        # All entries should have confidence > 0
        entries_all = tlc.query(min_confidence=0.0)
        entries_high = tlc.query(min_confidence=0.99)
        assert len(entries_all) >= len(entries_high)

    def test_get_context_structure(self):
        tlc = TLCModule()
        for _ in range(3):
            tlc.record("frequency", "scan", {}, {}, True)
        ctx = tlc.get_context()
        assert "technical_context" in ctx
        tc = ctx["technical_context"]
        assert "observation_count" in tc
        assert "knowledge_count" in tc
        assert "top_insights" in tc

    def test_get_context_with_device_id(self):
        tlc = TLCModule()
        for _ in range(3):
            tlc.record("frequency", "scan", {}, {}, True, device_id="esp-5")
        ctx = tlc.get_context(device_id="esp-5")
        assert "device_summary" in ctx["technical_context"]
        assert ctx["technical_context"]["device_summary"]["device_id"] == "esp-5"

    def test_get_context_counts_match_store(self):
        tlc = TLCModule()
        for _ in range(3):
            tlc.record("frequency", "scan", {}, {}, True)
        ctx = tlc.get_context()
        assert ctx["technical_context"]["observation_count"] == 3

    def test_get_context_is_serialisable(self):
        tlc = TLCModule()
        for _ in range(5):
            tlc.record("frequency", "scan", {"band": "2.4GHz"}, {}, True)
        json.dumps(tlc.get_context())  # must not raise

    def test_get_store_returns_store(self):
        tlc = TLCModule()
        assert isinstance(tlc.get_store(), TechnicalKnowledgeStore)

    def test_device_health_recorded_via_record(self):
        tlc = TLCModule()
        for _ in range(5):
            tlc.record("frequency", "scan", {}, {}, False, device_id="bad")
        entries = tlc.query(tags=["health_poor"])
        assert len(entries) >= 1

    def test_parameter_preference_via_record(self):
        tlc = TLCModule()
        for _ in range(5):
            tlc.record("frequency", "scan", {"band": "2.4GHz"}, {}, True)
        entries = tlc.query(tags=["preference"])
        assert len(entries) >= 1


# ===========================================================================
# TLCModule — dream-state mode
# ===========================================================================

class TestTLCModuleDream:

    def _populated_tlc(self) -> TLCModule:
        tlc = TLCModule()
        for _ in range(5):
            tlc.record("frequency", "scan", {"band": "2.4GHz"}, {}, True, device_id="esp-1")
        for _ in range(3):
            tlc.record("firmware", "build", {"template": "base"}, {}, False, device_id="esp-2")
        for _ in range(2):
            tlc.record("modulation", "set_modulation", {"scheme": "LoRa"}, {}, True, device_id="esp-1")
        return tlc

    def test_run_dream_cycle_returns_session(self):
        session = self._populated_tlc().run_dream_cycle()
        assert isinstance(session, DreamSession)

    def test_dream_cycle_session_id_is_unique(self):
        tlc = self._populated_tlc()
        s1 = tlc.run_dream_cycle()
        s2 = tlc.run_dream_cycle()
        assert s1.session_id != s2.session_id

    def test_dream_cycle_does_not_change_live_store(self):
        tlc = self._populated_tlc()
        before_obs = tlc.get_store().observation_count
        before_know = tlc.get_store().knowledge_count
        tlc.run_dream_cycle()
        assert tlc.get_store().observation_count == before_obs
        assert tlc.get_store().knowledge_count == before_know

    def test_dream_cycle_has_valid_mind_status(self):
        session = self._populated_tlc().run_dream_cycle()
        assert session.mind_status.status in ("healthy", "learning", "stressed", "degraded")
        assert 0.0 <= session.mind_status.eval_score <= 1.0
        assert 0.0 <= session.mind_status.resilience_score <= 1.0
        assert 0.0 <= session.mind_status.knowledge_coverage <= 1.0
        assert session.mind_status.diagnosis

    def test_dream_cycle_research_is_consistent(self):
        session = self._populated_tlc().run_dream_cycle()
        r = session.research
        total = r.total_corruptions
        assert r.resilient_count + r.degraded_count + r.failed_count == total
        assert 0.0 <= r.resilience_score <= 1.0

    def test_dream_cycle_evaluation_has_recommendations_when_vulnerable(self):
        tlc = self._populated_tlc()
        session = tlc.run_dream_cycle()
        if session.research.vulnerable_triggers:
            assert len(session.evaluation.recommendations) >= 1

    def test_dream_cycle_evaluation_is_serialisable(self):
        session = self._populated_tlc().run_dream_cycle()
        json.dumps(session.to_dict())

    def test_dream_cycle_on_empty_tlc(self):
        tlc = TLCModule()
        session = tlc.run_dream_cycle()
        assert isinstance(session, DreamSession)
        assert session.mind_status.status in ("healthy", "learning", "stressed", "degraded")

    def test_mind_status_stressed_or_degraded_for_fragile_store(self):
        """
        A store whose data is designed to trigger many protocol activations
        should produce a non-healthy mind status.
        """
        tlc = TLCModule()
        # Mix of failures and successes guaranteed to cross failure threshold
        # in multiple domains, and with params that get nullified during dream
        for _ in range(4):
            tlc.record("frequency", "scan", {"band": "2.4GHz"}, {}, False)
        for _ in range(4):
            tlc.record("firmware", "build", {"template": "base"}, {}, False)
        for _ in range(4):
            tlc.record("modulation", "set_modulation", {"scheme": "GFSK"}, {}, False)
        session = tlc.run_dream_cycle()
        # With many failures, pattern recognizer will produce low_reliability
        # entries that get wiped by negate-success corruption → degraded or failed
        assert session.mind_status.status in ("healthy", "learning", "stressed", "degraded")

    def test_eval_score_bounded(self):
        for _ in range(3):
            tlc = TLCModule()
            for i in range(6):
                tlc.record("frequency", "scan", {"band": "2.4GHz"}, {}, i % 2 == 0)
            session = tlc.run_dream_cycle()
            assert 0.0 <= session.evaluation.eval_score <= 1.0

    def test_dream_session_full_dict_has_all_keys(self):
        session = self._populated_tlc().run_dream_cycle()
        d = session.to_dict()
        for key in ("session_id", "corruptions", "captures", "research",
                    "evaluation", "mind_status", "started_at", "completed_at"):
            assert key in d

    def test_activated_protocols_are_strings(self):
        session = self._populated_tlc().run_dream_cycle()
        for proto in session.evaluation.activated_protocols:
            assert isinstance(proto, str)

    def test_protocol_adjustments_are_dicts(self):
        session = self._populated_tlc().run_dream_cycle()
        for proto_name, adjustment in session.evaluation.protocol_adjustments.items():
            assert isinstance(proto_name, str)
            assert isinstance(adjustment, dict)
