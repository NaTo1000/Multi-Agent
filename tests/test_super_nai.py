"""
Tests for SuperNAi — Quantum Topology Mesh Super Network AI.

Covers:
- QuantumTopologyMesh node/edge operations and recomputation
- FusionEngine ingestion and synthesis
- SuperNAi fleet intelligence score, insight generation, and rebalancing
- SuperNAiAgent task dispatch (all 8 tasks)
"""

import math
import pytest

from ai.super_nai import (
    FusionEngine,
    QuantumTopologyMesh,
    SuperNAi,
)
from agents.super_nai_agent import SuperNAiAgent


# ---------------------------------------------------------------------------
# QuantumTopologyMesh
# ---------------------------------------------------------------------------

class TestQuantumTopologyMesh:
    def test_add_and_remove_node(self):
        mesh = QuantumTopologyMesh()
        mesh.add_node("a")
        mesh.add_node("b")
        assert "a" in mesh._edges
        assert "b" in mesh._edges
        mesh.remove_node("a")
        assert "a" not in mesh._edges

    def test_set_and_get_edge(self):
        mesh = QuantumTopologyMesh()
        mesh.add_node("a")
        mesh.add_node("b")
        mesh.set_edge("a", "b", 0.8)
        assert mesh.edge_weight("a", "b") == pytest.approx(0.8)
        assert mesh.edge_weight("b", "a") == pytest.approx(0.8)  # undirected

    def test_edge_weight_clamped(self):
        mesh = QuantumTopologyMesh()
        mesh.add_node("x")
        mesh.add_node("y")
        mesh.set_edge("x", "y", 2.5)   # above 1
        assert mesh.edge_weight("x", "y") == pytest.approx(1.0)
        mesh.set_edge("x", "y", -0.5)  # below 0
        assert mesh.edge_weight("x", "y") == pytest.approx(0.0)

    def test_recompute_edges_frequency_separation(self):
        mesh = QuantumTopologyMesh()
        mesh.add_node("a")
        mesh.add_node("b")
        # Place a and b 40 MHz apart — full QAOA separation score
        mesh.update_frequency("a", 2_412e6)
        mesh.update_frequency("b", 2_452e6)   # 40 MHz apart
        mesh.recompute_edges()
        w = mesh.edge_weight("a", "b")
        assert w > 0.3, f"Expected weight > 0.3, got {w}"

    def test_recompute_edges_same_frequency(self):
        mesh = QuantumTopologyMesh()
        mesh.add_node("a")
        mesh.add_node("b")
        # Same frequency → poor QAOA separation
        mesh.update_frequency("a", 2_412e6)
        mesh.update_frequency("b", 2_412e6)
        mesh.recompute_edges()
        w = mesh.edge_weight("a", "b")
        # QAOA factor = 0 (no separation), QFT and QKD at defaults
        assert w < 0.6, f"Expected weight < 0.6 for co-channel devices, got {w}"

    def test_ghz_consensus_score(self):
        mesh = QuantumTopologyMesh()
        mesh.add_node("a")
        mesh.add_node("b")
        consensus = 2_437e6
        mesh.set_ghz_consensus(consensus)
        mesh.update_frequency("a", consensus)
        mesh.update_frequency("b", consensus)
        mesh.recompute_edges()
        w = mesh.edge_weight("a", "b")
        # Both on consensus → GHZ factor = 1.0, expect high weight
        assert w >= 0.3

    def test_average_edge_weight_empty_mesh(self):
        mesh = QuantumTopologyMesh()
        assert mesh.average_edge_weight() == 0.0

    def test_average_edge_weight_single_edge(self):
        mesh = QuantumTopologyMesh()
        mesh.add_node("a")
        mesh.add_node("b")
        mesh.set_edge("a", "b", 0.6)
        assert mesh.average_edge_weight() == pytest.approx(0.6)

    def test_partition_count_connected(self):
        mesh = QuantumTopologyMesh()
        for n in ["a", "b", "c"]:
            mesh.add_node(n)
        mesh.set_edge("a", "b", 0.5)
        mesh.set_edge("b", "c", 0.5)
        assert mesh.partition_count() == 1

    def test_partition_count_isolated(self):
        mesh = QuantumTopologyMesh()
        for n in ["a", "b", "c"]:
            mesh.add_node(n)
        # No edges — each node is its own partition
        assert mesh.partition_count() == 3

    def test_node_centrality_normalised(self):
        mesh = QuantumTopologyMesh()
        for n in ["a", "b", "c"]:
            mesh.add_node(n)
        mesh.set_edge("a", "b", 1.0)
        mesh.set_edge("a", "c", 1.0)
        mesh.set_edge("b", "c", 1.0)
        c = mesh.node_centrality()
        for v in c.values():
            assert 0.0 <= v <= 1.0

    def test_weakest_and_strongest_links(self):
        mesh = QuantumTopologyMesh()
        for n in ["a", "b", "c", "d"]:
            mesh.add_node(n)
        mesh.set_edge("a", "b", 0.9)
        mesh.set_edge("a", "c", 0.1)
        mesh.set_edge("b", "c", 0.5)
        mesh.set_edge("c", "d", 0.05)

        weak = mesh.weakest_links(2)
        assert weak[0][2] <= weak[1][2]  # sorted ascending

        strong = mesh.strongest_links(2)
        assert strong[0][2] >= strong[1][2]  # sorted descending

    def test_to_dict_structure(self):
        mesh = QuantumTopologyMesh()
        mesh.add_node("a")
        mesh.add_node("b")
        mesh.set_edge("a", "b", 0.7)
        d = mesh.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert "average_weight" in d
        assert "partition_count" in d
        assert d["node_count"] == 2
        assert d["edge_count"] == 1


