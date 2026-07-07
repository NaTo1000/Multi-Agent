"""
CHAiMERA3sp — Composite Hybrid AI Multi-Engine Routing Architecture (3 Service Providers).

Provides a unified interface for dispatching inference/research queries to multiple
AI backends.  Supported providers:

  - watsonx   : IBM watsonx.ai REST API (text generation)
  - kai9000   : Kai-9000 generic HTTP inference endpoint
  - kimi       : Moonshot AI Kimi REST API (compatible with OpenAI chat format)
  - manus      : Manus AI autonomous-agent REST API

The ``CHAiMERA3sp`` router selects the first configured and healthy provider,
with support for explicit provider selection and fallback chains.

The **Tracery subsystem** adds post-response knowledge scraping, series
deciphering, fake-info dispelling, accuracy scrutiny, and percentage-based
inference-stream lockouts to every routing path.
"""

import json
import logging
import re
import urllib.error
import urllib.request
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .hiai import HiAiModule

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tracery subsystem constants
# ---------------------------------------------------------------------------

# Minimum claim character length (shorter strings are noise).
_CLAIM_MIN_LEN: int = 20

# Maximum claim character length — long chunks are truncated.
_CLAIM_MAX_LEN: int = 300

# Minimum token overlap fraction for contradiction detection.
_CONTRADICTION_OVERLAP: float = 0.40

# Negation vocabulary used to flip the polarity of a claim.
_NEGATION_WORDS = frozenset({
    "not", "never", "no", "false", "incorrect", "wrong", "invalid",
    "cannot", "can't", "doesn't", "isn't", "aren't", "wasn't", "weren't",
    "shouldn't", "wouldn't", "won't", "don't", "didn't",
})

# Accuracy below this fraction triggers a provider lockout.
_LOCKOUT_THRESHOLD: float = 0.40

# Minimum claims before a lockout can be applied.
_LOCKOUT_MIN_CLAIMS: int = 5

