"""
User Behavioural Profile — per-user rolling state for personalised AI responses.

Statistical foundations
-----------------------
All metrics stored and derived in this module use elementary descriptive
statistics (arithmetic mean, frequency counts, ratio) applied to the
observation window.  No modelling assumptions beyond what the data directly
supports are made.

- **Dominant tone**: mode of the NRC EmoLex category labels across the rolling
  snapshot window — the most frequently occurring category.
- **Average valence**: arithmetic mean of ordinal valence scores
  (positive=+1, neutral=0, negative=−1) across the window, with a
  ±0.2 hysteresis band around zero to avoid spurious polarity flips.
- **Ambiguity rate**: simple proportion — ambiguous prompts / total prompts.
  This is a binomial proportion and is therefore well-defined for any n ≥ 1.
- **Average prompt length**: arithmetic mean of token counts (whitespace-
  delimited words), used as a proxy for the user's preferred verbosity level.

Profile data is derived exclusively from text interactions.  No biometric,
physiological, or real-world sensor data is collected or modelled.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from .emotional_state import EmotionalSnapshot

logger = logging.getLogger(__name__)

# Rolling window size — enough history for stable mode/mean estimates without
# over-weighting the distant past.
_SNAPSHOT_HISTORY_SIZE = 50


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class UserProfile:
    """
    Rolling behavioural profile for a single user, built exclusively from
    text-interaction observations.
    """

    user_id: str
    # Circular buffer of emotional snapshots, oldest evicted first
    snapshots: Deque[EmotionalSnapshot] = field(
        default_factory=lambda: deque(maxlen=_SNAPSHOT_HISTORY_SIZE)
    )
    prompt_count: int = 0
    ambiguous_count: int = 0
    total_words: int = 0
    # "brief" | "moderate" | "detailed" — derived from avg_prompt_length
    explanation_style: str = "unknown"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ------------------------------------------------------------------
    # Derived metrics — all computed from raw observation counts
    # ------------------------------------------------------------------

    @property
    def ambiguity_rate(self) -> float:
        """
        Proportion of prompts classified as ambiguous (binomial proportion).
        Returns 0.0 when no prompts have been observed.
        """
        if self.prompt_count == 0:
            return 0.0
        return self.ambiguous_count / self.prompt_count

    @property
    def dominant_tone(self) -> str:
        """
        Mode of NRC EmoLex category labels across the snapshot window.
        Returns "neutral" when the window is empty.
        """
        if not self.snapshots:
            return "neutral"
        counts: Dict[str, int] = {}
        for snap in self.snapshots:
            counts[snap.dominant_tone] = counts.get(snap.dominant_tone, 0) + 1
        return max(counts, key=lambda k: counts[k])

    @property
    def avg_valence(self) -> str:
        """
        Arithmetic mean of ordinal valence scores across the snapshot window
        (positive=+1, neutral=0, negative=−1), with ±0.2 hysteresis.
        Returns "neutral" when the window is empty.
        """
        if not self.snapshots:
            return "neutral"
        ordinal = {"positive": 1, "neutral": 0, "negative": -1}
        mean = sum(ordinal.get(s.valence, 0) for s in self.snapshots) / len(self.snapshots)
        if mean > 0.2:
            return "positive"
        if mean < -0.2:
            return "negative"
        return "neutral"

    @property
    def avg_prompt_length(self) -> float:
        """
        Arithmetic mean of whitespace-delimited word counts per prompt.
        Returns 0.0 before any prompts are recorded.
        """
        if self.prompt_count == 0:
            return 0.0
        return self.total_words / self.prompt_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "prompt_count": self.prompt_count,
            "ambiguity_rate": round(self.ambiguity_rate, 3),
            "dominant_tone": self.dominant_tone,
            "avg_valence": self.avg_valence,
            "explanation_style": self.explanation_style,
            "avg_prompt_length": round(self.avg_prompt_length, 1),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class UserProfileStore:
    """
    In-memory store of :class:`UserProfile` instances, keyed by ``user_id``.

    All operations are synchronous and re-entrant for single-threaded async
    use.  To persist profiles across restarts, subclass and override
    ``get_or_create`` and add a ``_save`` hook.
    """

    def __init__(self) -> None:
        self._profiles: Dict[str, UserProfile] = {}

    def get_or_create(self, user_id: str) -> UserProfile:
        """Return the existing profile for *user_id*, creating one if absent."""
        if user_id not in self._profiles:
            self._profiles[user_id] = UserProfile(user_id=user_id)
            logger.debug("Created new user profile: %s", user_id)
        return self._profiles[user_id]

    def update(
        self,
        user_id: str,
        snapshot: EmotionalSnapshot,
        prompt: str,
        was_ambiguous: bool,
    ) -> UserProfile:
        """
        Append *snapshot* and update rolling statistics for *user_id*.

        Explanation style is derived from ``avg_prompt_length`` using
        empirically common breakpoints for conversational interfaces:
        - < 8 words  → "brief"
        - 8–25 words → "moderate"
        - > 25 words → "detailed"

        Args:
            user_id:       Target user.
            snapshot:      Inferred :class:`EmotionalSnapshot` for this turn.
            prompt:        Raw user prompt (for word-count accumulation).
            was_ambiguous: Whether this prompt was classified as ambiguous.

        Returns:
            The updated :class:`UserProfile`.
        """
        profile = self.get_or_create(user_id)
        profile.snapshots.append(snapshot)
        profile.prompt_count += 1
        if was_ambiguous:
            profile.ambiguous_count += 1
        profile.total_words += len(prompt.split())
        profile.updated_at = datetime.now(timezone.utc).isoformat()

        avg = profile.avg_prompt_length
        if avg < 8:
            profile.explanation_style = "brief"
        elif avg > 25:
            profile.explanation_style = "detailed"
        else:
            profile.explanation_style = "moderate"

        logger.debug(
            "Updated profile %s | tone=%s | ambiguity_rate=%.3f",
            user_id,
            profile.dominant_tone,
            profile.ambiguity_rate,
        )
        return profile

    def get_rapport_context(self, user_id: str) -> Dict[str, Any]:
        """
        Return a compact, serialisable context dict for injection into
        :class:`~ai.chaimera3sp.CHAiMERA3sp` prompts.

        All values are directly derived from observed interaction data.
        Returns neutral defaults when no profile exists.
        """
        profile = self._profiles.get(user_id)
        if profile is None:
            return {
                "rapport": {
                    "user_id": user_id,
                    "dominant_tone": "neutral",
                    "avg_valence": "neutral",
                    "explanation_style": "moderate",
                    "ambiguity_rate": 0.0,
                    "prompt_count": 0,
                }
            }
        return {
            "rapport": {
                "user_id": user_id,
                "dominant_tone": profile.dominant_tone,
                "avg_valence": profile.avg_valence,
                "explanation_style": profile.explanation_style,
                "ambiguity_rate": round(profile.ambiguity_rate, 3),
                "prompt_count": profile.prompt_count,
            }
        }

    def list_users(self) -> List[str]:
        """Return all user IDs with active profiles."""
        return list(self._profiles.keys())

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """Return the profile for *user_id*, or ``None`` if not found."""
        return self._profiles.get(user_id)