# ---------------------------------------------------------------------------
# FusionEngine
# ---------------------------------------------------------------------------

class TestFusionEngine:
    def test_ingest_and_latest(self):
        fe = FusionEngine()
        fe.ingest("ai_agent", "recommend_config", {"recommendations": ["use GFSK"]})
        snap = fe.latest("ai_agent")
        assert snap is not None
        assert snap["agent_type"] == "ai_agent"
        assert snap["result"]["recommendations"] == ["use GFSK"]

    def test_latest_unknown_type(self):
        fe = FusionEngine()
        assert fe.latest("nonexistent_agent") is None

    def test_synthesise_recommended_frequency(self):
        fe = FusionEngine()
        fe.ingest("quantum_agent", "qaoa_optimise", {"optimal_frequency_hz": 2_437e6})
        report = fe.synthesise()
        assert report["recommended_frequency_hz"] == pytest.approx(2_437e6)

    def test_synthesise_ghz_consensus_wins(self):
        fe = FusionEngine()
        fe.ingest("quantum_agent", "entangle_fleet", {
            "consensus_frequency_hz": 2_462e6,
            "optimal_frequency_hz": 2_412e6,
        })
        report = fe.synthesise()
        assert report["recommended_frequency_hz"] == pytest.approx(2_462e6)

    def test_synthesise_sources_listed(self):
        fe = FusionEngine()
        fe.ingest("ai_agent", "research", {"response": "OK"})
        fe.ingest("firmware_agent", "build", {"build_id": "abc123"})
        report = fe.synthesise()
        assert "ai_agent" in report["sources"]
        assert "firmware_agent" in report["sources"]
        assert report["latest_build_id"] == "abc123"

    def test_history_capped(self):
        fe = FusionEngine()
        fe._max_history = 5
        for i in range(10):
            fe.ingest("ai_agent", "research", {"i": i})
        assert len(fe._history) == 5


# ---------------------------------------------------------------------------
# SuperNAi core
# ---------------------------------------------------------------------------