# Minimum coherence score to label a series as internally consistent.
_SERIES_COHERENCE_MIN: float = 0.50


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class CHAiMERAProvider(ABC):
    """Abstract base class for a single AI backend provider."""

    name: str = "base"

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    @property
    def is_configured(self) -> bool:
        """Return True if the minimum required config keys are present and non-empty."""
        return bool(self._endpoint)

    @property
    def _endpoint(self) -> str:
        return self.config.get("endpoint", "")

    @property
    def _api_key(self) -> str:
        return self.config.get("api_key", "")

    @abstractmethod
    async def query(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit a prompt and return a structured response dict.

        Required response keys: ``response`` (str), ``provider`` (str).
        """

    def _http_post(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Blocking HTTP POST helper (used by all providers)."""
        headers = headers or {}
        headers.setdefault("Content-Type", "application/json")
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Watsonx provider
# ---------------------------------------------------------------------------


class WatsonxProvider(CHAiMERAProvider):
    """
    IBM watsonx.ai text generation provider.

    Config keys:
      endpoint  : watsonx.ai generation URL
                  e.g. https://us-south.ml.cloud.ibm.com/ml/v1/text/generation
      api_key   : IBM Cloud IAM API key
      project_id: watsonx project ID
      model_id  : model to use (default: ibm/granite-13b-instruct-v2)
    """

    name = "watsonx"

    async def query(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        model_id = self.config.get("model_id", "ibm/granite-13b-instruct-v2")
        project_id = self.config.get("project_id", "")
        payload = {
            "model_id": model_id,
            "input": prompt,
            "parameters": {
                "decoding_method": "greedy",
                "max_new_tokens": self.config.get("max_tokens", 512),
            },
            "project_id": project_id,
        }
        headers = {
            "Authorization": "Bearer " + self._api_key,
            "Content-Type": "application/json",
        }
        try:
            data = self._http_post(self._endpoint, payload, headers)
            text = (
                data.get("results", [{}])[0].get("generated_text", "")
                or data.get("generated_text", "")
            )
            return {
                "provider": self.name,
                "model": model_id,
                "response": text.strip(),
                "raw": data,
            }
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("watsonx query failed: %s", exc)
            raise


# ---------------------------------------------------------------------------
# Kai-9000 provider
# ---------------------------------------------------------------------------


class Kai9000Provider(CHAiMERAProvider):
    """
    Kai-9000 generic HTTP inference provider.

    Sends a standard ``{"prompt": ..., "context": ...}`` body and expects
    ``{"response": ...}`` in the reply.  Suitable for custom/self-hosted models.

    Config keys:
      endpoint : inference URL
      api_key  : bearer token (optional)
      model    : model identifier forwarded to the endpoint (optional)
    """

    name = "kai9000"

    async def query(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"prompt": prompt, "context": context}
        model = self.config.get("model", "")
        if model:
            payload["model"] = model
        headers: Dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = "Bearer " + self._api_key
        try:
            data = self._http_post(self._endpoint, payload, headers)
            response_text = (
                data.get("response")
                or data.get("text")
                or data.get("output")
                or ""
            )
            return {
                "provider": self.name,
                "model": model or "kai9000",
                "response": str(response_text).strip(),
                "raw": data,
            }
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("kai9000 query failed: %s", exc)
            raise


# ---------------------------------------------------------------------------
# Kimi provider
# ---------------------------------------------------------------------------


class KimiProvider(CHAiMERAProvider):
    """
    Moonshot AI Kimi provider (OpenAI-compatible chat completions API).

    Config keys:
      endpoint  : API base URL (default: https://api.moonshot.cn/v1)
      api_key   : Moonshot API key
      model     : model name (default: moonshot-v1-8k  →  Kimi 2.6 uses kimi-2.6)
    """

    name = "kimi"
    _DEFAULT_ENDPOINT = "https://api.moonshot.cn/v1"

    @property
    def _endpoint(self) -> str:
        return self.config.get("endpoint", self._DEFAULT_ENDPOINT)

    @property
    def is_configured(self) -> bool:
        # Kimi has a default endpoint, so require an api_key to be truly configured.
        return bool(self._api_key)

    async def query(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        model = self.config.get("model", "kimi-2.6")
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.config.get("max_tokens", 512),
        }
        headers = {
            "Authorization": "Bearer " + self._api_key,
        }
        url = self._endpoint.rstrip("/") + "/chat/completions"
        try:
            data = self._http_post(url, payload, headers)
            text = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return {
                "provider": self.name,
                "model": model,
                "response": text.strip(),
                "raw": data,
            }
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("kimi query failed: %s", exc)
            raise


# ---------------------------------------------------------------------------
# Manus provider
# ---------------------------------------------------------------------------


class ManusProvider(CHAiMERAProvider):
    """
    Manus AI autonomous-agent provider.

    Submits a task to the Manus agent API and returns the result.

    Config keys:
      endpoint  : Manus API base URL  e.g. https://api.manus.im/v1
      api_key   : Manus API key
      agent_id  : optional target agent ID
    """

    name = "manus"

    async def query(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "task": prompt,
            "context": context,
        }
        agent_id = self.config.get("agent_id", "")
        if agent_id:
            payload["agent_id"] = agent_id
        headers = {
            "Authorization": "Bearer " + self._api_key,
        }
        url = self._endpoint.rstrip("/") + "/run"
        try:
            data = self._http_post(url, payload, headers)
            response_text = (
                data.get("result")
                or data.get("output")
                or data.get("response")
                or ""
            )
            return {
                "provider": self.name,
                "model": agent_id or "manus-agent",
                "response": str(response_text).strip(),
                "raw": data,
            }
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("manus query failed: %s", exc)
            raise


# ---------------------------------------------------------------------------
# Tracery subsystem — dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TraceryNode:
    """
    A single factual claim extracted (scraped) from a provider response.

    Attributes:
        node_id:         Unique identifier.
        source_provider: Provider that produced this claim.
        claim:           The extracted claim text (≤ ``_CLAIM_MAX_LEN`` chars).
        series_key:      Topic / series grouping key derived from context.
        confidence:      Extraction confidence in [0.0, 1.0].
        timestamp:       UTC timestamp of extraction.
        dispelled:       ``True`` when identified as false / contradictory.
        dispel_reason:   Explanation of why the claim was dispelled.
    """

    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source_provider: str = ""
    claim: str = ""
    series_key: str = "general"
    confidence: float = 1.0
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    dispelled: bool = False
    dispel_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "source_provider": self.source_provider,
            "claim": self.claim,
            "series_key": self.series_key,
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp.isoformat(),
            "dispelled": self.dispelled,
            "dispel_reason": self.dispel_reason,
        }


@dataclass
class SeriesPattern:
    """
    A group of :class:`TraceryNode` objects sharing a series key.

    Attributes:
        series_id:       Unique identifier.
        series_key:      Topic / domain shared by all nodes.
        nodes:           Constituent TraceryNodes (non-dispelled).
        coherence_score: Fraction of node pairs that do not contradict each
                         other (0.0 = fully contradictory, 1.0 = fully
                         coherent).
        dominant_claim:  The single most-supported claim in the series.
    """

    series_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    series_key: str = "general"
    nodes: List[TraceryNode] = field(default_factory=list)
    coherence_score: float = 1.0
    dominant_claim: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "series_id": self.series_id,
            "series_key": self.series_key,
            "node_count": len(self.nodes),
            "coherence_score": round(self.coherence_score, 3),
            "dominant_claim": self.dominant_claim,
        }


