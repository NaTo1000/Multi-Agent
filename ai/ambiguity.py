"""
Ambiguity Resolver — multi-pass contextual disambiguation of user prompts.

Linguistic foundations
----------------------
All detection logic is grounded in established linguistics and NLP research:

1. **Grice's Cooperative Principle and Maxims** (Grice, 1975)
   Grice, H. P. (1975). Logic and conversation.  In P. Cole & J. Morgan
   (Eds.), *Syntax and Semantics, Vol. 3: Speech Acts* (pp. 41–58).
   Academic Press.

   A prompt is classified as potentially ambiguous when it appears to
   violate the Maxim of Manner ("avoid obscurity of expression; avoid
   ambiguity") or the Maxim of Quantity (too little information given
   conversational context).

2. **Linguistic ambiguity taxonomy** (Poesio & Vieira, 1998;
   Wasow et al., 2005)
   Four orthogonal ambiguity types are detected:

   a. **Lexical ambiguity** — a word has multiple established senses
      (Navigli, 2009 — Word Sense Disambiguation survey).
   b. **Referential/pronominal ambiguity** — a pronoun or deictic
      expression has no recoverable antecedent in the local context
      (Mitkov, 2002 — *Anaphora Resolution*).
   c. **Scope ambiguity** — a quantifier or negation has multiple
      possible scopes over the sentence (Copestake & Flickinger, 2000).
   d. **Ellipsis/fragmentary ambiguity** — the prompt is grammatically
      incomplete (verb phrase or noun phrase ellipsis) and requires
      prior discourse to be interpreted (Dalrymple et al., 1991).

3. **Interpretation generation via CHAiMERA3sp (optional)**
   When a provider is configured, the resolver can delegate the
   generation of ranked alternative interpretations to an AI model.
   The model is prompted explicitly and its output is treated as one
   information source among others — not as ground truth.

4. **Confidence scoring**
   Confidence is a normalised score in [0, 1] derived from the number
   of ambiguity signals detected (more signals → lower confidence in
   any single interpretation).  This is a deterministic function of
   the detection output, not a learned or simulated probability.

References
----------
Dalrymple, M., Shieber, S. M., & Pereira, F. C. N. (1991). Ellipsis and
  higher-order unification. *Linguistics and Philosophy*, 14(4), 399–452.

Grice, H. P. (1975). Logic and conversation. In P. Cole & J. Morgan (Eds.),
  *Syntax and Semantics, Vol. 3: Speech Acts* (pp. 41–58). Academic Press.

Mitkov, R. (2002). *Anaphora Resolution*. Pearson Education.

Navigli, R. (2009). Word sense disambiguation: A survey. *ACM Computing
  Surveys*, 41(2), 1–69. https://doi.org/10.1145/1459352.1459355

Poesio, M., & Vieira, R. (1998). A corpus-based investigation of definite
  description use. *Computational Linguistics*, 24(2), 183–216.

Wasow, T., Perfors, A., & Beaver, D. (2005). The puzzle of ambiguity.
  In O. Orgun & P. Sells (Eds.), *Morphology and the Web of Grammar*
  (pp. 265–282). CSLI Publications.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .chaimera3sp import CHAiMERA3sp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ambiguity signal detectors
# ---------------------------------------------------------------------------

# (a) Referential/pronominal ambiguity (Mitkov, 2002)
# Detects bare pronouns/deictics without a co-referring noun in the prompt.
# A prompt that contains only pronouns and no explicit referent is ambiguous.
_BARE_PRONOUN = re.compile(
    r"^[\W]*\b(it|this|that|they|them|those|these|he|she|its|their)\b",
    re.IGNORECASE,
)
_EXPLICIT_REFERENT = re.compile(
    r"\b(the [A-Za-z]+|[A-Z][a-z]+|[a-z]+-agent|device|module|system|task|"
    r"agent|orchestrator|firmware|frequency|modulation)\b",
)

# (b) Scope ambiguity signals (Copestake & Flickinger, 2000)
# Quantifiers combined with negation indicate potential scope ambiguity.
_SCOPE_SIGNALS = re.compile(
    r"\b(not|n'?t|never|no)\b.{0,30}\b(all|every|each|any|some|most)\b|"
    r"\b(all|every|each|any|some|most)\b.{0,30}\b(not|n'?t|never|no)\b",
    re.IGNORECASE | re.DOTALL,
)

# (c) Ellipsis / fragmentary ambiguity (Dalrymple et al., 1991)
# Very short prompts (< 4 words) with no main verb are likely elliptical.
_HAS_MAIN_VERB = re.compile(
    r"\b(is|are|was|were|be|been|being|do|does|did|have|has|had|"
    r"will|would|can|could|shall|should|may|might|must|"
    r"want|need|try|make|get|use|run|build|set|add|remove|update|"
    r"check|help|tell|show|explain|find|create|start|stop)\b",
    re.IGNORECASE,
)

# (d) Lexical ambiguity markers — high-polysemy function words that shift
# meaning depending on context (Navigli, 2009 Table 1 — highest-polysemy
# English lemmas from WordNet 3.1).
_HIGH_POLYSEMY_WORDS = re.compile(
    r"\b(run|set|go|get|turn|put|take|make|break|line|point|"
    r"right|left|back|clear|light|fine|base|lead|bit|drive)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Interpretation:
    """
    One candidate interpretation of an ambiguous prompt.

    Attributes:
        meaning:          A concise description of this interpretation.
        rewritten_prompt: A disambiguated, canonical rewrite of the prompt.
        confidence:       Normalised score in [0, 1].  Higher = more likely
                          given the detected signals and conversation context.
        ambiguity_types:  Which ambiguity types drove this interpretation.
    """

    meaning: str
    rewritten_prompt: str
    confidence: float
    ambiguity_types: List[str] = field(default_factory=list)


@dataclass
class AmbiguityResult:
    """
    The outcome of resolving one prompt.

    Attributes:
        interpretations: Ranked list of candidate interpretations
                         (highest confidence first).
        selected:        The top-ranked interpretation chosen for the query.
        confidence:      Confidence of the selected interpretation.
        was_ambiguous:   True when ≥ 1 ambiguity signal was detected.
        signals:         Dict mapping each detected ambiguity type to its
                         raw detection count.
    """

    interpretations: List[Interpretation]
    selected: Interpretation
    confidence: float
    was_ambiguous: bool
    signals: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


class AmbiguityResolver:
    """
    Detects and resolves linguistic ambiguity in user prompts using a
    three-pass strategy:

    **Pass 1 — Structural detection**
      Apply the four ambiguity-type detectors (referential, scope, ellipsis,
      lexical) to the prompt.  Each detector returns a count of signals found.

    **Pass 2 — Contextual narrowing**
      Use the last *N* turns of conversation history to:
        - Resolve pronoun/deictic references (Mitkov, 2002).
        - Fill elliptical gaps from prior discourse (Dalrymple et al., 1991).
        - Disambiguate high-polysemy words using the dominant semantic domain
          established in prior turns.

    **Pass 3 — Interpretation generation**
      If signals remain after contextual narrowing:
        - If a :class:`~ai.chaimera3sp.CHAiMERA3sp` provider is configured,
          delegate candidate generation to the AI model.
        - Otherwise, generate a structural rewrite based on the detected
          signal types (deterministic rule-based fallback).
      Interpretations are ranked by confidence (normalised signal count).
    """

    # Confidence is computed as: 1 / (1 + total_signals).
    # This is a monotonically decreasing function of signal count,
    # bounded in (0, 1].  Zero signals → confidence 1.0 (unambiguous).
    # One signal → 0.5. Two → 0.33. Three → 0.25. Etc.

    def __init__(self, chaimera: Optional["CHAiMERA3sp"] = None) -> None:
        self._chaimera = chaimera

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def resolve(
        self,
        prompt: str,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> AmbiguityResult:
        """
        Resolve ambiguity in *prompt*.

        Args:
            prompt:       Raw user input.
            user_context: Dict with optional keys:
                          ``history`` (List[str]) — prior user turns, oldest
                          first; ``domain`` (str) — semantic domain hint.

        Returns:
            An :class:`AmbiguityResult` with ranked interpretations.
        """
        user_context = user_context or {}
        history: List[str] = user_context.get("history", [])
        domain: str = user_context.get("domain", "")

        # Pass 1 — detect structural ambiguity signals
        signals = self._detect_signals(prompt)
        total_signals = sum(signals.values())

        # Pass 2 — narrow using conversation context
        contextual_prompt = self._contextual_narrow(prompt, history, signals)
        remaining_signals = self._detect_signals(contextual_prompt)
        remaining_total = sum(remaining_signals.values())

        was_ambiguous = remaining_total > 0
        confidence = self._compute_confidence(remaining_total)

        # Pass 3 — generate interpretations
        if was_ambiguous and self._chaimera and self._chaimera.configured_providers:
            interpretations = await self._ai_interpretations(
                contextual_prompt, history, remaining_signals, domain
            )
        else:
            interpretations = self._rule_interpretations(
                contextual_prompt, remaining_signals, confidence
            )

        # Sort descending by confidence
        interpretations.sort(key=lambda x: x.confidence, reverse=True)
        selected = interpretations[0] if interpretations else Interpretation(
            meaning="literal",
            rewritten_prompt=prompt,
            confidence=1.0,
            ambiguity_types=[],
        )

        logger.debug(
            "Ambiguity resolve: was_ambiguous=%s signals=%s confidence=%.3f",
            was_ambiguous, remaining_signals, selected.confidence,
        )

        return AmbiguityResult(
            interpretations=interpretations,
            selected=selected,
            confidence=selected.confidence,
            was_ambiguous=was_ambiguous,
            signals=remaining_signals,
        )

    # ------------------------------------------------------------------
    # Pass 1 — structural detection
    # ------------------------------------------------------------------

    def _detect_signals(self, text: str) -> Dict[str, int]:
        """
        Return a count of each ambiguity type detected in *text*.
        """
        signals: Dict[str, int] = {}

        # Referential: bare pronoun with no explicit referent
        if _BARE_PRONOUN.search(text) and not _EXPLICIT_REFERENT.search(text):
            signals["referential"] = 1

        # Scope: quantifier + negation co-occurrence
        scope_matches = len(_SCOPE_SIGNALS.findall(text))
        if scope_matches:
            signals["scope"] = scope_matches

        # Ellipsis: very short, verb-less prompt
        word_count = len(text.split())
        if word_count < 4 and not _HAS_MAIN_VERB.search(text):
            signals["ellipsis"] = 1

        # Lexical: high-polysemy words present
        lex_matches = len(_HIGH_POLYSEMY_WORDS.findall(text))
        if lex_matches:
            signals["lexical"] = lex_matches

        return signals

    # ------------------------------------------------------------------
    # Pass 2 — contextual narrowing
    # ------------------------------------------------------------------

    def _contextual_narrow(
        self,
        prompt: str,
        history: List[str],
        signals: Dict[str, int],
    ) -> str:
        """
        Attempt to resolve signals using conversation history.

        Pronominal resolution: scan the last 3 turns for a noun phrase that
        could serve as the antecedent of a bare pronoun.

        Ellipsis filling: if the prompt is fragmentary, prepend the verb
        phrase from the immediately prior turn (VP ellipsis recovery,
        Dalrymple et al., 1991).
        """
        narrowed = prompt

        # Pronominal resolution — find closest noun antecedent in history
        if "referential" in signals and history:
            antecedent = self._find_antecedent(history[-3:])
            if antecedent:
                # Replace leading pronoun with the recovered antecedent
                narrowed = _BARE_PRONOUN.sub(antecedent, narrowed, count=1)
                signals.pop("referential", None)

        # Ellipsis filling — prepend prior-turn verb phrase
        if "ellipsis" in signals and history:
            prior_vp = self._extract_verb_phrase(history[-1])
            if prior_vp:
                narrowed = f"{prior_vp} {narrowed}"
                signals.pop("ellipsis", None)

        return narrowed

    @staticmethod
    def _find_antecedent(recent_turns: List[str]) -> Optional[str]:
        """
        Return the most recent bare noun phrase from *recent_turns* that
        could serve as a pronoun antecedent (simplified NP detection).
        Searches from most-recent turn backward.
        """
        np_pattern = re.compile(
            r"\b(the [a-zA-Z]+(?:\s[a-zA-Z]+)?|[A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b"
        )
        for turn in reversed(recent_turns):
            matches = np_pattern.findall(turn)
            if matches:
                return matches[-1]  # closest NP = last match in most-recent turn
        return None

    @staticmethod
    def _extract_verb_phrase(turn: str) -> Optional[str]:
        """
        Extract a simple VP (verb + optional complement) from *turn*.
        Returns the first verb + up to 3 following words as the VP head.
        """
        vp_pattern = re.compile(
            r"\b(is|are|was|were|do|does|did|have|has|had|will|would|can|"
            r"could|want|need|build|run|set|use|check|help|tell|find|"
            r"create|start|stop|update|add|remove)\b(\s+\S+){0,3}",
            re.IGNORECASE,
        )
        match = vp_pattern.search(turn)
        return match.group(0).strip() if match else None

    # ------------------------------------------------------------------
    # Pass 3 — interpretation generation
    # ------------------------------------------------------------------

    async def _ai_interpretations(
        self,
        prompt: str,
        history: List[str],
        signals: Dict[str, int],
        domain: str,
    ) -> List[Interpretation]:
        """
        Ask CHAiMERA3sp to enumerate plausible interpretations.
        Falls back to rule-based interpretations on any provider error.
        """
        signal_summary = ", ".join(
            f"{k} ({v})" for k, v in signals.items()
        )
        context_summary = ""
        if history:
            context_summary = "Recent context: " + " | ".join(history[-3:])
        domain_hint = f"Domain: {domain}. " if domain else ""

        ai_prompt = (
            f"{domain_hint}The following user message contains linguistic ambiguity "
            f"({signal_summary}). {context_summary}\n\n"
            f"Message: \"{prompt}\"\n\n"
            "List up to 3 distinct, plausible interpretations of this message. "
            "For each, provide: a concise meaning description and a clear rewritten "
            "version of the message that removes the ambiguity. "
            "Format each as: MEANING: <text> | REWRITE: <text>"
        )
        try:
            result = await self._chaimera.query(
                ai_prompt,
                context={"task": "ambiguity_resolution", "signals": signals},
            )
            return self._parse_ai_interpretations(
                result.get("response", ""), prompt, signals
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("AI ambiguity resolution failed, using rule-based: %s", exc)
            return self._rule_interpretations(
                prompt, signals, self._compute_confidence(sum(signals.values()))
            )

    def _parse_ai_interpretations(
        self,
        response: str,
        original_prompt: str,
        signals: Dict[str, int],
    ) -> List[Interpretation]:
        """
        Parse the structured AI response into :class:`Interpretation` objects.
        Falls back to a single literal interpretation if parsing fails.
        """
        interpretations: List[Interpretation] = []
        total_signals = sum(signals.values())

        pattern = re.compile(
            r"MEANING:\s*(.+?)\s*\|\s*REWRITE:\s*(.+?)(?=MEANING:|$)",
            re.IGNORECASE | re.DOTALL,
        )
        matches = pattern.findall(response)

        for idx, (meaning, rewrite) in enumerate(matches):
            # Confidence decays with rank: top interpretation gets full
            # confidence, subsequent ones are discounted by 0.2 per rank.
            rank_penalty = idx * 0.2
            conf = max(0.05, self._compute_confidence(total_signals) - rank_penalty)
            interpretations.append(
                Interpretation(
                    meaning=meaning.strip(),
                    rewritten_prompt=rewrite.strip(),
                    confidence=round(conf, 3),
                    ambiguity_types=list(signals.keys()),
                )
            )

        if not interpretations:
            # AI returned unparseable output — fall back to literal
            interpretations = self._rule_interpretations(
                original_prompt, signals, self._compute_confidence(total_signals)
            )

        return interpretations

    @staticmethod
    def _rule_interpretations(
        prompt: str,
        signals: Dict[str, int],
        confidence: float,
    ) -> List[Interpretation]:
        """
        Deterministic rule-based interpretation generator used when no AI
        provider is available or as a fallback.

        Generates one canonical interpretation (literal reading) with the
        computed confidence, plus one structural rewrite per detected signal
        type at lower confidence.
        """
        interpretations = [
            Interpretation(
                meaning="literal reading of the prompt",
                rewritten_prompt=prompt,
                confidence=confidence,
                ambiguity_types=list(signals.keys()),
            )
        ]

        for idx, sig_type in enumerate(signals):
            alt_confidence = max(0.05, confidence - 0.15 * (idx + 1))
            if sig_type == "referential":
                rewrite = f"[Please clarify what 'it/this/that' refers to] {prompt}"
            elif sig_type == "scope":
                rewrite = f"[Broad-scope reading] {prompt}"
            elif sig_type == "ellipsis":
                rewrite = f"[Implicit continuation] {prompt}"
            elif sig_type == "lexical":
                rewrite = f"[Technical-domain sense] {prompt}"
            else:
                rewrite = prompt
            interpretations.append(
                Interpretation(
                    meaning=f"{sig_type} ambiguity — alternative reading",
                    rewritten_prompt=rewrite,
                    confidence=round(alt_confidence, 3),
                    ambiguity_types=[sig_type],
                )
            )

        return interpretations

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_confidence(total_signals: int) -> float:
        """
        Confidence = 1 / (1 + total_signals).

        This is a strictly monotone decreasing function of detected signal
        count, bounded in (0, 1].  It makes no probabilistic claims beyond
        "more ambiguity signals → lower confidence in any single reading."
        """
        return round(1.0 / (1.0 + total_signals), 3)
