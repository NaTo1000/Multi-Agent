"""
HiAi Module — Human-Intelligence Augmented AI coordinator.

Combines the three scientifically grounded sub-systems into a single
processing pipeline applied before every AI query:

1. :class:`~ai.emotional_state.EmotionalStateModel`
   NRC EmoLex + VAD model (Russell 1980; Mohammad & Turney 2013)

2. :class:`~ai.user_profile.UserProfileStore`
   Per-user rolling behavioural profile (descriptive statistics)

3. :class:`~ai.ambiguity.AmbiguityResolver`
   Grice (1975) Cooperative Principle + NLP ambiguity taxonomy

The module is stateless in itself — all persistent state is owned by
:class:`~ai.user_profile.UserProfileStore`.

Pipeline
--------
For a given (prompt, user_id, conversation_history):

    Step 1  Infer emotional state from the raw prompt.
    Step 2  Fetch the user's rapport context from the profile store.
    Step 3  Resolve ambiguity in the prompt using history + rapport context.
    Step 4  Update the user's profile with the new snapshot + resolution.
    Step 5  Return a :class:`HiAiResult` containing:
              - resolved_prompt       (disambiguated prompt)
              - interpretations       (ranked candidate interpretations)
              - emotional_snapshot    (VAD-structured snapshot)
              - rapport_note          (plain-English tone guidance for the AI)
              - rapport_context       (structured profile context dict)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .emotional_state import EmotionalStateModel, EmotionalSnapshot
from .user_profile import UserProfile, UserProfileStore
from .ambiguity import AmbiguityResolver, AmbiguityResult, Interpretation

if TYPE_CHECKING:
    from .chaimera3sp import CHAiMERA3sp

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class HiAiResult:
    """
    The output of one :meth:`HiAiModule.process` call.

    Attributes:
        resolved_prompt:     Disambiguated prompt ready for the AI provider.
        interpretations:     Ranked list of candidate interpretations
                             (empty when the prompt was unambiguous).
        was_ambiguous:       True when at least one ambiguity signal was found.
        emotional_snapshot:  VAD-structured emotional state for this turn.
        rapport_context:     Structured context dict from the user's profile,
                             suitable for injection into a CHAiMERA3sp query.
        rapport_note:        Plain-English tone-adaptation note for the AI
                             response (derived from profile + snapshot).
        user_profile:        Serialisable snapshot of the updated user profile.
    """

    resolved_prompt: str
    interpretations: List[Interpretation]
    was_ambiguous: bool
    emotional_snapshot: EmotionalSnapshot
    rapport_context: Dict[str, Any]
    rapport_note: str
    user_profile: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Rapport note generator
# ---------------------------------------------------------------------------

def _build_rapport_note(
    snapshot: EmotionalSnapshot,
    profile: UserProfile,
) -> str:
    """
    Produce a short, plain-English instruction the AI can use to adapt its
    response tone to the inferred user state.

    The note is derived entirely from the VAD dimensions and profile
    statistics — no invented or simulated values.
    """
    parts: List[str] = []

    # Valence guidance
    if snapshot.valence == "negative":
        parts.append("Respond with empathy; the user shows signs of frustration or distress.")
    elif snapshot.valence == "positive":
        parts.append("Match the user's positive energy with an enthusiastic tone.")

    # Arousal / urgency guidance
    if snapshot.arousal == "high" and snapshot.dominant_tone in ("urgency", "anger", "fear"):
        parts.append("Be concise and direct — high arousal detected.")
    elif snapshot.arousal == "low":
        parts.append("A calm, measured response is appropriate.")

    # Dominance / uncertainty guidance
    if snapshot.dominance == "submissive":
        parts.append("Provide clear, reassuring explanations to support confidence.")

    # Verbosity preference from profile
    style = profile.explanation_style
    if style == "brief":
        parts.append("Keep the response brief (user prefers short answers).")
    elif style == "detailed":
        parts.append("Provide a thorough explanation (user prefers detailed responses).")

    # Ambiguity rate note
    if profile.ambiguity_rate > 0.4 and profile.prompt_count >= 3:
        parts.append(
            "This user's prompts are often ambiguous — "
            "consider asking a clarifying question if the intent is unclear."
        )

    return "  ".join(parts) if parts else "Respond in a neutral, helpful tone."


# ---------------------------------------------------------------------------
# HiAi Module
# ---------------------------------------------------------------------------


class HiAiModule:
    """
    Human-Intelligence Augmented AI — pre-processing coordinator.

    Instantiate once and reuse across requests.  All sub-system instances
    are owned by this module and shared across calls.

    Args:
        chaimera:  Optional :class:`~ai.chaimera3sp.CHAiMERA3sp` instance.
                   When provided, the :class:`~ai.ambiguity.AmbiguityResolver`
                   will use it to generate richer candidate interpretations for
                   ambiguous prompts.
        profile_store: Optional external :class:`~ai.user_profile.UserProfileStore`.
                       Provide one to share profile state with other components.
    """

    def __init__(
        self,
        chaimera: Optional["CHAiMERA3sp"] = None,
        profile_store: Optional[UserProfileStore] = None,
    ) -> None:
        self._emotion_model = EmotionalStateModel()
        self._profile_store = profile_store or UserProfileStore()
        self._resolver = AmbiguityResolver(chaimera=chaimera)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process(
        self,
        prompt: str,
        user_id: str,
        conversation_history: Optional[List[str]] = None,
    ) -> HiAiResult:
        """
        Run the full HiAi pipeline for one user turn.

        Args:
            prompt:               Raw user message.
            user_id:              Stable identifier for the user.
            conversation_history: Prior user messages, oldest first.
                                  Used by both emotion inference and
                                  ambiguity resolution.

        Returns:
            A :class:`HiAiResult` with the resolved prompt and all
            supporting signals.
        """
        history = conversation_history or []

        # Step 1 — infer emotional state (NRC EmoLex + VAD)
        snapshot = self._emotion_model.infer(prompt, history)

        # Step 2 — fetch rapport context from profile store
        rapport_ctx = self._profile_store.get_rapport_context(user_id)
        profile = self._profile_store.get_or_create(user_id)

        # Step 3 — resolve ambiguity
        user_context: Dict[str, Any] = {
            "history": history,
            "rapport": rapport_ctx.get("rapport", {}),
        }
        ambiguity_result: AmbiguityResult = await self._resolver.resolve(
            prompt, user_context
        )

        # Step 4 — update user profile
        updated_profile = self._profile_store.update(
            user_id=user_id,
            snapshot=snapshot,
            prompt=prompt,
            was_ambiguous=ambiguity_result.was_ambiguous,
        )

        # Step 5 — build rapport note and assemble result
        rapport_note = _build_rapport_note(snapshot, updated_profile)

        logger.info(
            "HiAi processed | user=%s | tone=%s | valence=%s | ambiguous=%s",
            user_id,
            snapshot.dominant_tone,
            snapshot.valence,
            ambiguity_result.was_ambiguous,
        )

        return HiAiResult(
            resolved_prompt=ambiguity_result.selected.rewritten_prompt,
            interpretations=ambiguity_result.interpretations,
            was_ambiguous=ambiguity_result.was_ambiguous,
            emotional_snapshot=snapshot,
            rapport_context=rapport_ctx,
            rapport_note=rapport_note,
            user_profile=updated_profile.to_dict(),
        )

    def get_profile_store(self) -> UserProfileStore:
        """Return the underlying :class:`~ai.user_profile.UserProfileStore`."""
        return self._profile_store