@dataclass
class AccuracyReport:
    """
    Per-provider accuracy assessment produced by :class:`InferenceStreamMonitor`.

    Attributes:
        provider:        Provider name.
        total_claims:    Total claims scraped from this provider.
        dispelled_claims: Claims identified as false / contradictory.
        accuracy_rate:   ``(total − dispelled) / total`` — 1.0 when no
                         dispelled claims, 0.0 when all are dispelled.
        is_locked:       ``True`` when accuracy is below ``_LOCKOUT_THRESHOLD``
                         and ``total_claims ≥ _LOCKOUT_MIN_CLAIMS``.
        lockout_reason:  Human-readable lockout explanation.
    """

    provider: str
    total_claims: int
    dispelled_claims: int
    accuracy_rate: float
    is_locked: bool
    lockout_reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "total_claims": self.total_claims,
            "dispelled_claims": self.dispelled_claims,
            "accuracy_rate": round(self.accuracy_rate, 3),
            "is_locked": self.is_locked,
            "lockout_reason": self.lockout_reason,
        }


@dataclass
class DataResearchReport:
    """
    Synthesized research report from the :class:`TraceryStore`.

    Attributes:
        report_id:        Unique identifier.
        timestamp:        UTC timestamp of report generation.
        total_nodes:      Total TraceryNodes in the store (including dispelled).
        series_patterns:  Detected series, sorted by coherence descending.
        dispelled_nodes:  All nodes flagged as dispelled fake info.
        accuracy_reports: Per-provider accuracy assessments.
        locked_providers: Providers currently locked out.
        summary:          One-paragraph narrative of the report findings.
    """

    report_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    total_nodes: int = 0
    series_patterns: List[SeriesPattern] = field(default_factory=list)
    dispelled_nodes: List[TraceryNode] = field(default_factory=list)
    accuracy_reports: List[AccuracyReport] = field(default_factory=list)
    locked_providers: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp.isoformat(),
            "total_nodes": self.total_nodes,
            "series_patterns": [s.to_dict() for s in self.series_patterns],
            "dispelled_count": len(self.dispelled_nodes),
            "accuracy_reports": [a.to_dict() for a in self.accuracy_reports],
            "locked_providers": list(self.locked_providers),
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Tracery subsystem — helpers
# ---------------------------------------------------------------------------


def _tokenise(text: str) -> frozenset:
    """Return a frozenset of lowercase alpha-only tokens from *text*."""
    return frozenset(w.lower() for w in re.findall(r"[a-zA-Z]+", text) if len(w) > 2)


def _has_negation(text: str) -> bool:
    """Return True if *text* contains any negation indicator."""
    tokens = _tokenise(text)
    # Also catch contracted forms that tokenise differently
    lower = text.lower()
    contracted = {"n't", "can't", "won't", "don't", "isn't", "aren't",
                  "wasn't", "weren't", "doesn't", "didn't", "wouldn't",
                  "shouldn't"}
    return bool(tokens & _NEGATION_WORDS) or any(c in lower for c in contracted)


def _token_overlap(a: str, b: str) -> float:
    """Jaccard token overlap between claims *a* and *b*."""
    ta, tb = _tokenise(a), _tokenise(b)
    union = ta | tb
    if not union:
        return 0.0
    return len(ta & tb) / len(union)


def _claims_contradict(a: str, b: str) -> bool:
    """
    Return True when claims *a* and *b* are likely contradictory.

    Contradiction = high token overlap AND exactly one of them contains
    a negation indicator.
    """
    if _token_overlap(a, b) < _CONTRADICTION_OVERLAP:
        return False
    return _has_negation(a) != _has_negation(b)


