"""
Emotional State Model — infers affective/behavioural signals from text.

Analyses user prompt patterns to derive a lightweight emotional snapshot
using heuristic keyword matching.  No biometric or physiological data is
ever collected; all signals are derived exclusively from linguistic cues in
text interactions.

When a ``CHAiMERA3sp`` instance is supplied the model can optionally
delegate richer inference to a configured AI provider for prompts that
don't trigger any heuristic pattern.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .chaimera3sp import CHAiMERA3sp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Heuristic signal patterns
# ---------------------------------------------------------------------------

_FRUSTRATION_PATTERNS = re.compile(
    r"\b(frustrated?|annoyed?|stuck|broken|not working|doesn'?t work|"
    r"keeps? failing|why (isn'?t|won'?t|can'?t)|ugh|argh|!!+)\b",
    re.IGNORECASE,
)
_CURIOSITY_PATTERNS = re.compile(
    r"\b(how does|what if|I wonder|curious|explain|why does|could you|"
    r"tell me more|what is|is it possible)\b",
    re.IGNORECASE,
)
_ENTHUSIASM_PATTERNS = re.compile(
    r"\b(great|awesome|love|excited|amazing|brilliant|perfect|excellent|"
    r"fantastic|wonderful|let'?s go|can'?t wait)\b",
    re.IGNORECASE,
)
_URGENCY_PATTERNS = re.compile(
    r"\b(urgent|asap|immediately|right now|critical|emergency|hurry|"
    r"as soon as possible|need it now|deadline)\b",
    re.IGNORECASE,
)
_UNCERTAINTY_PATTERNS = re.compile(
    r"\b(not sure|I think|maybe|perhaps|possibly|I guess|might|could be|"
    r"unsure|confused|unclear|don'?t know|hard to say)\b",
    re.IGNORECASE,
)

_TONE_PRIORITY = ["frustrated", "urgent", "enthusiastic", "curious", "uncertain", "neutral"]


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class EmotionalSnapshot:
    """
    A lightweight snapshot of inferred emotional state at a point in time.

    Attributes:
        valence:        "positive", "negative", or "neutral"
        arousal:        "high" (energetic/urgent) or "low" (calm/disengaged)
        dominance:      "confident" or "uncertain"
        dominant_tone:  Most salient detected tone label
        tone_scores:    Raw heuristic scores per tone category
        source:         "heuristic" or "chaimera3sp"
        timestamp:      UTC ISO-8601 string
    """

    valence: str
    arousal: str
    dominance: str
    dominant_tone: str
    tone_scores: Dict[str, int] = field(default_factory=dict)
    source: str = "heuristic"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valence": self.valence,
            "arousal": self.arousal,
            "dominance": self.dominance,
            "dominant_tone": self.dominant_tone,
            "tone_scores": self.tone_scores,
            "source": self.source,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class EmotionalStateModel:
    """
    Infers an :class:`EmotionalSnapshot` from a text prompt and optional
    conversation history.

    Pipeline:
    1. Run lightweight heuristic keyword/pattern matching.
    2. If no strong signal is detected **and** a CHAiMERA3sp instance is
       configured, delegate to the AI provider for deeper analysis.
    3. Return a structured :class:`EmotionalSnapshot`.
    """

    # Minimum match count to consider a heuristic signal "strong"
    STRONG_SIGNAL_THRESHOLD = 2

    def __init__(self, chaimera: Optional["CHAiMERA3sp"] = None) -> None:
        self._chaimera = chaimera

    def infer(
        self,
        prompt: str,
        history: Optional[List[str]] = None,
    ) -> EmotionalSnapshot:
        """
        Infer emotional state from *prompt* and optional conversation *history*.

        Args:
            prompt:  The latest user message.
            history: Previous user messages, oldest first (used to pick up
                     recurrent patterns across the conversation).

        Returns:
            An :class:`EmotionalSnapshot` describing the inferred state.
        """
        combined = prompt
        if history:
            combined = " ".join(history[-5:]) + " " + prompt  # use last 5 turns

        scores = self._heuristic_scores(combined)
        dominant = self._dominant_tone(scores)
        snapshot = self._build_snapshot(scores, dominant, source="heuristic")

        total_signals = sum(scores.values())
        if total_signals < self.STRONG_SIGNAL_THRESHOLD and self._chaimera:
            ai_snapshot = self._infer_via_ai(prompt, history)
            if ai_snapshot is not None:
                return ai_snapshot

        return snapshot

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _heuristic_scores(self, text: str) -> Dict[str, int]:
        return {
            "frustrated": len(_FRUSTRATION_PATTERNS.findall(text)),
            "curious": len(_CURIOSITY_PATTERNS.findall(text)),
            "enthusiastic": len(_ENTHUSIASM_PATTERNS.findall(text)),
            "urgent": len(_URGENCY_PATTERNS.findall(text)),
            "uncertain": len(_UNCERTAINTY_PATTERNS.findall(text)),
        }

    def _dominant_tone(self, scores: Dict[str, int]) -> str:
        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] > 0 else "neutral"

    def _build_snapshot(
        self,
        scores: Dict[str, int],
        dominant: str,
        source: str,
    ) -> EmotionalSnapshot:
        valence = "neutral"
        if dominant in ("enthusiastic",):
            valence = "positive"
        elif dominant in ("frustrated", "urgent"):
            valence = "negative"

        arousal = "low"
        if dominant in ("urgent", "enthusiastic", "frustrated"):
            arousal = "high"

        dominance = "uncertain" if dominant in ("uncertain",) else "confident"

        return EmotionalSnapshot(
            valence=valence,
            arousal=arousal,
            dominance=dominance,
            dominant_tone=dominant,
            tone_scores=dict(scores),
            source=source,
        )

    def _infer_via_ai(
        self,
        prompt: str,
        history: Optional[List[str]],
    ) -> Optional[EmotionalSnapshot]:
        """
        Ask CHAiMERA3sp to classify the emotional tone.
        Returns None on any failure so the caller can fall back to heuristics.
        """
        import asyncio
        import json

        system_prompt = (
            "You are an emotional intelligence classifier. "
            "Analyse the following user message and return a JSON object with keys: "
            "valence (positive|negative|neutral), arousal (high|low), "
            "dominance (confident|uncertain), dominant_tone (one word label). "
            "Return ONLY valid JSON, no extra text.\n\n"
            f"Message: {prompt}"
        )
        if history:
            system_prompt += f"\n\nRecent context: {' | '.join(history[-3:])}"

        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                self._chaimera.query(system_prompt, context={"task": "emotion_inference"})
            )
            raw = result.get("response", "")
            # Strip markdown code fences if present
            raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
            data = json.loads(raw)
            return EmotionalSnapshot(
                valence=data.get("valence", "neutral"),
                arousal=data.get("arousal", "low"),
                dominance=data.get("dominance", "confident"),
                dominant_tone=data.get("dominant_tone", "neutral"),
                tone_scores={},
                source="chaimera3sp",
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug("AI emotion inference failed, using heuristics: %s", exc)
            return None
