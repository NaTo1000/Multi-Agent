"""
Council Cluster — 369 tribute cluster system, musical-chairs role rotation,
cross-examination pipeline, hallucination/delusion detector, and build token
meter with fairness regulation.

Architecture
------------

  ┌──────────────────────────────────────────────────────────────────┐
  │                      Cluster369                                  │
  │                                                                  │
  │  members  ──►  form_clusters(preferred_size ∈ {3,6,9})          │
  │                │                                                 │
  │                ▼  musical-chairs rotation                        │
  │           RoleAssigner  ──►  roles per member                   │
  │           ┌──────────────────────────────────────────┐          │
  │           │  TEAM  SOLO  OPPOSITION  FACT_BREAKER     │          │
  │           │  HALLUCINATION_DETECTOR                   │          │
  │           └──────────────────────────────────────────┘          │
  │                │                                                 │
  │                ▼                                                 │
  │           CrossExaminer  (runs after primary execution)          │
  │           ┌──────────────────────────────────────────┐          │
  │           │  OPPOSITION        → challenge notes      │          │
  │           │  FACT_BREAKER      → claim analysis       │          │
  │           │  HALLUCINATION_DET → hallucination score  │          │
  │           └──────────────────────────────────────────┘          │
  │                │                                                 │
  │                ▼                                                 │
  │           BuildTokenMeter                                        │
  │           ┌──────────────────────────────────────────┐          │
  │           │  per-member token tally (heuristic)       │          │
  │           │  fairness regulator (budget enforcement)  │          │
  │           │  platform sales innovation metrics        │          │
  │           └──────────────────────────────────────────┘          │
  └──────────────────────────────────────────────────────────────────┘

Key concepts
------------
- 369 system   : Clusters are sized 3, 6, or 9 (Tesla's harmonic groupings).
                 Any overflow forms the smallest valid cluster (≥3).
- Musical chairs: Role assignments rotate by one seat each ``rotate()`` call.
                  Members cycle through every role over time.
- Roles        : TEAM (collaborate), SOLO (independent), OPPOSITION (challenge),
                 FACT_BREAKER (assumption auditor), HALLUCINATION_DETECTOR.
- Cross-exam   : Second-pass pipeline where role-holders examine primary outputs.
- Token meter  : 1 token ≈ 4 chars heuristic; per-member budget + fairness score.
"""

import logging
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Member roles (musical-chairs rotation)
# ---------------------------------------------------------------------------

class MemberRole(str, Enum):
    """Roles a council member may hold during a build round."""

    TEAM = "team"
    """Collaborate with cluster-mates; outputs are pooled."""

    SOLO = "solo"
    """Work independently; output stands alone."""

    OPPOSITION = "opposition"
    """Challenge and critique the outputs of TEAM/SOLO members."""

    FACT_BREAKER = "fact_breaker"
    """Audit assumptions and unsupported claims in all outputs."""

    HALLUCINATION_DETECTOR = "hallucination_detector"
    """Detect hallucinations / delusions in all outputs."""


# Canonical rotation order — roles shift one seat each ``rotate()``
_ROLE_SEQUENCE: List[MemberRole] = [
    MemberRole.TEAM,
    MemberRole.SOLO,
    MemberRole.OPPOSITION,
    MemberRole.FACT_BREAKER,
    MemberRole.HALLUCINATION_DETECTOR,
]

# ---------------------------------------------------------------------------
# Role assigner — musical chairs
# ---------------------------------------------------------------------------

class RoleAssigner:
    """
    Assigns and rotates roles across a list of members like musical chairs.

    Each call to ``rotate()`` shifts every seat one position around the
    ``_ROLE_SEQUENCE`` ring so every member eventually occupies every role.

    Members beyond the length of ``_ROLE_SEQUENCE`` wrap around (multiple
    members may share a role in larger clusters).
    """

    def __init__(self, rotation_index: int = 0) -> None:
        self._rotation_index = rotation_index

    def assign(self, members: List[str]) -> Dict[str, MemberRole]:
        """Return current role mapping without advancing the rotation."""
        return {
            name: _ROLE_SEQUENCE[(i + self._rotation_index) % len(_ROLE_SEQUENCE)]
            for i, name in enumerate(members)
        }

    def rotate(self, members: List[str]) -> Dict[str, MemberRole]:
        """Advance the rotation by one seat and return the new mapping."""
        self._rotation_index = (self._rotation_index + 1) % len(_ROLE_SEQUENCE)
        logger.debug("RoleAssigner: rotated to index %d", self._rotation_index)
        return self.assign(members)

    @property
    def rotation_index(self) -> int:
        return self._rotation_index

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rotation_index": self._rotation_index,
            "role_sequence": [r.value for r in _ROLE_SEQUENCE],
        }


