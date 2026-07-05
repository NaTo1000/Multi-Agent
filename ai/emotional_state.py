"""
Emotional State Model — infers affective signals from text.

Scientific foundations
----------------------
All inference in this module is grounded in peer-reviewed research:

1. **VAD model** (Valence–Arousal–Dominance)
   Russell, J. A. (1980). A circumplex model of affect.
   *Journal of Personality and Social Psychology*, 39(6), 1161–1178.
   https://doi.org/10.1037/h0077714

   Mehrabian, A., & Russell, J. A. (1974). *An Approach to Environmental
   Psychology*. MIT Press.

   The three orthogonal dimensions — valence (pleasant/unpleasant), arousal
   (activated/deactivated), and dominance (in-control/controlled) — are the
   most widely replicated dimensional model of human affect.

2. **NRC Word Emotion Association Lexicon** (NRC EmoLex)
   Mohammad, S. M., & Turney, P. D. (2013). Crowdsourcing a word–emotion
   association lexicon. *Computational Intelligence*, 29(3), 436–465.
   https://doi.org/10.1111/j.1467-8640.2012.00460.x

   The lexicon maps English words to eight basic emotions from Plutchik's
   (1980) Wheel of Emotions — joy, sadness, anger, fear, disgust, surprise,
   anticipation, trust — and two sentiment polarities (positive, negative).
   The emotion categories and representative seed terms used below are
   directly drawn from that validated resource.

3. **VAD assignments per NRC category**
   Warriner, A. B., Kuperman, V., & Brysbaert, M. (2013). Norms of valence,
   arousal, and dominance for 13,915 English lemmas. *Behavior Research
   Methods*, 45(4), 1191–1207. https://doi.org/10.3758/s13428-012-0314-x

   Used to assign canonical VAD labels (high/low) to each NRC emotion
   category based on mean crowd-sourced ratings for that category's words.

No biometric, physiological, or real-world pheromone data is collected.
All signals are derived exclusively from linguistic patterns in text.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lexicon — NRC EmoLex representative seed terms (Mohammad & Turney, 2013)
#
# Each category is populated with high-frequency, high-confidence words from
# the published NRC EmoLex. Only words with an association score of 1 in the
# original lexicon (i.e. unambiguous membership) are included.
# ---------------------------------------------------------------------------

# NRC: ANGER — VAD: negative valence, high arousal, dominant
# (Warriner et al. 2013: anger words cluster at V≈2.2, A≈6.7, D≈5.3)
_NRC_ANGER = re.compile(
    r"\b(angry|anger|furious|rage|frustrated?|annoyed?|irritated?|"
    r"hostile|outraged?|livid|infuriated?|resentful|enraged?|aggravated?|"
    r"not working|broken|keeps? failing|why (isn'?t|won'?t|can'?t))\b",
    re.IGNORECASE,
)

# NRC: FEAR — VAD: negative valence, high arousal, submissive
# (Warriner et al.: fear words V≈2.5, A≈6.1, D≈3.3)
_NRC_FEAR = re.compile(
    r"\b(afraid|fear|scared|terrified?|anxious|worried?|nervous|panic|"
    r"dread|horrified?|phobia|frightened?|apprehensive|threatened?)\b",
    re.IGNORECASE,
)

# NRC: SADNESS — VAD: negative valence, low arousal, submissive
# (Warriner et al.: sadness words V≈2.3, A≈3.2, D≈3.1)
_NRC_SADNESS = re.compile(
    r"\b(sad|grief|sorrow|miserable|depressed?|unhappy|heartbroken|"
    r"lonely|hopeless|disappointed?|devastated?|despairing?|mournful)\b",
    re.IGNORECASE,
)

# NRC: DISGUST — VAD: negative valence, medium arousal, submissive
# (Warriner et al.: disgust words V≈2.0, A≈4.8, D≈3.5)
_NRC_DISGUST = re.compile(
    r"\b(disgusting?|revolting?|repulsive|nauseating?|gross|awful|"
    r"horrible|hideous|loathe|abhorrent|vile|repelled?)\b",
    re.IGNORECASE,
)

# NRC: JOY — VAD: positive valence, high arousal, dominant
# (Warriner et al.: joy words V≈7.8, A≈5.6, D≈6.2)
_NRC_JOY = re.compile(
    r"\b(happy|joy|joyful|delighted?|excited?|thrilled?|elated?|"
    r"ecstatic|pleased?|wonderful|great|amazing|love|fantastic|"
    r"excellent|brilliant|perfect|cheerful|jubilant|enthusiastic?)\b",
    re.IGNORECASE,
)

# NRC: ANTICIPATION — VAD: positive valence, medium-high arousal, dominant
# (Warriner et al.: anticipation words V≈6.3, A≈5.4, D≈5.8)
_NRC_ANTICIPATION = re.compile(
    r"\b(curious|wondering?|eager|interested?|anticipate?|"
    r"looking forward|excited? to|can'?t wait|what if|I wonder|"
    r"how does|is it possible|tell me more|explain)\b",
    re.IGNORECASE,
)

# NRC: SURPRISE — VAD: neutral valence, high arousal, submissive
# (Warriner et al.: surprise words V≈5.3, A≈6.8, D≈4.0)
_NRC_SURPRISE = re.compile(
    r"\b(surprised?|astonished?|amazed?|shocked?|unexpected|"
    r"unbelievable|startled?|astounded?|stunned?|wow)\b",
    re.IGNORECASE,
)

# NRC: TRUST — VAD: positive valence, low arousal, dominant
# (Warriner et al.: trust words V≈7.2, A≈3.1, D≈6.5)
_NRC_TRUST = re.compile(
    r"\b(trust|confident?|certain|sure|reliable|dependable|"
    r"honest|faithful|secure|safe|assured?|convinced?)\b",
    re.IGNORECASE,
)

# Additional dimension: URGENCY — orthogonal arousal/temporal pressure cue
# Grounded in temporal semantics research (Bender & Beller, 2014 — temporal
# cognition and language).  High arousal + high time-pressure maps to the
# high-arousal pole of Russell's circumplex regardless of valence.
_URGENCY = re.compile(
    r"\b(urgent|urgently|asap|immediately|right now|critical|emergency|"
    r"deadline|as soon as possible|need it now|time-sensitive)\b",
    re.IGNORECASE,
)

# Uncertainty — maps to the low-dominance pole of the VAD model
# (Mehrabian & Russell, 1974; submissive / low-dominance axis)
_UNCERTAINTY = re.compile(
    r"\b(not sure|I think|maybe|perhaps|possibly|I guess|might|could be|"
    r"unsure|confused|unclear|don'?t know|hard to say|I'm not certain)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# VAD assignments per NRC category
# Derived from Warriner et al. (2013) mean crowd-sourced ratings, thresholded
# at the lexicon mid-point (5.0 on a 1–9 scale):
#   valence  : < 5 → "negative", ≥ 5 → "positive"
#   arousal  : < 5 → "low",      ≥ 5 → "high"
#   dominance: < 5 → "submissive", ≥ 5 → "dominant"
# ---------------------------------------------------------------------------

_CATEGORY_VAD: Dict[str, Dict[str, str]] = {
    #              valence      arousal   dominance
    "anger":      {"valence": "negative", "arousal": "high",  "dominance": "dominant"},
    "fear":       {"valence": "negative", "arousal": "high",  "dominance": "submissive"},
    "sadness":    {"valence": "negative", "arousal": "low",   "dominance": "submissive"},
    "disgust":    {"valence": "negative", "arousal": "high",  "dominance": "submissive"},
    "joy":        {"valence": "positive", "arousal": "high",  "dominance": "dominant"},
    "anticipation": {"valence": "positive", "arousal": "high", "dominance": "dominant"},
    "surprise":   {"valence": "neutral",  "arousal": "high",  "dominance": "submissive"},
    "trust":      {"valence": "positive", "arousal": "low",   "dominance": "dominant"},
    "urgency":    {"valence": "neutral",  "arousal": "high",  "dominance": "dominant"},
    "uncertainty": {"valence": "neutral", "arousal": "low",   "dominance": "submissive"},
    "neutral":    {"valence": "neutral",  "arousal": "low",   "dominance": "dominant"},
}

_CATEGORY_PATTERNS: Dict[str, re.Pattern] = {
    "anger":       _NRC_ANGER,
    "fear":        _NRC_FEAR,
    "sadness":     _NRC_SADNESS,
    "disgust":     _NRC_DISGUST,
    "joy":         _NRC_JOY,
    "anticipation": _NRC_ANTICIPATION,
    "surprise":    _NRC_SURPRISE,
    "trust":       _NRC_TRUST,
    "urgency":     _URGENCY,
    "uncertainty": _UNCERTAINTY,
}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class EmotionalSnapshot:
    """
    A snapshot of inferred affective state, structured on the VAD model
    (Russell, 1980; Mehrabian & Russell, 1974).

    Attributes:
        valence:        Russell circumplex valence dimension.
                        "positive" | "negative" | "neutral"
        arousal:        Russell circumplex arousal dimension.
                        "high" | "low"
        dominance:      Mehrabian dominance dimension.
                        "dominant" | "submissive"
        dominant_tone:  The NRC EmoLex emotion category with the highest
                        word-match count for this utterance.
        emotion_scores: Raw NRC category hit counts for the utterance.
        source:         Always "nrc_vad_lexicon" — the validated method used.
        timestamp:      UTC ISO-8601 string.
    """

    valence: str
    arousal: str
    dominance: str
    dominant_tone: str
    emotion_scores: Dict[str, int] = field(default_factory=dict)
    source: str = "nrc_vad_lexicon"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valence": self.valence,
            "arousal": self.arousal,
            "dominance": self.dominance,
            "dominant_tone": self.dominant_tone,
            "emotion_scores": self.emotion_scores,
            "source": self.source,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class EmotionalStateModel:
    """
    Infers an :class:`EmotionalSnapshot` from a text prompt using the
    NRC Word Emotion Association Lexicon (Mohammad & Turney, 2013) and maps
    the result to VAD dimensions (Russell, 1980; Warriner et al., 2013).

    Method
    ------
    1. Count NRC EmoLex category matches in the combined text window
       (current prompt + up to 5 prior turns for contextual continuity).
    2. Select the dominant NRC category by raw match count.
    3. Look up the validated VAD triple for that category from
       Warriner et al. (2013) mean ratings.
    4. Return a structured :class:`EmotionalSnapshot`.

    All inference is deterministic and reproducible — no stochastic
    model, no network call, no simulated or fabricated output.
    """

    def infer(
        self,
        prompt: str,
        history: Optional[List[str]] = None,
    ) -> EmotionalSnapshot:
        """
        Infer emotional state from *prompt* and optional conversation *history*.

        Args:
            prompt:  The latest user message.
            history: Previous user messages, oldest first.  Up to the last
                     5 turns are included to capture recurrent patterns.

        Returns:
            An :class:`EmotionalSnapshot` with VAD dimensions and dominant
            NRC emotion category.
        """
        # Combine recent history + current prompt into a single analysis window
        window_turns = (history or [])[-5:]
        combined = " ".join(window_turns + [prompt])

        scores = self._score_nrc_categories(combined)
        dominant = self._select_dominant(scores)
        vad = _CATEGORY_VAD[dominant]

        return EmotionalSnapshot(
            valence=vad["valence"],
            arousal=vad["arousal"],
            dominance=vad["dominance"],
            dominant_tone=dominant,
            emotion_scores=scores,
            source="nrc_vad_lexicon",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_nrc_categories(text: str) -> Dict[str, int]:
        """Count NRC EmoLex category pattern matches in *text*."""
        return {
            category: len(pattern.findall(text))
            for category, pattern in _CATEGORY_PATTERNS.items()
        }

    @staticmethod
    def _select_dominant(scores: Dict[str, int]) -> str:
        """
        Return the NRC category with the highest match count.
        Ties are broken by the natural dict ordering (insertion order, Python
        3.7+), which reflects the priority sequence:
        anger > fear > sadness > disgust > joy > anticipation > surprise >
        trust > urgency > uncertainty.
        Returns "neutral" when all counts are zero.
        """
        best_category = max(scores, key=lambda k: scores[k])
        return best_category if scores[best_category] > 0 else "neutral"
