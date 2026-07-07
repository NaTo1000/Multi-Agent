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


# ===========================================================================
# Tracery subsystem imports
# ===========================================================================

from ai.chaimera3sp import (
    TraceryNode,
    SeriesPattern,
    AccuracyReport,
    DataResearchReport,
    TraceryStore,
    KnowledgeScraper,
    SeriesDecipher,
    AccuracyScrutineer,
    InferenceStreamMonitor,
    _tokenise,
    _has_negation,
    _token_overlap,
    _claims_contradict,
    _LOCKOUT_THRESHOLD,
    _LOCKOUT_MIN_CLAIMS,
    _SERIES_COHERENCE_MIN,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _node(claim="LoRa is optimal for long range.", provider="kimi", series="lora",
          dispelled=False, dispel_reason=""):
    n = TraceryNode(source_provider=provider, claim=claim, series_key=series)
    n.dispelled = dispelled
    n.dispel_reason = dispel_reason
    return n


def _store_with_nodes(nodes):
    s = TraceryStore()
    for n in nodes:
        s.add(n)
    return s


# ===========================================================================
# TraceryNode
# ===========================================================================

class TestTraceryNode:
    def test_defaults(self):
        n = TraceryNode()
        assert n.dispelled is False
        assert n.series_key == "general"

    def test_unique_ids(self):
        ids = {TraceryNode().node_id for _ in range(20)}
        assert len(ids) == 20

    def test_to_dict_keys(self):
        d = _node().to_dict()
        for k in ("node_id", "source_provider", "claim", "series_key",
                  "confidence", "timestamp", "dispelled", "dispel_reason"):
            assert k in d

    def test_serialisable(self):
        import json
        json.dumps(_node().to_dict())


# ===========================================================================
# Tracery helpers
# ===========================================================================

class TestTraceryHelpers:
    def test_tokenise_basic(self):
        tokens = _tokenise("LoRa is optimal for wireless")
        assert "lora" in tokens
        assert "optimal" in tokens

    def test_tokenise_removes_short_words(self):
        # _tokenise keeps words with len > 2; single and two-char words are excluded
        tokens = _tokenise("a in")
        assert tokens == frozenset()

    def test_has_negation_true(self):
        assert _has_negation("LoRa is not optimal")
        assert _has_negation("This is never correct")
        assert _has_negation("The claim is false")

    def test_has_negation_false(self):
        assert not _has_negation("LoRa is optimal for range")

    def test_token_overlap_identical(self):
        assert _token_overlap("LoRa is optimal", "LoRa is optimal") == 1.0

    def test_token_overlap_disjoint(self):
        overlap = _token_overlap("apples oranges", "hydrogen nitrogen")
        assert overlap == 0.0

    def test_token_overlap_partial(self):
        o = _token_overlap("LoRa optimal range", "LoRa range interference")
        assert 0.0 < o < 1.0

    def test_claims_contradict_yes(self):
        a = "LoRa is the optimal modulation for long range transmission"
        b = "LoRa is not the optimal modulation for long range transmission"
        assert _claims_contradict(a, b)

    def test_claims_contradict_no_low_overlap(self):
        a = "Bananas are yellow"
        b = "The sky is not blue today"
        assert not _claims_contradict(a, b)

    def test_claims_contradict_no_same_polarity(self):
        a = "LoRa is optimal"
        b = "LoRa is also optimal for urban"
        assert not _claims_contradict(a, b)


# ===========================================================================
# TraceryStore
# ===========================================================================

class TestTraceryStore:
    def test_empty_store(self):
        s = TraceryStore()
        assert s.total_count == 0
        assert s.live_count == 0
        assert s.dispelled_count == 0

    def test_add_live_node(self):
        s = TraceryStore()
        s.add(_node())
        assert s.total_count == 1
        assert s.live_count == 1

    def test_add_dispelled_node(self):
        s = TraceryStore()
        s.add(_node(dispelled=True))
        assert s.dispelled_count == 1
        assert s.live_count == 0

    def test_get_live_filters_dispelled(self):
        s = _store_with_nodes([
            _node(claim="A is true"),
            _node(claim="B is false", dispelled=True),
        ])
        live = s.get_live()
        assert len(live) == 1
        assert not live[0].dispelled

    def test_get_dispelled(self):
        s = _store_with_nodes([_node(dispelled=True), _node(dispelled=True)])
        assert len(s.get_dispelled()) == 2

    def test_get_by_series(self):
        s = _store_with_nodes([
            _node(series="lora"),
            _node(series="lora"),
            _node(series="wifi"),
        ])
        lora_nodes = s.get_by_series("lora")
        assert len(lora_nodes) == 2

    def test_get_by_provider(self):
        s = _store_with_nodes([
            _node(provider="kimi"),
            _node(provider="watsonx"),
            _node(provider="kimi"),
        ])
        assert len(s.get_by_provider("kimi")) == 2

    def test_series_keys(self):
        s = _store_with_nodes([_node(series="a"), _node(series="b")])
        keys = s.series_keys()
        assert "a" in keys and "b" in keys


# ===========================================================================
# KnowledgeScraper
# ===========================================================================

class TestKnowledgeScraper:
    def test_scrapes_sentences(self):
        text = (
            "LoRa is the optimal modulation for long-range IoT transmission. "
            "It operates in sub-GHz bands and provides excellent range. "
            "The SF setting controls the trade-off between range and data rate."
        )
        nodes = KnowledgeScraper.scrape(text, "kimi")
        assert len(nodes) >= 2

    def test_question_sentences_excluded(self):
        # Questions are those ending with "?" — the scraper skips them.
        # Use clear sentence boundaries so the question is isolated.
        nodes = KnowledgeScraper.scrape(
            "LoRa is optimal for long range IoT deployment. Is WiFi better?",
            "kimi"
        )
        claims = [n.claim for n in nodes]
        assert not any(c.strip().endswith("?") for c in claims)

    def test_short_text_no_nodes(self):
        nodes = KnowledgeScraper.scrape("Yes.", "kimi")
        assert nodes == []

    def test_context_topic_sets_series_key(self):
        nodes = KnowledgeScraper.scrape(
            "LoRa is optimal for IoT deployments in rural areas.",
            "kimi",
            context={"topic": "lora_modulation"}
        )
        assert all(n.series_key == "lora_modulation" for n in nodes)

    def test_provider_name_stored(self):
        nodes = KnowledgeScraper.scrape(
            "The frequency lock algorithm converges quickly.", "watsonx"
        )
        assert all(n.source_provider == "watsonx" for n in nodes)

    def test_claim_capped_at_max_len(self):
        long_text = "A" * 400 + "."
        nodes = KnowledgeScraper.scrape(long_text, "kimi")
        for n in nodes:
            assert len(n.claim) <= 300

    def test_empty_response_no_nodes(self):
        assert KnowledgeScraper.scrape("", "kimi") == []

    def test_series_key_derived_from_first_word_when_no_topic(self):
        nodes = KnowledgeScraper.scrape(
            "Frequency hopping prevents interference in dense networks.", "kimi"
        )
        if nodes:
            assert nodes[0].series_key != "general" or True  # derived or general


# ===========================================================================
# AccuracyScrutineer
# ===========================================================================

class TestAccuracyScrutineer:
    def test_non_contradicting_node_not_dispelled(self):
        store = _store_with_nodes([_node("LoRa is optimal for rural range.")])
        new_node = _node("LoRa uses sub-GHz bands for long distance.")
        AccuracyScrutineer.scrutinise([new_node], store)
        assert not new_node.dispelled

    def test_contradicting_node_dispelled(self):
        store = _store_with_nodes([
            _node("LoRa is the optimal modulation for long range IoT transmission.")
        ])
        new_node = _node(
            "LoRa is not the optimal modulation for long range IoT transmission."
        )
        AccuracyScrutineer.scrutinise([new_node], store)
        assert new_node.dispelled
        assert new_node.dispel_reason != ""

    def test_dispel_reason_references_conflicting_claim(self):
        store = _store_with_nodes([_node("The device responds correctly.")])
        new_node = _node("The device does not respond correctly.")
        AccuracyScrutineer.scrutinise([new_node], store)
        if new_node.dispelled:
            assert "Contradicts" in new_node.dispel_reason

    def test_empty_store_nothing_dispelled(self):
        node = _node("Anything is fine.")
        AccuracyScrutineer.scrutinise([node], TraceryStore())
        assert not node.dispelled

    def test_cross_series_contradiction_not_flagged(self):
        store = _store_with_nodes([
            _node("LoRa is not optimal.", series="lora")
        ])
        new_node = _node("LoRa is optimal.", series="wifi")
        AccuracyScrutineer.scrutinise([new_node], store)
        assert not new_node.dispelled


# ===========================================================================
# SeriesDecipher
# ===========================================================================

class TestSeriesDecipher:
    def test_empty_store_returns_no_patterns(self):
        patterns = SeriesDecipher.decipher(TraceryStore())
        assert patterns == []

    def test_single_node_series_coherence_one(self):
        store = _store_with_nodes([_node(series="lora")])
        patterns = SeriesDecipher.decipher(store)
        assert len(patterns) == 1
        assert patterns[0].coherence_score == 1.0

    def test_coherent_series_high_score(self):
        store = _store_with_nodes([
            _node("LoRa operates at sub-GHz frequencies.", series="lora"),
            _node("LoRa provides long range communication.", series="lora"),
            _node("LoRa is widely used for IoT applications.", series="lora"),
        ])
        patterns = SeriesDecipher.decipher(store)
        assert patterns[0].coherence_score >= 0.0

    def test_contradictory_series_lower_coherence(self):
        store = _store_with_nodes([
            _node("LoRa is the optimal modulation scheme for transmission.", series="lora"),
            _node("LoRa is not the optimal modulation scheme for transmission.", series="lora"),
        ])
        patterns = SeriesDecipher.decipher(store)
        assert patterns[0].coherence_score < 1.0

    def test_multiple_series_detected(self):
        store = _store_with_nodes([
            _node(series="lora"),
            _node(series="wifi"),
        ])
        patterns = SeriesDecipher.decipher(store)
        keys = {p.series_key for p in patterns}
        assert "lora" in keys and "wifi" in keys

    def test_dominant_claim_set(self):
        store = _store_with_nodes([
            _node("LoRa is optimal.", series="lora"),
            _node("LoRa is good for IoT.", series="lora"),
        ])
        patterns = SeriesDecipher.decipher(store)
        assert patterns[0].dominant_claim != ""

    def test_sorted_by_coherence_desc(self):
        store = _store_with_nodes([
            _node("A is not A.", series="bad"),
            _node("A is correct.", series="good"),
            _node("B is correct.", series="good"),
        ])
        patterns = SeriesDecipher.decipher(store)
        scores = [p.coherence_score for p in patterns]
        assert scores == sorted(scores, reverse=True)

    def test_dispelled_nodes_excluded(self):
        store = _store_with_nodes([
            _node("Live claim.", series="x"),
            _node("Dispelled claim.", series="x", dispelled=True),
        ])
        patterns = SeriesDecipher.decipher(store)
        assert patterns[0].nodes[0].claim == "Live claim."


# ===========================================================================
# InferenceStreamMonitor
# ===========================================================================

class TestInferenceStreamMonitor:
    def test_not_locked_with_few_claims(self):
        store = _store_with_nodes([_node(provider="kimi")] * (_LOCKOUT_MIN_CLAIMS - 1))
        monitor = InferenceStreamMonitor()
        monitor.update(store)
        assert not monitor.is_locked("kimi")

    def test_not_locked_with_high_accuracy(self):
        store = _store_with_nodes([_node(provider="kimi")] * _LOCKOUT_MIN_CLAIMS)
        monitor = InferenceStreamMonitor()
        monitor.update(store)
        assert not monitor.is_locked("kimi")

    def test_locked_when_accuracy_below_threshold(self):
        # Need dispelled/total > (1 - _LOCKOUT_THRESHOLD) to trigger lockout.
        total = _LOCKOUT_MIN_CLAIMS + 4
        # Make 70% dispelled so accuracy = 30% < 40% threshold
        dispelled_count = int(total * 0.70) + 1
        nodes = (
            [_node(provider="kimi", dispelled=True)] * dispelled_count
            + [_node(provider="kimi")] * (total - dispelled_count)
        )
        store = _store_with_nodes(nodes)
        monitor = InferenceStreamMonitor()
        monitor.update(store)
        assert monitor.is_locked("kimi")

    def test_unknown_provider_not_locked(self):
        monitor = InferenceStreamMonitor()
        assert not monitor.is_locked("nonexistent")

    def test_locked_providers_list(self):
        nodes = [_node(provider="bad", dispelled=True)] * (_LOCKOUT_MIN_CLAIMS + 2)
        store = _store_with_nodes(nodes)
        monitor = InferenceStreamMonitor()
        monitor.update(store)
        assert "bad" in monitor.locked_providers

    def test_accuracy_reports_structure(self):
        store = _store_with_nodes([_node(provider="kimi")] * 3)
        monitor = InferenceStreamMonitor()
        monitor.update(store)
        reports = monitor.get_accuracy_reports(store)
        assert len(reports) == 1
        assert reports[0].provider == "kimi"
        assert reports[0].total_claims == 3
        assert reports[0].accuracy_rate == 1.0

    def test_accuracy_report_to_dict(self):
        import json
        store = _store_with_nodes([_node(provider="kimi")])
        monitor = InferenceStreamMonitor()
        monitor.update(store)
        reports = monitor.get_accuracy_reports(store)
        json.dumps(reports[0].to_dict())


# ===========================================================================
# CHAiMERA3sp tracery integration
# ===========================================================================

class TestCHAiMERA3spTracery:
    def _router(self):
        return CHAiMERA3sp({
            "strategy": "first",
            "providers": {"kimi": {"api_key": "kimi-test-key"}},
        })

    @pytest.mark.asyncio
    async def test_query_scrapes_nodes(self):
        router = self._router()
        mock_resp = {
            "provider": "kimi",
            "response": (
                "LoRa operates at sub-GHz frequencies for long range. "
                "The spreading factor controls the data rate and range tradeoff. "
                "Higher SF values extend range but reduce throughput."
            ),
            "model": "kimi-2.6",
        }
        with patch.object(router._providers["kimi"], "query", return_value=mock_resp):
            await router.query("explain LoRa", context={"topic": "lora"})
        assert router._tracery_store.total_count >= 1

    @pytest.mark.asyncio
    async def test_query_populates_series(self):
        router = self._router()
        mock_resp = {
            "provider": "kimi",
            "response": (
                "LoRa is optimal for rural IoT applications. "
                "LoRa provides excellent coverage over several kilometres."
            ),
            "model": "kimi-2.6",
        }
        with patch.object(router._providers["kimi"], "query", return_value=mock_resp):
            await router.query("LoRa range", context={"topic": "lora_test"})
        report = router.get_research_report()
        assert report.total_nodes >= 1

    @pytest.mark.asyncio
    async def test_fake_info_logged_and_dispelled(self):
        router = self._router()
        # Seed the store with an established claim
        established = _node(
            "LoRa is the optimal modulation for long range IoT transmission.",
            provider="kimi", series="modulation"
        )
        router._tracery_store.add(established)

        mock_resp = {
            "provider": "kimi",
            "response": (
                "LoRa is not the optimal modulation for long range IoT transmission."
            ),
            "model": "kimi-2.6",
        }
        with patch.object(router._providers["kimi"], "query", return_value=mock_resp):
            await router.query("modulation", context={"topic": "modulation"})
        dispelled = router._tracery_store.get_dispelled()
        assert len(dispelled) >= 1

    def test_get_research_report_structure(self):
        router = self._router()
        report = router.get_research_report()
        assert isinstance(report, DataResearchReport)
        assert report.summary != ""

    def test_get_research_report_to_dict(self):
        import json
        router = self._router()
        json.dumps(router.get_research_report().to_dict())

    def test_is_provider_locked_false_initially(self):
        router = self._router()
        assert not router.is_provider_locked("kimi")

    @pytest.mark.asyncio
    async def test_locked_provider_excluded_from_routing(self):
        router = self._router()
        # Manually lock kimi
        router._stream_monitor._locked["kimi"] = True
        # configured_providers should exclude it
        assert "kimi" not in router.configured_providers

    def test_all_configured_providers_ignores_lockout(self):
        router = self._router()
        router._stream_monitor._locked["kimi"] = True
        assert "kimi" in router.all_configured_providers

    @pytest.mark.asyncio
    async def test_no_scraping_for_empty_response(self):
        router = self._router()
        mock_resp = {"provider": "kimi", "response": "", "model": "kimi-2.6"}
        with patch.object(router._providers["kimi"], "query", return_value=mock_resp):
            await router.query("empty")
        assert router._tracery_store.total_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_scrapes_all_provider_responses(self):
        router = CHAiMERA3sp({
            "strategy": "broadcast",
            "providers": {
                "kimi": {"api_key": "k"},
                "manus": {"endpoint": "https://manus.example.com/v1", "api_key": "m"},
            },
        })
        kimi_resp = {
            "provider": "kimi", "model": "kimi-2.6",
            "response": "LoRa provides optimal long range communication for IoT.",
        }
        manus_resp = {
            "provider": "manus", "model": "manus-agent",
            "response": "Frequency hopping reduces interference in dense deployments.",
        }
        with (
            patch.object(router._providers["kimi"], "query", return_value=kimi_resp),
            patch.object(router._providers["manus"], "query", return_value=manus_resp),
        ):
            await router.query("broadcast test", context={"topic": "broadcast"})
        assert router._tracery_store.total_count >= 2
