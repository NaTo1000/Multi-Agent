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
"""

import json
import logging
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .hiai import HiAiModule

logger = logging.getLogger(__name__)


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

        configured = [n for n in self._priority if self._providers[n].is_configured]
        logger.info(
            "CHAiMERA3sp initialised | strategy=%s | configured providers: %s",
            self._strategy,
            configured or ["none"],
        )

    @property
    def configured_providers(self) -> List[str]:
        """Return the names of providers that have a non-empty endpoint configured."""
        return [n for n in self._priority if self._providers[n].is_configured]

    async def query(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Route a query to the appropriate provider(s).

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
            return await self._query_single(provider, prompt, context, timestamp)

        if self._strategy == "broadcast":
            return await self._query_broadcast(prompt, context, timestamp)

        if self._strategy == "fallback":
            return await self._query_fallback(prompt, context, timestamp)

        # default: "first"
        return await self._query_first(prompt, context, timestamp)

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