# ---------------------------------------------------------------------------
# 369 Cluster formation
# ---------------------------------------------------------------------------

_VALID_SIZES = (3, 6, 9)


def _best_cluster_size(n_members: int, preferred: int) -> int:
    """Return the best cluster size given available member count."""
    if preferred in _VALID_SIZES and n_members >= preferred:
        return preferred
    for size in sorted(_VALID_SIZES):
        if n_members >= size:
            return size
    return n_members  # fewer than 3 — all in one group


class Cluster369:
    """
    Groups council members into 3-6-9 clusters with per-cluster musical-chairs
    role rotation.

    The 369 tribute system
    ----------------------
    Members are partitioned into clusters whose sizes are drawn exclusively
    from {3, 6, 9}.  The preferred size is tried first; overflow members
    form smaller valid clusters.  Each cluster maintains an independent
    ``RoleAssigner`` so roles rotate separately within each cluster.

    Example (9 members, preferred=3) → three clusters of 3.
    Example (7 members, preferred=3) → two clusters of 3 + one cluster of 1
        (the singleton gets a pseudo-cluster of size 1 labelled ``orphan``).
    """

    def __init__(self, preferred_size: int = 3) -> None:
        if preferred_size not in _VALID_SIZES:
            raise ValueError(
                f"preferred_size must be one of {_VALID_SIZES}, got {preferred_size}"
            )
        self._preferred_size = preferred_size
        # cluster_id → list of member names
        self._clusters: Dict[str, List[str]] = {}
        # cluster_id → RoleAssigner
        self._assigners: Dict[str, RoleAssigner] = {}

    # ------------------------------------------------------------------
    # Formation
    # ------------------------------------------------------------------

    def form(self, members: List[str]) -> Dict[str, List[str]]:
        """
        Partition ``members`` into 3-6-9 clusters.

        Existing cluster state is cleared and rebuilt from scratch.  Each new
        cluster gets a fresh ``RoleAssigner`` seeded at rotation index 0.

        Returns
        -------
        dict
            cluster_id → list of member names.
        """
        self._clusters = {}
        self._assigners = {}

        if not members:
            return {}

        size = _best_cluster_size(len(members), self._preferred_size)
        chunks = [members[i : i + size] for i in range(0, len(members), size)]

        for idx, chunk in enumerate(chunks):
            # Name after the actual cluster size used
            actual_size = len(chunk)
            label = actual_size if actual_size in _VALID_SIZES else "x"
            cid = f"cluster-{label}-{idx + 1}"
            self._clusters[cid] = chunk
            self._assigners[cid] = RoleAssigner()
            logger.debug("Cluster369: formed %s with %d members", cid, len(chunk))

        logger.info(
            "Cluster369: %d member(s) → %d cluster(s) (preferred size=%d)",
            len(members), len(self._clusters), self._preferred_size,
        )
        return dict(self._clusters)

    # ------------------------------------------------------------------
    # Role management
    # ------------------------------------------------------------------

    def current_roles(self) -> Dict[str, MemberRole]:
        """Return the current role of every member across all clusters."""
        roles: Dict[str, MemberRole] = {}
        for cid, names in self._clusters.items():
            roles.update(self._assigners[cid].assign(names))
        return roles

    def rotate_all(self) -> Dict[str, MemberRole]:
        """Rotate every cluster's roles by one seat (musical-chairs step)."""
        roles: Dict[str, MemberRole] = {}
        for cid, names in self._clusters.items():
            roles.update(self._assigners[cid].rotate(names))
        logger.info("Cluster369: musical-chairs rotation complete")
        return roles

    def rotate_cluster(self, cluster_id: str) -> Dict[str, MemberRole]:
        """Rotate only the specified cluster."""
        if cluster_id not in self._assigners:
            raise KeyError(f"Unknown cluster: {cluster_id}")
        names = self._clusters[cluster_id]
        return self._assigners[cluster_id].rotate(names)

    def get_cluster_of(self, member_name: str) -> Optional[str]:
        """Return the cluster_id containing ``member_name``, or None."""
        for cid, names in self._clusters.items():
            if member_name in names:
                return cid
        return None

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        roles = self.current_roles()
        return {
            "preferred_size": self._preferred_size,
            "clusters": {
                cid: {
                    "members": names,
                    "roles": {n: roles[n].value for n in names},
                    "rotation_index": self._assigners[cid].rotation_index,
                }
                for cid, names in self._clusters.items()
            },
        }