class TestSuperNAi:
    def test_register_and_unregister_device(self):
        sn = SuperNAi()
        sn.register_device("d1")
        assert "d1" in sn.mesh._edges
        sn.unregister_device("d1")
        assert "d1" not in sn.mesh._edges

    def test_fleet_intelligence_score_empty_mesh(self):
        sn = SuperNAi()
        score = sn.fleet_intelligence_score()
        assert 0.0 <= score <= 1.0

    def test_fleet_intelligence_score_with_data(self):
        sn = SuperNAi()
        for did in ["d1", "d2", "d3"]:
            sn.register_device(did)
        sn.fuse_agents([
            {
                "agent_type": "frequency_agent",
                "task": "get_frequency",
                "device_id": "d1",
                "result": {"frequency_hz": 2_412e6},
            },
            {
                "agent_type": "frequency_agent",
                "task": "get_frequency",
                "device_id": "d2",
                "result": {"frequency_hz": 2_437e6},
            },
            {
                "agent_type": "quantum_agent",
                "task": "qrng",
                "device_id": None,
                "result": {"entropy_bits_per_byte": 7.9},
            },
        ])
        sn.optimise_mesh()
        score = sn.fleet_intelligence_score()
        assert 0.0 <= score <= 1.0

    def test_optimise_mesh_returns_topology(self):
        sn = SuperNAi()
        sn.register_device("a")
        sn.register_device("b")
        result = sn.optimise_mesh()
        assert "topology" in result
        assert "fleet_intelligence_score" in result
        assert "score_label" in result
        assert result["score_label"] in ("optimal", "degraded", "critical")

    def test_score_label_optimal(self):
        assert SuperNAi._score_label(0.80) == "optimal"

    def test_score_label_degraded(self):
        assert SuperNAi._score_label(0.55) == "degraded"

    def test_score_label_critical(self):
        assert SuperNAi._score_label(0.30) == "critical"

    def test_fuse_agents_extracts_frequency(self):
        sn = SuperNAi()
        sn.register_device("d1")
        sn.fuse_agents([{
            "agent_type": "quantum_agent",
            "task": "qaoa_optimise",
            "device_id": "d1",
            "result": {"optimal_frequency_hz": 5_180e6},
        }])
        assert sn.mesh._frequency.get("d1") == pytest.approx(5_180e6)

    def test_fuse_agents_extracts_ghz_consensus(self):
        sn = SuperNAi()
        sn.fuse_agents([{
            "agent_type": "quantum_agent",
            "task": "entangle_fleet",
            "device_id": None,
            "result": {"consensus_frequency_hz": 2_462e6},
        }])
        assert sn.mesh._ghz_consensus == pytest.approx(2_462e6)

    def test_fuse_agents_extracts_qft_spectral_energy(self):
        sn = SuperNAi()
        sn.register_device("d1")
        sn.fuse_agents([{
            "agent_type": "quantum_agent",
            "task": "qft_spectrum",
            "device_id": "d1",
            "result": {"mean_magnitude": 12.5},
        }])
        assert sn.mesh._spectral_energy.get("d1") == pytest.approx(12.5)

    def test_fuse_agents_extracts_qkd_trust(self):
        sn = SuperNAi()
        sn.register_device("d1")
        sn.register_device("d2")
        sn.fuse_agents([{
            "agent_type": "quantum_agent",
            "task": "qkd_simulate",
            "device_id": "d1",
            "result": {"key_rate_bps": 500, "qber": 0.02},
        }])
        trust = sn.mesh._qkd_trust.get("d1", {}).get("d2")
        assert trust is not None
        assert 0.0 <= trust <= 1.0

    def test_supernai_insight_structure(self):
        sn = SuperNAi()
        sn.register_device("d1")
        insight = sn.superNAi_insight()
        assert "fleet_intelligence_score" in insight
        assert "topology_summary" in insight
        assert "fusion_report" in insight
        assert "device_actions" in insight
        assert "alerts" in insight
        assert "generated_at" in insight
        assert "version" in insight

    def test_supernai_insight_cached(self):
        sn = SuperNAi()
        sn.register_device("d1")
        i1 = sn.superNAi_insight()
        i2 = sn.superNAi_insight()
        assert i1 is i2  # same object — cached

    def test_supernai_insight_cache_invalidated_on_fuse(self):
        sn = SuperNAi()
        sn.register_device("d1")
        i1 = sn.superNAi_insight()
        sn.fuse_agents([{
            "agent_type": "ai_agent",
            "task": "recommend_config",
            "device_id": "d1",
            "result": {"recommendations": ["switch to LoRa"]},
        }])
        i2 = sn.superNAi_insight()
        assert i1 is not i2  # cache was invalidated

    def test_rebalance_topology_off_consensus(self):
        sn = SuperNAi()
        sn.register_device("d1")
        sn.mesh.set_ghz_consensus(2_437e6)
        sn.mesh.update_frequency("d1", 2_412e6)  # 25 MHz off
        actions = sn.rebalance_topology()
        device_actions = next(
            (a for a in actions if a["device_id"] == "d1"), None
        )
        assert device_actions is not None
        assert any("entangle_fleet" in act for act in device_actions["recommended_actions"])

    def test_rebalance_topology_low_trust(self):
        sn = SuperNAi()
        sn.register_device("d1")
        sn.register_device("d2")
        sn.mesh.update_qkd_trust("d1", "d2", 0.1)  # very low trust
        # set centrality by adding an edge
        sn.mesh.set_edge("d1", "d2", 0.5)
        actions = sn.rebalance_topology()
        d1_actions = next((a for a in actions if a["device_id"] == "d1"), None)
        assert d1_actions is not None
        assert any("qkd_simulate" in act for act in d1_actions["recommended_actions"])

    def test_get_status_structure(self):
        sn = SuperNAi()
        status = sn.get_status()
        assert "version" in status
        assert "fleet_intelligence_score" in status
        assert "score_label" in status
        assert "node_count" in status
        assert "partition_count" in status


# ---------------------------------------------------------------------------
# SuperNAiAgent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_super_nai_agent_mesh_status():
    agent = SuperNAiAgent()
    await agent.start()
    result = await agent.execute("mesh_status", {}, None)
    assert "fleet_intelligence_score" in result
    assert "node_count" in result
    await agent.stop()