# ---------------------------------------------------------------------------
# Tracery subsystem — TraceryStore
# ---------------------------------------------------------------------------


class TraceryStore:
    """
    In-memory repository for :class:`TraceryNode` objects, grouped by
    series key for efficient series-level operations.
    """

    def __init__(self) -> None:
        self._nodes: List[TraceryNode] = []

    @property
    def total_count(self) -> int:
        """Total nodes (including dispelled)."""
        return len(self._nodes)

    @property
    def live_count(self) -> int:
        """Non-dispelled nodes."""
        return sum(1 for n in self._nodes if not n.dispelled)

    @property
    def dispelled_count(self) -> int:
        """Dispelled nodes."""
        return sum(1 for n in self._nodes if n.dispelled)

    def add(self, node: TraceryNode) -> None:
        self._nodes.append(node)

    def get_all(self) -> List[TraceryNode]:
        return list(self._nodes)

    def get_live(self) -> List[TraceryNode]:
        return [n for n in self._nodes if not n.dispelled]

    def get_dispelled(self) -> List[TraceryNode]:
        return [n for n in self._nodes if n.dispelled]

    def get_by_series(self, series_key: str, live_only: bool = True) -> List[TraceryNode]:
        nodes = [n for n in self._nodes if n.series_key == series_key]
        return [n for n in nodes if not n.dispelled] if live_only else nodes

    def get_by_provider(self, provider: str) -> List[TraceryNode]:
        return [n for n in self._nodes if n.source_provider == provider]

    def series_keys(self) -> List[str]:
        return list({n.series_key for n in self._nodes})


# ---------------------------------------------------------------------------
# Tracery subsystem — KnowledgeScraper
# ---------------------------------------------------------------------------