# ---------------------------------------------------------------------------
# Hallucination / delusion detector
# ---------------------------------------------------------------------------

# Patterns that commonly accompany hallucinated or overconfident AI text
_HALLUCINATION_PATTERNS: List[Tuple[str, str, float]] = [
    # (regex_pattern, label, weight)
    (r"\b(always|never|definitely|certainly|absolutely|guaranteed)\b", "overconfidence", 0.15),
    (r"\b(it is (well )?known that|studies (have )?shown|research (has )?proven)\b",
     "unverified_citation", 0.20),
    (r"\b(100%|zero percent|without (any )?doubt)\b", "absolute_claim", 0.15),
    (r"(\w+)\s+(?:\w+\s+){0,5}\1",  # simple repetition of a word within 5 words
     "repetition", 0.10),
    (r"\b(as (I|we) (mentioned|said|noted) (earlier|above|before))\b",
     "false_self_reference", 0.20),
    (r"\b(in (19\d{2}|20\d{2}))\b(?!.*\b(source|ref|cited)\b)",
     "unverified_date", 0.10),
    (r"\b(the (only|best|most (effective|efficient|reliable)) (way|method|approach))\b",
     "superlative_claim", 0.10),
]

_COMPILED_PATTERNS = [
    (re.compile(pat, re.IGNORECASE), label, weight)
    for pat, label, weight in _HALLUCINATION_PATTERNS
]


