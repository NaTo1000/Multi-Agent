"""
Tests for the HiAi module: AmbiguityResolver, EmotionalStateModel,
UserProfileStore, and the full HiAiModule pipeline.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai.ambiguity import AmbiguityResolver, AmbiguityResult, Interpretation
from ai.emotional_state import EmotionalStateModel, EmotionalSnapshot
from ai.hiai import HiAiModule, HiAiResult
from ai.user_profile import UserProfile, UserProfileStore


# ---------------------------------------------------------------------------
# AmbiguityResolver
# ---------------------------------------------------------------------------


class TestAmbiguityResolver:

    @pytest.mark.asyncio
    async def test_unambiguous_prompt_returns_false(self):
        """A clear, single-meaning prompt should not be flagged as ambiguous."""
        resolver = AmbiguityResolver()
        # Use a prompt with no high-polysemy words, no bare pronouns, no scope signals
        result: AmbiguityResult = await resolver.resolve(
            "Configure the transmit frequency for the ESP32 module."
        )
        assert not result.was_ambiguous
        assert result.confidence == 1.0
        assert result.selected.rewritten_prompt == "Configure the transmit frequency for the ESP32 module."

    @pytest.mark.asyncio
    async def test_ambiguous_prompt_flags_signals(self):
        """A prompt starting with a bare pronoun and no referent should be ambiguous."""
        resolver = AmbiguityResolver()
        # _BARE_PRONOUN anchors to start of string; lowercase "this" avoids
        # the _EXPLICIT_REFERENT pattern which requires a capital letter.
        result: AmbiguityResult = await resolver.resolve("this is not responding.")
        assert result.was_ambiguous
        assert result.confidence < 1.0
        assert len(result.interpretations) >= 1

    @pytest.mark.asyncio
    async def test_interpretations_ranked_by_confidence(self):
        """Interpretations must be sorted highest confidence first."""
        resolver = AmbiguityResolver()
        result: AmbiguityResult = await resolver.resolve("Can you fix it?")
        confs = [i.confidence for i in result.interpretations]
        assert confs == sorted(confs, reverse=True)

    @pytest.mark.asyncio
    async def test_context_history_resolves_referential_ambiguity(self):
        """Pronoun should be resolved via antecedent in conversation history."""
        resolver = AmbiguityResolver()
        history = ["The frequency agent is running on the ESP32 device."]
        result: AmbiguityResult = await resolver.resolve(
            "it is not responding.", {"history": history}
        )
        # After contextual narrowing the referential signal should be resolved
        assert result.selected.rewritten_prompt != "it is not responding."

    @pytest.mark.asyncio
    async def test_scope_ambiguity_detected(self):
        """Scope ambiguity (negation + quantifier) should be flagged."""
        resolver = AmbiguityResolver()
        result: AmbiguityResult = await resolver.resolve("Not all agents are running.")
        assert result.was_ambiguous

    @pytest.mark.asyncio
    async def test_ellipsis_detected_on_short_verbless_prompt(self):
        """A very short, verb-less fragment should trigger ellipsis detection."""
        resolver = AmbiguityResolver()
        result: AmbiguityResult = await resolver.resolve("the firmware")
        assert result.was_ambiguous

    @pytest.mark.asyncio
    async def test_ai_fallback_on_provider_error(self):
        """When the AI provider raises, rule-based fallback is used."""
        bad_chaimera = MagicMock()
        bad_chaimera.configured_providers = ["watsonx"]
        bad_chaimera.query = AsyncMock(side_effect=RuntimeError("provider down"))
        resolver = AmbiguityResolver(chaimera=bad_chaimera)
        result: AmbiguityResult = await resolver.resolve("Can you fix it?")
        # Fallback must still produce a valid result
        assert isinstance(result, AmbiguityResult)
        assert len(result.interpretations) >= 1


# ---------------------------------------------------------------------------
# EmotionalStateModel
# ---------------------------------------------------------------------------


class TestEmotionalStateModel:

    def test_frustrated_prompt_gives_negative_valence(self):
        model = EmotionalStateModel()
        snap: EmotionalSnapshot = model.infer(
            "This is not working and I'm frustrated. It keeps failing!"
        )
        assert snap.valence == "negative"

    def test_curious_prompt_gives_anticipation_tone(self):
        model = EmotionalStateModel()
        snap: EmotionalSnapshot = model.infer(
            "I wonder how this works. Can you explain how the system decides?"
        )
        assert snap.dominant_tone == "anticipation"

    def test_happy_prompt_gives_positive_valence(self):
        model = EmotionalStateModel()
        snap: EmotionalSnapshot = model.infer("This is fantastic, I love it!")
        assert snap.valence == "positive"

    def test_neutral_prompt_gives_neutral_dominant_tone(self):
        model = EmotionalStateModel()
        snap: EmotionalSnapshot = model.infer("List the current devices.")
        assert snap.dominant_tone == "neutral"

    def test_history_incorporated_in_inference(self):
        """History window should influence the snapshot."""
        model = EmotionalStateModel()
        history = ["I'm so angry this keeps breaking!", "Why doesn't it work?!"]
        snap: EmotionalSnapshot = model.infer(
            "Please help.", history=history
        )
        # History contains anger signals — they should shift the result
        assert snap.emotion_scores.get("anger", 0) > 0

    def test_snapshot_has_required_fields(self):
        model = EmotionalStateModel()
        snap: EmotionalSnapshot = model.infer("Hello there.")
        assert snap.valence in {"positive", "negative", "neutral"}
        assert snap.arousal in {"high", "low"}
        assert snap.dominance in {"dominant", "submissive"}
        assert isinstance(snap.timestamp, str)
        assert snap.source == "nrc_vad_lexicon"

    def test_to_dict_is_serialisable(self):
        model = EmotionalStateModel()
        snap = model.infer("Test serialisation.")
        d = snap.to_dict()
        import json
        json.dumps(d)  # must not raise


# ---------------------------------------------------------------------------
# UserProfileStore
# ---------------------------------------------------------------------------


class TestUserProfileStore:

    def _make_snapshot(self, tone: str = "neutral") -> EmotionalSnapshot:
        from ai.emotional_state import EmotionalSnapshot
        return EmotionalSnapshot(
            valence="neutral", arousal="low", dominance="dominant",
            dominant_tone=tone,
        )

    def test_get_or_create_creates_new_profile(self):
        store = UserProfileStore()
        profile: UserProfile = store.get_or_create("user_1")
        assert profile.user_id == "user_1"
        assert profile.prompt_count == 0

    def test_get_or_create_returns_same_profile(self):
        store = UserProfileStore()
        p1 = store.get_or_create("user_1")
        p2 = store.get_or_create("user_1")
        assert p1 is p2

    def test_update_accumulates_snapshots(self):
        store = UserProfileStore()
        snap = self._make_snapshot("joy")
        store.update("user_1", snap, "hello world", was_ambiguous=False)
        store.update("user_1", snap, "another prompt here", was_ambiguous=True)
        profile = store.get_or_create("user_1")
        assert profile.prompt_count == 2
        assert len(profile.snapshots) == 2

    def test_ambiguity_rate_is_correct(self):
        store = UserProfileStore()
        snap = self._make_snapshot()
        store.update("user_1", snap, "clear prompt", was_ambiguous=False)
        store.update("user_1", snap, "ambiguous one", was_ambiguous=True)
        profile = store.get_or_create("user_1")
        assert abs(profile.ambiguity_rate - 0.5) < 1e-9

    def test_dominant_tone_reflects_majority(self):
        store = UserProfileStore()
        for _ in range(3):
            store.update("user_1", self._make_snapshot("anger"), "prompt", was_ambiguous=False)
        store.update("user_1", self._make_snapshot("joy"), "prompt", was_ambiguous=False)
        profile = store.get_or_create("user_1")
        assert profile.dominant_tone == "anger"

    def test_rapport_context_returns_neutral_defaults_for_unknown_user(self):
        store = UserProfileStore()
        ctx = store.get_rapport_context("unknown_user")
        assert ctx["rapport"]["dominant_tone"] == "neutral"
        assert ctx["rapport"]["prompt_count"] == 0

    def test_rapport_context_reflects_profile(self):
        store = UserProfileStore()
        for _ in range(3):
            store.update("user_1", self._make_snapshot("joy"), "happy prompt", was_ambiguous=False)
        ctx = store.get_rapport_context("user_1")
        assert ctx["rapport"]["dominant_tone"] == "joy"
        assert ctx["rapport"]["prompt_count"] == 3

    def test_explanation_style_brief_for_short_prompts(self):
        store = UserProfileStore()
        # All prompts ≤ 3 words each → avg < 8 → "brief"
        snap = self._make_snapshot()
        for _ in range(5):
            store.update("user_1", snap, "fix it", was_ambiguous=False)
        profile = store.get_or_create("user_1")
        assert profile.explanation_style == "brief"

    def test_explanation_style_detailed_for_long_prompts(self):
        store = UserProfileStore()
        snap = self._make_snapshot()
        long_prompt = " ".join(["word"] * 30)  # 30 words > 25 threshold
        for _ in range(3):
            store.update("user_1", snap, long_prompt, was_ambiguous=False)
        profile = store.get_or_create("user_1")
        assert profile.explanation_style == "detailed"

    def test_list_users_returns_all_ids(self):
        store = UserProfileStore()
        store.get_or_create("alice")
        store.get_or_create("bob")
        assert set(store.list_users()) == {"alice", "bob"}

    def test_get_profile_returns_none_for_unknown(self):
        store = UserProfileStore()
        assert store.get_profile("ghost") is None


# ---------------------------------------------------------------------------
# HiAiModule — end-to-end pipeline
# ---------------------------------------------------------------------------


class TestHiAiModule:

    def _make_mock_chaimera(self, response: str = "MEANING: literal | REWRITE: the device") -> MagicMock:
        mock = MagicMock()
        mock.configured_providers = []  # no real providers → rule-based fallback
        mock.query = AsyncMock(return_value={"response": response, "provider": "mock"})
        return mock

    @pytest.mark.asyncio
    async def test_process_returns_hiai_result(self):
        hiai = HiAiModule()
        result: HiAiResult = await hiai.process(
            prompt="I wonder how it works.",
            user_id="user_1",
        )
        assert isinstance(result, HiAiResult)
        assert isinstance(result.resolved_prompt, str)
        assert result.resolved_prompt  # non-empty

    @pytest.mark.asyncio
    async def test_process_unambiguous_prompt(self):
        hiai = HiAiModule()
        # Prompt with no high-polysemy words or bare pronouns
        result = await hiai.process(
            prompt="Configure the transmit frequency for the ESP32 module.",
            user_id="user_1",
        )
        assert not result.was_ambiguous
        assert result.emotional_snapshot is not None

    @pytest.mark.asyncio
    async def test_process_updates_user_profile(self):
        hiai = HiAiModule()
        await hiai.process("Tell me more about LoRa.", user_id="user_2")
        await hiai.process("Explain the modulation scheme.", user_id="user_2")
        profile_store = hiai.get_profile_store()
        profile = profile_store.get_profile("user_2")
        assert profile is not None
        assert profile.prompt_count == 2

    @pytest.mark.asyncio
    async def test_process_with_conversation_history(self):
        hiai = HiAiModule()
        history = ["The frequency agent is running."]
        result = await hiai.process(
            prompt="it is not responding.",
            user_id="user_3",
            conversation_history=history,
        )
        assert isinstance(result, HiAiResult)

    @pytest.mark.asyncio
    async def test_process_rapport_note_non_empty(self):
        hiai = HiAiModule()
        result = await hiai.process(
            prompt="This is broken and I'm really frustrated!",
            user_id="user_4",
        )
        assert result.rapport_note  # should not be empty
        assert isinstance(result.rapport_note, str)

    @pytest.mark.asyncio
    async def test_process_rapport_context_includes_user_id(self):
        hiai = HiAiModule()
        result = await hiai.process(
            prompt="How do I configure the device?",
            user_id="user_5",
        )
        assert result.rapport_context["rapport"]["user_id"] == "user_5"

    @pytest.mark.asyncio
    async def test_process_with_mock_chaimera(self):
        """Full pipeline with a mocked CHAiMERA3sp that returns AI interpretations."""
        mock_chaimera = self._make_mock_chaimera(
            "MEANING: asking how to configure | REWRITE: How do I configure the device?\n"
            "MEANING: asking for troubleshooting help | REWRITE: Troubleshoot the device configuration."
        )
        mock_chaimera.configured_providers = ["mock"]
        hiai = HiAiModule(chaimera=mock_chaimera)
        result = await hiai.process(
            prompt="Can you set it up?",
            user_id="user_6",
        )
        assert isinstance(result, HiAiResult)
        # Chaimera was provided but prompt "Can you set it up?" contains a bare
        # pronoun — it should have been flagged as ambiguous and AI asked.
        # The mock returns two interpretations.
        assert len(result.interpretations) >= 1

    @pytest.mark.asyncio
    async def test_process_accumulated_ambiguity_rate_in_rapport_note(self):
        """After many ambiguous prompts the rapport note should mention clarification."""
        hiai = HiAiModule()
        # "this is not responding." starts with bare pronoun "this" (lowercase,
        # so it bypasses _EXPLICIT_REFERENT) — reliably detected as ambiguous.
        for i in range(6):
            await hiai.process(
                prompt="this is not responding.",
                user_id="user_7",
            )
        result = await hiai.process(
            prompt="this keeps failing.",
            user_id="user_7",
        )
        # ambiguity_rate should now be > 0.4 with ≥ 3 prompts
        store = hiai.get_profile_store()
        profile = store.get_profile("user_7")
        assert profile.ambiguity_rate > 0.4
        # Rapport note should reference clarification
        assert "clarif" in result.rapport_note.lower() or "ambig" in result.rapport_note.lower()

    @pytest.mark.asyncio
    async def test_process_user_profile_dict_in_result(self):
        hiai = HiAiModule()
        result = await hiai.process("Hello, can you help?", user_id="user_8")
        assert "user_id" in result.user_profile
        assert result.user_profile["user_id"] == "user_8"

    @pytest.mark.asyncio
    async def test_get_profile_store_returns_store(self):
        hiai = HiAiModule()
        store = hiai.get_profile_store()
        assert isinstance(store, UserProfileStore)
