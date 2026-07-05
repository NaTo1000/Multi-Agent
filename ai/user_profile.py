"""
User Behavioural Profile — per-user rolling state for personalised AI responses.

Stores an in-memory profile for each user that accumulates:
- Recent emotional snapshots
- Vocabulary and prompt-length preferences
- Ambiguity rate (fraction of prompts that were classified as ambiguous)
- Dominant tone trend across the conversation
- Inferred preferred explanation style

The profile is used by :class:`~ai.hiai.HiAiModule` to inject rapport
context into every :class:`~ai.chaimera3sp.CHAiMERA3sp` query, subtly
adapting the AI's tone and word choices to the individual user.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from .emotional_state import EmotionalSnapshot

logger = logging.getLogger(__name__)

# How many emotional snapshots to keep per user
_SNAPSHOT_HISTORY_SIZE = 50


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class UserProfile:
    """
    Rolling behavioural profile for a single user.

    All data is derived exclusively from text-interaction patterns.
    """

    user_id: str
    # Circular buffer of emotional snapshots, most recent last
    snapshots: Deque[EmotionalSnapshot] = field(
        default_factory=lambda: deque(maxlen=_SNAPSHOT_HISTORY_SIZE)
    )
    # Total prompts seen
    prompt_count: int = 0
    # Prompts classified as ambiguous
    ambiguous_count: int = 0
    # Accumulated word counts for vocabulary size estimation
    total_words: int = 0
    # Preferred explanation style: "brief" | "detailed" | "unknown"
    explanation_style: str = "unknown"
    # ISO-8601 timestamp of first interaction
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    # ISO-8601 timestamp of last update
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def ambiguity_rate(self) -> float:
        """Fraction of prompts that were ambiguous (0.0 – 1.0)."""
        if self.prompt_count == 0:
            return 0.0
        return self.ambiguous_count / self.prompt_count

    @property
    def dominant_tone(self) -> str:
        """Most frequently occurring tone across recent snapshots."""
        if not self.snapshots:
            return "neutral"
        counts: Dict[str, int] = {}
        for snap in self.snapshots:
            counts[snap.dominant_tone] = counts.get(snap.dominant_tone, 0) + 1
        return max(counts, key=lambda k: counts[k])

    @property
    def avg_valence(self) -> str:
        """
        Average valence of the last N snapshots.
        Returns "positive", "negative", or "neutral".
        """
        if not self.snapshots:
            return "neutral"
        scores = {"positive": 1, "neutral": 0, "negative": -1}
        avg = sum(scores.get(s.valence, 0) for s in self.snapshots) / len(self.snapshots)
        if avg > 0.2:
            return "positive"
        if avg < -0.2:
            return "negative"
        return "neutral"

    @property
    def avg_prompt_length(self) -> float:
        """Average words per prompt."""
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
    In-memory store of :class:`UserProfile` instances.

    All methods are synchronous and thread-safe for single-threaded async
    use.  To persist profiles across restarts, subclass and override
    ``get_or_create`` / ``_save``.
    """

    def __init__(self) -> None:
        self._profiles: Dict[str, UserProfile] = {}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get_or_create(self, user_id: str) -> UserProfile:
        """Return the existing profile for *user_id*, or create a blank one."""
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
        Append an :class:`EmotionalSnapshot` and update rolling statistics.

        Args:
            user_id:       The user whose profile to update.
            snapshot:      The inferred emotional state for this turn.
            prompt:        The raw user prompt (used for length statistics).
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

        # Infer preferred explanation style from prompt length trend
        avg = profile.avg_prompt_length
        if avg < 8:
            profile.explanation_style = "brief"
        elif avg > 25:
            profile.explanation_style = "detailed"
        else:
            profile.explanation_style = "moderate"

        logger.debug(
            "Updated profile %s | tone=%s | ambiguity_rate=%.2f",
            user_id,
            profile.dominant_tone,
            profile.ambiguity_rate,
        )
        return profile

    def get_rapport_context(self, user_id: str) -> Dict[str, Any]:
        """
        Return a compact context dict that can be injected into a
        :class:`~ai.chaimera3sp.CHAiMERA3sp` prompt to personalise the
        AI's tone and verbosity for this user.

        If the user has no profile yet, returns a neutral/default context.
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
        """Return all known user IDs."""
        return list(self._profiles.keys())

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """Return the profile for *user_id*, or ``None`` if not found."""
        return self._profiles.get(user_id)