class HallucinationDetector:
    """
    Heuristic hallucination and delusion detector.

    Scores a text string from 0.0 (clean) to 1.0 (highly suspect) by
    counting weighted pattern matches.  This is an intentionally
    lightweight, dependency-free implementation; production deployments
    should layer a dedicated fact-checking model on top.
    """

    def __init__(self, threshold: float = 0.4) -> None:
        self.threshold = threshold

    def score(self, text: str) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Return ``(score, flags)`` for the supplied text.

        Parameters
        ----------
        text : str
            The AI-generated text to analyse.

        Returns
        -------
        score : float
            Hallucination probability estimate in [0, 1].
        flags : list of dict
            Each entry: ``{label, match, weight}``.
        """
        if not text:
            return 0.0, []

        flags: List[Dict[str, Any]] = []
        raw_score = 0.0

        for pattern, label, weight in _COMPILED_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                # Cap contribution of each pattern at 0.3 regardless of hit count
                contribution = min(weight * len(matches), 0.3)
                raw_score += contribution
                flags.append({
                    "label": label,
                    "hits": len(matches),
                    "weight": weight,
                    "contribution": round(contribution, 3),
                })

        # Normalise to [0, 1]
        final_score = round(min(raw_score, 1.0), 3)
        return final_score, flags

    def detect(self, text: str) -> Dict[str, Any]:
        """
        Run detection and return a structured report.

        Returns
        -------
        dict
            Keys: ``score``, ``flagged`` (bool), ``threshold``, ``flags``.
        """
        score, flags = self.score(text)
        return {
            "score": score,
            "flagged": score >= self.threshold,
            "threshold": self.threshold,
            "flags": flags,
        }


# ---------------------------------------------------------------------------
# Cross-examiner
# ---------------------------------------------------------------------------

class CrossExaminer:
    """
    Second-pass cross-examination pipeline.

    After the primary execution produces a list of member results,
    ``examine()`` iterates over every result and asks role-holding members
    to weigh in according to their current assignment:

    - OPPOSITION        → generate a structured challenge note
    - FACT_BREAKER      → audit claims in the target output
    - HALLUCINATION_DETECTOR → score the output for hallucination signals

    The input ``results`` list is augmented in-place: each result dict
    gains an ``"examination"`` key containing a list of examiner verdicts.
    """

    _CHALLENGE_OPENERS = [
        "This claim warrants scrutiny",
        "Counter-position",
        "Alternative interpretation",
        "Challenging assumption",
        "Reframing the argument",
    ]

    _CLAIM_AUDIT_TEMPLATES = [
        "Unsupported assertion detected",
        "Claim lacks cited evidence",
        "Assumption not substantiated",
        "Requires empirical validation",
    ]

    def __init__(self, hallucination_threshold: float = 0.4) -> None:
        self._detector = HallucinationDetector(threshold=hallucination_threshold)

    def examine(
        self,
        results: List[Dict[str, Any]],
        roles: Dict[str, MemberRole],
    ) -> List[Dict[str, Any]]:
        """
        Run cross-examination over all primary results.

        Parameters
        ----------
        results : list of dict
            Primary execution outputs (each must have a ``"member"`` key).
        roles   : dict
            Current role assignment (member_name → MemberRole).

        Returns
        -------
        list of dict
            Same list with ``"examination"`` key appended to each result.
        """
        for result in results:
            examinations: List[Dict[str, Any]] = []
            target_name = result.get("member", "unknown")
            target_text = str(result.get("response", ""))

            for examiner_name, role in roles.items():
                if examiner_name == target_name:
                    continue  # members don't examine themselves

                if role == MemberRole.OPPOSITION:
                    examinations.append(
                        self._opposition_verdict(examiner_name, target_name, target_text)
                    )
                elif role == MemberRole.FACT_BREAKER:
                    examinations.append(
                        self._fact_breaker_verdict(examiner_name, target_name, target_text)
                    )
                elif role == MemberRole.HALLUCINATION_DETECTOR:
                    examinations.append(
                        self._hallucination_verdict(examiner_name, target_name, target_text)
                    )

            result["examination"] = examinations
            result["examination_summary"] = self._summarise(examinations)

        return results

    # ------------------------------------------------------------------
    # Per-role verdict generators
    # ------------------------------------------------------------------

    def _opposition_verdict(
        self, examiner: str, target: str, text: str
    ) -> Dict[str, Any]:
        """Generate a structured challenge note."""
        opener = self._pick(self._CHALLENGE_OPENERS, examiner)
        word_count = len(text.split())
        # Heuristic: very short responses may be evasive; very long may be padding
        if word_count < 10:
            note = f"{opener}: response is unusually brief ({word_count} words) — may lack substance."
        elif word_count > 300:
            note = f"{opener}: response is lengthy ({word_count} words) — check for padding."
        else:
            note = f"{opener}: response appears reasonably substantiated ({word_count} words). Verify key claims independently."
        return {
            "examiner": examiner,
            "role": MemberRole.OPPOSITION.value,
            "verdict": "CHALLENGED" if word_count < 10 else "SCRUTINISED",
            "note": note,
        }

    def _fact_breaker_verdict(
        self, examiner: str, target: str, text: str
    ) -> Dict[str, Any]:
        """Identify and flag absolute / unsupported claims."""
        template = self._pick(self._CLAIM_AUDIT_TEMPLATES, examiner)
        # Count absolute indicators as a simple claim-strength proxy
        absolute_hits = sum(
            1 for word in ("always", "never", "definitely", "proven", "guaranteed")
            if word.lower() in text.lower()
        )
        if absolute_hits:
            note = (
                f"{template}: {absolute_hits} absolute indicator(s) found. "
                "Claims should reference verifiable sources."
            )
            verdict = "CLAIMS_FLAGGED"
        else:
            note = f"Claim audit: no strong absolute indicators found. Moderate confidence."
            verdict = "CLAIMS_MODERATE"
        return {
            "examiner": examiner,
            "role": MemberRole.FACT_BREAKER.value,
            "verdict": verdict,
            "absolute_hits": absolute_hits,
            "note": note,
        }

    def _hallucination_verdict(
        self, examiner: str, target: str, text: str
    ) -> Dict[str, Any]:
        """Run hallucination detection on the target text."""
        detection = self._detector.detect(text)
        return {
            "examiner": examiner,
            "role": MemberRole.HALLUCINATION_DETECTOR.value,
            "verdict": "HALLUCINATION_FLAGGED" if detection["flagged"] else "PASSED",
            "hallucination_score": detection["score"],
            "hallucination_flags": detection["flags"],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pick(options: List[str], seed: str) -> str:
        """Deterministically pick from options using the seed string."""
        return options[hash(seed) % len(options)]

    @staticmethod
    def _summarise(examinations: List[Dict[str, Any]]) -> Dict[str, Any]:
        verdicts = [e["verdict"] for e in examinations]
        flagged = [v for v in verdicts if v not in ("PASSED", "SCRUTINISED", "CLAIMS_MODERATE")]
        return {
            "total_examiners": len(examinations),
            "flagged_count": len(flagged),
            "clean": len(flagged) == 0,
            "verdicts": verdicts,
        }


# ---------------------------------------------------------------------------
# Build token meter
# ---------------------------------------------------------------------------

_CHARS_PER_TOKEN = 4  # ~OpenAI heuristic


class BuildTokenMeter:
    """
    Tracks estimated token usage across all council members and enforces a
    configurable per-member fairness budget.

    Token counting
    --------------
    Uses a simple ``len(text) / 4`` heuristic (1 token ≈ 4 characters).
    Replace ``estimate_tokens()`` with a real tokenizer if precision matters.

    Fairness regulation
    -------------------
    When a member exceeds ``budget_per_member`` tokens their over-budget flag
    is raised.  The caller may choose to skip or throttle that member on the
    next round.  The ``fairness_report()`` quantifies the distribution
    inequality using the Gini coefficient.

    Platform sales innovation metrics
    ----------------------------------
    ``innovation_score()`` is a composite metric combining output diversity
    (unique-word ratio across all members) and throughput (total tokens).
    Useful for tracking how much novel content the council is generating.
    """

    def __init__(self, budget_per_member: int = 2048) -> None:
        self.budget_per_member = budget_per_member
        self._usage: Dict[str, int] = defaultdict(int)
        self._call_count: Dict[str, int] = defaultdict(int)
        self._all_texts: List[str] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, member_name: str, text: str) -> int:
        """
        Record a member's response text and return the estimated token count.
        """
        tokens = self.estimate_tokens(text)
        self._usage[member_name] += tokens
        self._call_count[member_name] += 1
        self._all_texts.append(text)
        return tokens

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Heuristic: 1 token ≈ 4 characters."""
        return max(1, math.ceil(len(text) / _CHARS_PER_TOKEN))

    # ------------------------------------------------------------------
    # Budget / fairness
    # ------------------------------------------------------------------

    def is_over_budget(self, member_name: str) -> bool:
        """Return True if the member has exceeded their per-member budget."""
        return self._usage.get(member_name, 0) > self.budget_per_member

    def get_usage(self) -> Dict[str, int]:
        """Per-member cumulative token usage."""
        return dict(self._usage)

    def get_total(self) -> int:
        """Sum of all recorded tokens."""
        return sum(self._usage.values())

    def reset(self) -> None:
        """Reset all counters (start of a new build round)."""
        self._usage.clear()
        self._call_count.clear()
        self._all_texts.clear()

    def fairness_report(self) -> Dict[str, Any]:
        """
        Return a fairness analysis of token distribution.

        Includes the Gini coefficient (0 = perfectly equal, 1 = completely
        unequal) and flags members who are over budget.
        """
        values = list(self._usage.values())
        over_budget = [n for n in self._usage if self.is_over_budget(n)]

        gini = self._gini(values) if len(values) > 1 else 0.0
        total = self.get_total()

        return {
            "total_tokens": total,
            "budget_per_member": self.budget_per_member,
            "per_member": dict(self._usage),
            "call_counts": dict(self._call_count),
            "over_budget": over_budget,
            "gini_coefficient": round(gini, 4),
            "fairness_label": self._fairness_label(gini),
        }

    def innovation_score(self) -> Dict[str, Any]:
        """
        Platform sales innovation metric.

        Combines:
        - Output diversity  : unique-word ratio across all member outputs
        - Throughput        : total tokens produced (log-normalised)
        - Balance           : 1 − Gini (inverse inequality)

        Returns a composite score in [0, 1] and its components.
        """
        all_words = " ".join(self._all_texts).lower().split()
        diversity = len(set(all_words)) / max(len(all_words), 1)
        total = self.get_total()
        throughput = min(math.log1p(total) / math.log1p(100_000), 1.0)
        gini = self._gini(list(self._usage.values())) if len(self._usage) > 1 else 0.0
        balance = 1.0 - gini
        composite = round((diversity + throughput + balance) / 3, 4)
        return {
            "innovation_score": composite,
            "diversity": round(diversity, 4),
            "throughput": round(throughput, 4),
            "balance": round(balance, 4),
            "total_tokens": total,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _gini(values: List[int]) -> float:
        """Compute the Gini coefficient of a list of non-negative values."""
        if not values or sum(values) == 0:
            return 0.0
        n = len(values)
        sorted_vals = sorted(values)
        cumsum = 0
        for i, v in enumerate(sorted_vals):
            cumsum += (2 * (i + 1) - n - 1) * v
        return cumsum / (n * sum(sorted_vals))

    @staticmethod
    def _fairness_label(gini: float) -> str:
        if gini < 0.2:
            return "very_fair"
        if gini < 0.4:
            return "fair"
        if gini < 0.6:
            return "moderate"
        return "unequal"
