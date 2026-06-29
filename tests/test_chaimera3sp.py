"""
Tests for CHAiMERA3sp — multi-AI provider router.
All provider HTTP calls are mocked so no real network access is needed.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ai.chaimera3sp import (
    CHAiMERA3sp,
    WatsonxProvider,
    Kai9000Provider,
    KimiProvider,
    ManusProvider,
)


# ---------------------------------------------------------------------------
# Provider unit tests
# ---------------------------------------------------------------------------

class TestWatsonxProvider:
    def _provider(self, extra=None):
        cfg = {"endpoint": "https://example.com/watsonx", "api_key": "test-key", **(extra or {})}
        return WatsonxProvider(cfg)

    def test_is_configured(self):
        p = self._provider()
        assert p.is_configured is True

    def test_not_configured_without_endpoint(self):
        p = WatsonxProvider({})
        assert p.is_configured is False

    @pytest.mark.asyncio
    async def test_query_success(self):
        p = self._provider()
        mock_resp = {"results": [{"generated_text": "LoRa is optimal"}]}
        with patch.object(p, "_http_post", return_value=mock_resp):
            result = await p.query("best modulation?", {})
        assert result["provider"] == "watsonx"
        assert result["response"] == "LoRa is optimal"

    @pytest.mark.asyncio
    async def test_query_uses_model_id(self):
        p = self._provider({"model_id": "ibm/granite-3b"})
        mock_resp = {"results": [{"generated_text": "Use GFSK"}]}
        captured = {}
        def capture(url, payload, headers):
            captured["payload"] = payload
            return mock_resp
        with patch.object(p, "_http_post", side_effect=capture):
            await p.query("test", {})
        assert captured["payload"]["model_id"] == "ibm/granite-3b"

    @pytest.mark.asyncio
    async def test_query_raises_on_http_error(self):
        p = self._provider()
        with patch.object(p, "_http_post", side_effect=RuntimeError("network fail")):
            with pytest.raises(RuntimeError):
                await p.query("test", {})


class TestKai9000Provider:
    def _provider(self, extra=None):
        cfg = {"endpoint": "https://kai9000.example.com/infer", **(extra or {})}
        return Kai9000Provider(cfg)

    def test_is_configured(self):
        assert self._provider().is_configured is True

    def test_not_configured(self):
        assert Kai9000Provider({}).is_configured is False

    @pytest.mark.asyncio
    async def test_query_success(self):
        p = self._provider()
        mock_resp = {"response": "Use 915 MHz LoRa"}
        with patch.object(p, "_http_post", return_value=mock_resp):
            result = await p.query("best band?", {})
        assert result["provider"] == "kai9000"
        assert result["response"] == "Use 915 MHz LoRa"

    @pytest.mark.asyncio
    async def test_query_fallback_fields(self):
        p = self._provider()
        for field in ("text", "output"):
            mock_resp = {field: "answer via " + field}
            with patch.object(p, "_http_post", return_value=mock_resp):
                result = await p.query("q", {})
            assert "answer via" in result["response"]


class TestKimiProvider:
    def _provider(self, extra=None):
        cfg = {"api_key": "kimi-key", **(extra or {})}
        return KimiProvider(cfg)

    def test_default_endpoint(self):
        p = self._provider()
        assert "moonshot" in p._endpoint

    def test_is_configured_with_default_endpoint(self):
        p = self._provider()
        assert p.is_configured is True

    @pytest.mark.asyncio
    async def test_query_success(self):
        p = self._provider()
        mock_resp = {
            "choices": [{"message": {"content": "Kimi recommends LoRa for long-range"}}]
        }
        captured = {}
        def capture(url, payload, headers):
            captured["url"] = url
            return mock_resp
        with patch.object(p, "_http_post", side_effect=capture):
            result = await p.query("range question", {})
        assert result["provider"] == "kimi"
        assert "LoRa" in result["response"]
        assert captured["url"].endswith("/chat/completions")

    @pytest.mark.asyncio
    async def test_query_uses_model(self):
        p = self._provider({"model": "kimi-2.6"})
        mock_resp = {"choices": [{"message": {"content": "ok"}}]}
        captured = {}
        def capture(url, payload, headers):
            captured["payload"] = payload
            return mock_resp
        with patch.object(p, "_http_post", side_effect=capture):
            await p.query("q", {})
        assert captured["payload"]["model"] == "kimi-2.6"


class TestManusProvider:
    def _provider(self, extra=None):
        cfg = {"endpoint": "https://api.manus.example.com/v1", "api_key": "m-key", **(extra or {})}
        return ManusProvider(cfg)

    def test_is_configured(self):
        assert self._provider().is_configured is True

    def test_not_configured(self):
        assert ManusProvider({}).is_configured is False

    @pytest.mark.asyncio
    async def test_query_success(self):
        p = self._provider()
        mock_resp = {"result": "Manus suggests channel hop"}
        captured = {}
        def capture(url, payload, headers):
            captured["url"] = url
            return mock_resp
        with patch.object(p, "_http_post", side_effect=capture):
            result = await p.query("interference?", {})
        assert result["provider"] == "manus"
        assert "Manus" in result["response"]
        assert captured["url"].endswith("/run")

    @pytest.mark.asyncio
    async def test_query_fallback_fields(self):
        p = self._provider()
        for field in ("output", "response"):
            mock_resp = {field: "via " + field}
            with patch.object(p, "_http_post", return_value=mock_resp):
                result = await p.query("q", {})
            assert "via " + field == result["response"]


# ---------------------------------------------------------------------------
# CHAiMERA3sp router tests
# ---------------------------------------------------------------------------

def _make_router(strategy="first", configured_providers=("kimi",)):
    """Build a CHAiMERA3sp with only the specified providers configured."""
    provider_cfgs = {}
    for name in configured_providers:
        if name == "watsonx":
            provider_cfgs["watsonx"] = {
                "endpoint": "https://watsonx.example.com",
                "api_key": "wx-key",
            }
        elif name == "kimi":
            provider_cfgs["kimi"] = {"api_key": "kimi-key"}
        elif name == "kai9000":
            provider_cfgs["kai9000"] = {"endpoint": "https://kai9000.example.com"}
        elif name == "manus":
            provider_cfgs["manus"] = {
                "endpoint": "https://manus.example.com/v1",
                "api_key": "m-key",
            }
    return CHAiMERA3sp({
        "strategy": strategy,
        "providers": provider_cfgs,
    })


class TestCHAiMERA3spRouter:
    def test_configured_providers_list(self):
        router = _make_router(configured_providers=("kimi", "manus"))
        names = router.configured_providers
        assert "kimi" in names
        assert "manus" in names
        assert "kai9000" not in names

    def test_no_providers_configured(self):
        router = CHAiMERA3sp({})
        assert router.configured_providers == []

    @pytest.mark.asyncio
    async def test_strategy_first_selects_first_configured(self):
        router = _make_router(strategy="first", configured_providers=("kimi",))
        mock_resp = {
            "provider": "kimi",
            "response": "Use LoRa",
            "model": "kimi-2.6",
        }
        with patch.object(router._providers["kimi"], "query", return_value=mock_resp):
            result = await router.query("best modulation?")
        assert result["provider"] == "kimi"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_strategy_fallback_skips_failing_provider(self):
        router = _make_router(strategy="fallback", configured_providers=("watsonx", "kimi"))
        good_resp = {"provider": "kimi", "response": "ok", "model": "kimi-2.6"}
        with (
            patch.object(router._providers["watsonx"], "query", side_effect=RuntimeError("fail")),
            patch.object(router._providers["kimi"], "query", return_value=good_resp),
        ):
            result = await router.query("test")
        assert result["provider"] == "kimi"

    @pytest.mark.asyncio
    async def test_strategy_broadcast_returns_all(self):
        router = _make_router(strategy="broadcast", configured_providers=("kimi", "manus"))
        kimi_resp = {"provider": "kimi", "response": "kimi says A", "model": "kimi-2.6"}
        manus_resp = {"provider": "manus", "response": "manus says B", "model": "manus-agent"}
        with (
            patch.object(router._providers["kimi"], "query", return_value=kimi_resp),
            patch.object(router._providers["manus"], "query", return_value=manus_resp),
        ):
            result = await router.query("broadcast test")
        assert result["strategy"] == "broadcast"
        providers_in_resp = {r["provider"] for r in result["responses"]}
        assert "kimi" in providers_in_resp
        assert "manus" in providers_in_resp

    @pytest.mark.asyncio
    async def test_no_provider_response_when_none_configured(self):
        router = CHAiMERA3sp({})
        result = await router.query("anything")
        assert result["provider"] == "none"
        assert result["response"] == ""
        assert "error" in result

    @pytest.mark.asyncio
    async def test_explicit_provider_selection(self):
        router = _make_router(configured_providers=("kimi", "manus"))
        manus_resp = {"provider": "manus", "response": "manus answer", "model": "manus-agent"}
        with patch.object(router._providers["manus"], "query", return_value=manus_resp):
            result = await router.query("test", provider="manus")
        assert result["provider"] == "manus"

    @pytest.mark.asyncio
    async def test_explicit_unknown_provider_raises(self):
        router = _make_router(configured_providers=("kimi",))
        with pytest.raises(ValueError, match="Unknown provider"):
            await router.query("test", provider="nonexistent")

    @pytest.mark.asyncio
    async def test_explicit_unconfigured_provider_raises(self):
        router = CHAiMERA3sp({"providers": {}})
        with pytest.raises(RuntimeError, match="not configured"):
            await router.query("test", provider="kai9000")

    @pytest.mark.asyncio
    async def test_fallback_all_fail_returns_no_provider(self):
        router = _make_router(strategy="fallback", configured_providers=("kimi",))
        with patch.object(router._providers["kimi"], "query", side_effect=RuntimeError("down")):
            result = await router.query("test")
        assert result["provider"] == "none"

    @pytest.mark.asyncio
    async def test_broadcast_partial_failure_included_in_responses(self):
        router = _make_router(strategy="broadcast", configured_providers=("kimi", "manus"))
        good_resp = {"provider": "kimi", "response": "ok", "model": "kimi-2.6"}
        with (
            patch.object(router._providers["kimi"], "query", return_value=good_resp),
            patch.object(router._providers["manus"], "query", side_effect=RuntimeError("fail")),
        ):
            result = await router.query("test")
        assert result["strategy"] == "broadcast"
        providers = {r["provider"] for r in result["responses"]}
        assert "kimi" in providers
        assert "manus" in providers  # included with error key
        manus_r = next(r for r in result["responses"] if r["provider"] == "manus")
        assert "error" in manus_r


# ---------------------------------------------------------------------------
# AIAgent integration test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_agent_research_uses_chaimera3sp():
    """AIAgent._research should prefer CHAiMERA3sp when a provider is configured."""
    from agents.ai_agent import AIAgent

    agent = AIAgent({
        "chaimera3sp": {
            "strategy": "first",
            "providers": {
                "kimi": {"api_key": "kimi-key"},
            },
        }
    })
    await agent.start()

    mock_resp = {
        "provider": "kimi",
        "response": "CHAiMERA3sp answer",
        "model": "kimi-2.6",
        "timestamp": "2026-01-01T00:00:00+00:00",
    }
    with patch.object(agent._chaimera, "query", return_value=mock_resp):
        result = await agent.execute("research", {"query": "best modulation"}, None)

    assert result["provider"] == "kimi"
    assert result["source"] == "chaimera3sp"
    assert "CHAiMERA3sp answer" in result["response"]
    await agent.stop()


@pytest.mark.asyncio
async def test_ai_agent_research_falls_back_to_heuristics():
    """AIAgent._research falls back to built-in heuristics when no providers configured."""
    from agents.ai_agent import AIAgent

    agent = AIAgent({})
    await agent.start()
    result = await agent.execute("research", {"query": "best modulation"}, None)
    assert result["source"] == "builtin_heuristics"
    assert "response" in result
    await agent.stop()