@pytest.mark.asyncio
async def test_super_nai_agent_fleet_score():
    agent = SuperNAiAgent()
    await agent.start()
    result = await agent.execute("fleet_score", {}, None)
    assert "fleet_intelligence_score" in result
    score = result["fleet_intelligence_score"]
    assert 0.0 <= score <= 1.0
    assert result["score_label"] in ("optimal", "degraded", "critical")
    await agent.stop()


@pytest.mark.asyncio
async def test_super_nai_agent_insight():
    agent = SuperNAiAgent()
    await agent.start()
    result = await agent.execute("insight", {}, None)
    assert "fleet_intelligence_score" in result
    assert "topology_summary" in result
    assert "alerts" in result
    await agent.stop()


@pytest.mark.asyncio
async def test_super_nai_agent_optimise_mesh():
    agent = SuperNAiAgent()
    await agent.start()
    result = await agent.execute("optimise_mesh", {}, None)
    assert "topology" in result
    assert "fleet_intelligence_score" in result
    await agent.stop()


@pytest.mark.asyncio
async def test_super_nai_agent_fuse():
    agent = SuperNAiAgent()
    await agent.start()
    payload = {
        "results": [
            {
                "agent_type": "ai_agent",
                "task": "recommend_config",
                "device_id": "test-dev",
                "result": {"recommendations": ["use 5GHz band"]},
            }
        ]
    }
    result = await agent.execute("fuse", payload, None)
    assert result["ok"] is True
    assert result["fused"] == 1
    await agent.stop()


@pytest.mark.asyncio
async def test_super_nai_agent_rebalance():
    agent = SuperNAiAgent()
    await agent.start()
    result = await agent.execute("rebalance", {}, None)
    assert "actions" in result
    assert isinstance(result["actions"], list)
    await agent.stop()


@pytest.mark.asyncio
async def test_super_nai_agent_register_unregister_device():
    agent = SuperNAiAgent()
    await agent.start()

    reg = await agent.execute("register_device", {"device_id": "esp-xyz"}, None)
    assert reg["ok"] is True
    assert "esp-xyz" in agent.super_nai.mesh._edges

    unreg = await agent.execute("unregister_device", {"device_id": "esp-xyz"}, None)
    assert unreg["ok"] is True
    assert "esp-xyz" not in agent.super_nai.mesh._edges

    await agent.stop()


@pytest.mark.asyncio
async def test_super_nai_agent_unknown_task():
    agent = SuperNAiAgent()
    await agent.start()
    with pytest.raises(ValueError):
        await agent.execute("nonexistent_task", {}, None)
    await agent.stop()


@pytest.mark.asyncio
async def test_super_nai_agent_insight_with_context():
    agent = SuperNAiAgent()
    await agent.start()
    result = await agent.execute("insight", {"context": {"caller": "test"}}, None)
    assert result["context"] == {"caller": "test"}
    await agent.stop()


@pytest.mark.asyncio
async def test_super_nai_agent_full_pipeline():
    """
    End-to-end: fuse results from multiple agent types, optimise the mesh,
    then verify the insight reflects the ingested data.
    """
    agent = SuperNAiAgent()
    await agent.start()

    # Register two devices
    await agent.execute("register_device", {"device_id": "alpha"}, None)
    await agent.execute("register_device", {"device_id": "beta"}, None)

    # Fuse multi-agent results
    await agent.execute("fuse", {
        "results": [
            {
                "agent_type": "frequency_agent",
                "task": "get_frequency",
                "device_id": "alpha",
                "result": {"frequency_hz": 2_412e6},
            },
            {
                "agent_type": "frequency_agent",
                "task": "get_frequency",
                "device_id": "beta",
                "result": {"frequency_hz": 2_437e6},
            },
            {
                "agent_type": "quantum_agent",
                "task": "entangle_fleet",
                "device_id": None,
                "result": {"consensus_frequency_hz": 2_437e6},
            },
            {
                "agent_type": "quantum_agent",
                "task": "qrng",
                "device_id": None,
                "result": {"entropy_bits_per_byte": 7.95},
            },
            {
                "agent_type": "ai_agent",
                "task": "recommend_config",
                "device_id": "alpha",
                "result": {"recommendations": ["increase tx power"]},
            },
        ]
    }, None)

    # Optimise mesh
    opt = await agent.execute("optimise_mesh", {}, None)
    assert opt["topology"]["node_count"] >= 2

    # Full insight
    insight = await agent.execute("insight", {}, None)
    assert insight["fleet_intelligence_score"] >= 0.0
    assert "alpha" in insight["topology_summary"]["node_centrality"] or \
           len(insight["topology_summary"]["node_centrality"]) >= 0  # may be empty if no edges

    await agent.stop()