class KnowledgeScraper:
    """
    Extracts :class:`TraceryNode` objects (factual claims) from provider
    response text.

    A claim is any sentence-like fragment that:

    * is between ``_CLAIM_MIN_LEN`` and ``_CLAIM_MAX_LEN`` characters,
    * does not end with ``?`` (questions are not claims),
    * is not a blank or whitespace-only string.

    The ``series_key`` is derived from ``context.get("topic")`` when
    available, otherwise the first significant word (> 3 chars) of the
    first extracted claim, falling back to ``"general"``.
    """

    @staticmethod
    def scrape(
        response_text: str,
        provider: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[TraceryNode]:
        """
        Extract :class:`TraceryNode` objects from *response_text*.

        Args:
            response_text: Raw text returned by the provider.
            provider:      Provider name (stored in each node).
            context:       Optional context dict; ``context["topic"]`` sets
                           the series key when present.

        Returns:
            List of :class:`TraceryNode` objects (may be empty for short or
            question-only responses).
        """
        ctx = context or {}
        series_key = str(ctx.get("topic", "")).strip() or None

        # Split on sentence boundaries
        raw_sentences = re.split(r"(?<=[.!])\s+", response_text.strip())
        nodes: List[TraceryNode] = []

        for sentence in raw_sentences:
            sentence = sentence.strip()
            if not sentence or sentence.endswith("?"):
                continue
            if len(sentence) < _CLAIM_MIN_LEN:
                continue
            claim = sentence[:_CLAIM_MAX_LEN]
            nodes.append(
                TraceryNode(
                    source_provider=provider,
                    claim=claim,
                    series_key=series_key or "general",
                )
            )

        # Derive series key from first claim if not provided
        if not series_key and nodes:
            first_words = re.findall(r"[a-zA-Z]{4,}", nodes[0].claim)
            if first_words:
                series_key = first_words[0].lower()
                for node in nodes:
                    node.series_key = series_key

        return nodes


# ---------------------------------------------------------------------------
# Tracery subsystem — SeriesDecipher
# ---------------------------------------------------------------------------


class SeriesDecipher:
    """
    Groups :class:`TraceryNode` objects from a :class:`TraceryStore` into
    :class:`SeriesPattern` objects and computes per-series coherence scores.

    Coherence = fraction of node pairs that do *not* contradict each other.
    The dominant claim is the node with the highest average similarity
    to all other live nodes in the same series.
    """

    @staticmethod
    def decipher(store: TraceryStore) -> List[SeriesPattern]:
        """
        Derive :class:`SeriesPattern` objects from *store*.

        Returns:
            List of :class:`SeriesPattern` sorted by coherence descending.
        """
        patterns: List[SeriesPattern] = []

        for key in store.series_keys():
            nodes = store.get_by_series(key, live_only=True)
            if not nodes:
                continue

            # Coherence: fraction of pairs without contradiction
            pairs = [
                (nodes[i], nodes[j])
                for i in range(len(nodes))
                for j in range(i + 1, len(nodes))
            ]
            if pairs:
                non_contradicting = sum(
                    0 if _claims_contradict(a.claim, b.claim) else 1
                    for a, b in pairs
                )
                coherence = non_contradicting / len(pairs)
            else:
                coherence = 1.0

            # Dominant claim: highest mean similarity to peers
            dominant = nodes[0]
            if len(nodes) > 1:
                best_score = -1.0
                for candidate in nodes:
                    peers = [n for n in nodes if n is not candidate]
                    score = sum(
                        _token_overlap(candidate.claim, p.claim) for p in peers
                    ) / len(peers)
                    if score > best_score:
                        best_score, dominant = score, candidate

            patterns.append(
                SeriesPattern(
                    series_key=key,
                    nodes=list(nodes),
                    coherence_score=round(coherence, 3),
                    dominant_claim=dominant.claim,
                )
            )

        patterns.sort(key=lambda p: p.coherence_score, reverse=True)
        return patterns


# ---------------------------------------------------------------------------
# Tracery subsystem — AccuracyScrutineer
# ---------------------------------------------------------------------------


class AccuracyScrutineer:
    """
    Evaluates incoming :class:`TraceryNode` objects against established live
    nodes in the same series and dispels those that contradict the consensus.

    A node is **dispelled** when it contradicts ≥ 1 established non-dispelled
    node in the same series.  The rationale records the conflicting claim.

    All dispelled nodes are logged at WARNING level for auditable fake-info
    tracking.
    """

    @staticmethod
    def scrutinise(
        nodes: List[TraceryNode], store: TraceryStore
    ) -> List[TraceryNode]:
        """
        Check *nodes* against *store* and mark contradictory ones as dispelled.

        Args:
            nodes: Freshly scraped nodes (not yet in the store).
            store: Current :class:`TraceryStore` for baseline comparison.

        Returns:
            The same list of nodes, with ``dispelled`` and ``dispel_reason``
            populated where contradictions were found.
        """
        for node in nodes:
            established = store.get_by_series(node.series_key, live_only=True)
            for existing in established:
                if _claims_contradict(node.claim, existing.claim):
                    node.dispelled = True
                    node.dispel_reason = (
                        f"Contradicts established claim: "
                        f'"{existing.claim[:120]}"'
                    )
                    logger.warning(
                        "CHAiMERA3sp DISPELLED fake info | provider=%s "
                        "series=%s | claim=%s | reason=%s",
                        node.source_provider,
                        node.series_key,
                        node.claim[:80],
                        node.dispel_reason[:80],
                    )
                    break  # one contradiction is sufficient
        return nodes


# ---------------------------------------------------------------------------
# Tracery subsystem — InferenceStreamMonitor
# ---------------------------------------------------------------------------


class InferenceStreamMonitor:
    """
    Tracks per-provider accuracy rates and enforces percentage-based
    inference-stream lockouts.

    A provider is **locked** when:

    * it has at least ``_LOCKOUT_MIN_CLAIMS`` total scraped claims, **and**
    * its accuracy rate ``(non-dispelled / total)`` falls below
      ``_LOCKOUT_THRESHOLD``.

    Locked providers are excluded from routing by :class:`CHAiMERA3sp`.
    """

    def __init__(self) -> None:
        self._locked: Dict[str, bool] = {}

    def update(self, store: TraceryStore) -> None:
        """Recompute lockout status for all providers seen in *store*."""
        providers = {n.source_provider for n in store.get_all()}
        for provider in providers:
            nodes = store.get_by_provider(provider)
            total = len(nodes)
            dispelled = sum(1 for n in nodes if n.dispelled)
            accuracy = (total - dispelled) / total if total > 0 else 1.0
            if total >= _LOCKOUT_MIN_CLAIMS and accuracy < _LOCKOUT_THRESHOLD:
                if not self._locked.get(provider):
                    logger.warning(
                        "CHAiMERA3sp LOCKOUT | provider=%s accuracy=%.1f%% "
                        "(threshold=%.0f%%)",
                        provider, accuracy * 100, _LOCKOUT_THRESHOLD * 100,
                    )
                self._locked[provider] = True
            else:
                self._locked[provider] = False

    def is_locked(self, provider: str) -> bool:
        """Return ``True`` when *provider* is currently locked out."""
        return self._locked.get(provider, False)

    def get_accuracy_reports(self, store: TraceryStore) -> List[AccuracyReport]:
        """Build an :class:`AccuracyReport` for every provider in *store*."""
        reports: List[AccuracyReport] = []
        providers = {n.source_provider for n in store.get_all()}
        for provider in sorted(providers):
            nodes = store.get_by_provider(provider)
            total = len(nodes)
            dispelled = sum(1 for n in nodes if n.dispelled)
            accuracy = (total - dispelled) / total if total > 0 else 1.0
            locked = self.is_locked(provider)
            reason = ""
            if locked:
                reason = (
                    f"Accuracy {accuracy:.0%} is below the {_LOCKOUT_THRESHOLD:.0%} "
                    f"lockout threshold after {total} claims."
                )
            reports.append(
                AccuracyReport(
                    provider=provider,
                    total_claims=total,
                    dispelled_claims=dispelled,
                    accuracy_rate=round(accuracy, 3),
                    is_locked=locked,
                    lockout_reason=reason,
                )
            )
        return reports

    @property
    def locked_providers(self) -> List[str]:
        """List of currently locked provider names."""
        return [p for p, locked in self._locked.items() if locked]


# ---------------------------------------------------------------------------
# CHAiMERA3sp router
# ---------------------------------------------------------------------------

_PROVIDER_REGISTRY: Dict[str, type] = {
    "watsonx": WatsonxProvider,
    "kai9000": Kai9000Provider,
    "kimi": KimiProvider,
    "manus": ManusProvider,
}


class CHAiMERA3sp:
    """
    Composite Hybrid AI Multi-Engine Routing Architecture (3 Service Providers).

    Routes inference/research queries to one or more configured AI backends.
    Provider selection strategy (``strategy`` config key):

    - ``"first"``    (default) — use the first configured provider in priority order.
    - ``"fallback"`` — try providers in order; return first successful response.
    - ``"broadcast"``— query all configured providers and return all responses.

    Config structure (mirrors ``config/default.yaml`` ``chaimera3sp`` section)::

        chaimera3sp:
          strategy: first          # first | fallback | broadcast
          priority:                # provider resolution order
            - watsonx
            - kimi
            - kai9000
            - manus
          providers:
            watsonx:
              endpoint: "https://us-south.ml.cloud.ibm.com/ml/v1/text/generation"
              api_key: ""
              project_id: ""
              model_id: "ibm/granite-13b-instruct-v2"
            kimi:
              endpoint: "https://api.moonshot.cn/v1"
              api_key: ""
              model: "kimi-2.6"
            kai9000:
              endpoint: ""
              api_key: ""
            manus:
              endpoint: ""
              api_key: ""
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        hiai_module: Optional["HiAiModule"] = None,
    ) -> None:
        cfg = config or {}
        self._strategy: str = cfg.get("strategy", "first")
        self._priority: List[str] = cfg.get(
            "priority", ["watsonx", "kimi", "kai9000", "manus"]
        )
        provider_configs: Dict[str, Any] = cfg.get("providers", {})
        self._providers: Dict[str, CHAiMERAProvider] = {}
        for name, klass in _PROVIDER_REGISTRY.items():
            p_cfg = provider_configs.get(name, {})
            self._providers[name] = klass(p_cfg)
        self._hiai: Optional["HiAiModule"] = hiai_module

        # Tracery subsystem
        self._tracery_store = TraceryStore()
        self._scraper = KnowledgeScraper()
        self._decipher = SeriesDecipher()
        self._scrutineer = AccuracyScrutineer()
        self._stream_monitor = InferenceStreamMonitor()

        configured = [n for n in self._priority if self._providers[n].is_configured]
        logger.info(
            "CHAiMERA3sp initialised | strategy=%s | configured providers: %s",
            self._strategy,
            configured or ["none"],
        )

    @property
    def configured_providers(self) -> List[str]:
        """Return the names of providers that are configured and not locked out."""
        return [
            n for n in self._priority
            if self._providers[n].is_configured
            and not self._stream_monitor.is_locked(n)
        ]

    @property
    def all_configured_providers(self) -> List[str]:
        """Return all configured providers regardless of lockout status."""
        return [n for n in self._priority if self._providers[n].is_configured]

    async def query(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Route a query to the appropriate provider(s).

        After each successful response the Tracery subsystem:

        1. **Scrapes** :class:`TraceryNode` claims from the response text.
        2. **Scrutinises** each claim against established series knowledge
           and dispels contradictory (fake) claims, logging each dispel event.
        3. **Updates** the :class:`InferenceStreamMonitor`; providers whose
           accuracy drops below ``_LOCKOUT_THRESHOLD`` (after ≥
           ``_LOCKOUT_MIN_CLAIMS`` claims) are locked out of future routing.

        If a :class:`~ai.hiai.HiAiModule` is attached and ``context`` contains
        a ``user_id``, the prompt is pre-processed through the HiAi pipeline
        first: the resolved (disambiguated) prompt is used instead of the raw
        one, and ``rapport_note`` plus ``emotional_snapshot`` are injected into
        the context forwarded to the provider.

        Args:
            prompt:   Natural-language prompt / query string.
            context:  Optional key-value context forwarded to the provider.
            provider: Force a specific provider by name (overrides strategy).

        Returns:
            A dict with at least ``provider``, ``response``, and ``timestamp`` keys.
            When ``strategy="broadcast"``, returns ``{"responses": [...], ...}``.
        """
        context = context or {}
        timestamp = datetime.now(timezone.utc).isoformat()

        # HiAi pre-processing — run when a hiai_module is attached and a
        # user_id is present in context so the pipeline can personalise.
        if self._hiai is not None and context.get("user_id"):
            try:
                history: List[str] = context.get("conversation_history", [])
                hiai_result = await self._hiai.process(
                    prompt=prompt,
                    user_id=context["user_id"],
                    conversation_history=history,
                )
                # Swap in the disambiguated prompt
                prompt = hiai_result.resolved_prompt
                # Inject personalisation signals into the provider context
                context = {
                    **context,
                    "rapport_note": hiai_result.rapport_note,
                    "emotional_snapshot": hiai_result.emotional_snapshot.to_dict(),
                    "rapport_context": hiai_result.rapport_context,
                }
                logger.debug(
                    "CHAiMERA3sp HiAi pre-processed | user=%s | tone=%s",
                    context["user_id"],
                    hiai_result.emotional_snapshot.dominant_tone,
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("CHAiMERA3sp HiAi pre-processing failed: %s", exc)

        if provider:
            result = await self._query_single(provider, prompt, context, timestamp)
        elif self._strategy == "broadcast":
            result = await self._query_broadcast(prompt, context, timestamp)
        elif self._strategy == "fallback":
            result = await self._query_fallback(prompt, context, timestamp)
        else:
            # default: "first"
            result = await self._query_first(prompt, context, timestamp)

        # Tracery post-processing — scrape, scrutinise, monitor
        self._tracery_post_process(result, context)
        return result

    # ------------------------------------------------------------------
    # Tracery pipeline
    # ------------------------------------------------------------------

    def _tracery_post_process(
        self, result: Dict[str, Any], context: Dict[str, Any]
    ) -> None:
        """
        Run the full tracery pipeline on a single provider result.

        For broadcast results (``result["strategy"] == "broadcast"``) this
        is called once per sub-response.
        """
        if result.get("strategy") == "broadcast":
            for sub in result.get("responses", []):
                self._tracery_post_process(sub, context)
            return

        provider_name = result.get("provider", "unknown")
        response_text = result.get("response", "")
        if not response_text or provider_name in ("none", "unknown"):
            return

        nodes = self._scraper.scrape(response_text, provider_name, context)
        nodes = self._scrutineer.scrutinise(nodes, self._tracery_store)
        for node in nodes:
            self._tracery_store.add(node)
        self._stream_monitor.update(self._tracery_store)

        dispelled_count = sum(1 for n in nodes if n.dispelled)
        if dispelled_count:
            logger.info(
                "CHAiMERA3sp tracery | provider=%s scraped=%d dispelled=%d",
                provider_name, len(nodes), dispelled_count,
            )

    # ------------------------------------------------------------------
    # Public tracery API
    # ------------------------------------------------------------------

    def is_provider_locked(self, name: str) -> bool:
        """Return ``True`` when *name* is currently locked out by the stream monitor."""
        return self._stream_monitor.is_locked(name)

    def get_research_report(self) -> DataResearchReport:
        """
        Synthesize a :class:`DataResearchReport` from all accumulated tracery
        knowledge.

        The report includes:

        * All detected :class:`SeriesPattern` objects (sorted by coherence).
        * All dispelled :class:`TraceryNode` fake-info entries.
        * Per-provider :class:`AccuracyReport` with lockout status.
        * A plain-English summary narrative.

        Returns:
            A freshly generated :class:`DataResearchReport`.
        """
        series = self._decipher.decipher(self._tracery_store)
        dispelled = self._tracery_store.get_dispelled()
        accuracy_reports = self._stream_monitor.get_accuracy_reports(
            self._tracery_store
        )
        locked = self._stream_monitor.locked_providers

        total = self._tracery_store.total_count
        live = self._tracery_store.live_count
        n_series = len(series)
        coherent_series = sum(
            1 for s in series if s.coherence_score >= _SERIES_COHERENCE_MIN
        )

        parts = [
            f"Tracery store: {total} total claims "
            f"({live} live, {len(dispelled)} dispelled).",
        ]
        if n_series:
            parts.append(
                f"{n_series} series detected; "
                f"{coherent_series} coherent (score ≥ {_SERIES_COHERENCE_MIN:.0%})."
            )
        if dispelled:
            parts.append(
                f"{len(dispelled)} fake/contradictory claim(s) dispelled and logged."
            )
        if locked:
            parts.append(
                f"Inference streams locked out due to low accuracy: "
                f"{', '.join(locked)}."
            )
        if not dispelled and not locked:
            parts.append("All inference streams operating within accuracy thresholds.")

        return DataResearchReport(
            total_nodes=total,
            series_patterns=series,
            dispelled_nodes=dispelled,
            accuracy_reports=accuracy_reports,
            locked_providers=locked,
            summary="  ".join(parts),
        )

    # ------------------------------------------------------------------
    # Internal routing helpers
    # ------------------------------------------------------------------

    async def _query_single(
        self, name: str, prompt: str, context: Dict[str, Any], timestamp: str
    ) -> Dict[str, Any]:
        p = self._providers.get(name)
        if p is None:
            raise ValueError(f"Unknown provider '{name}'. "
                             f"Available: {list(_PROVIDER_REGISTRY)}")
        if not p.is_configured:
            raise RuntimeError(f"Provider '{name}' is not configured (no endpoint).")
        result = await p.query(prompt, context)
        result["timestamp"] = timestamp
        return result

    async def _query_first(
        self, prompt: str, context: Dict[str, Any], timestamp: str
    ) -> Dict[str, Any]:
        ordered = self.configured_providers
        if not ordered:
            return self._no_provider_response(prompt, timestamp)
        result = await self._providers[ordered[0]].query(prompt, context)
        result["timestamp"] = timestamp
        return result

    async def _query_fallback(
        self, prompt: str, context: Dict[str, Any], timestamp: str
    ) -> Dict[str, Any]:
        last_exc: Optional[Exception] = None
        for name in self.configured_providers:
            try:
                result = await self._providers[name].query(prompt, context)
                result["timestamp"] = timestamp
                return result
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("CHAiMERA3sp fallback: provider '%s' failed: %s", name, exc)
                last_exc = exc
        if last_exc:
            logger.error("CHAiMERA3sp: all providers failed. Last error: %s", last_exc)
        return self._no_provider_response(prompt, timestamp)

    async def _query_broadcast(
        self, prompt: str, context: Dict[str, Any], timestamp: str
    ) -> Dict[str, Any]:
        import asyncio  # local import to keep module import light
        configured = self.configured_providers
        if not configured:
            return self._no_provider_response(prompt, timestamp)

        async def _safe_query(name: str) -> Dict[str, Any]:
            try:
                return await self._providers[name].query(prompt, context)
            except Exception as exc:  # pylint: disable=broad-except
                return {"provider": name, "response": "", "error": str(exc)}

        results = await asyncio.gather(*[_safe_query(n) for n in configured])
        for r in results:
            r["timestamp"] = timestamp
        return {
            "strategy": "broadcast",
            "responses": list(results),
            "timestamp": timestamp,
        }

    @staticmethod
    def _no_provider_response(prompt: str, timestamp: str) -> Dict[str, Any]:
        return {
            "provider": "none",
            "response": "",
            "prompt": prompt,
            "error": "No CHAiMERA3sp providers are configured.",
            "timestamp": timestamp,
        }

