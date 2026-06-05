"""
SuperNAi — Quantum Topology Mesh Super Network AI.

SuperNAi fuses every agent's intelligence stream into a single, self-aware
meta-intelligence layer by modelling the entire device fleet as a *quantum
topology mesh*: a weighted, dynamically-evolving graph whose edges are shaped
by QAOA interference costs, QFT spectral energy, GHZ entanglement consensus,
Grover search hits, and BB84 QKD trust scores.

Architecture
------------

                       ┌─────────────────────────────┐
                       │       SuperNAi               │
                       │   (meta-intelligence layer)  │
                       │                              │
                       │  QuantumTopologyMesh         │
                       │  ┌────────────────────────┐  │
                       │  │  nodes: fleet devices  │  │
                       │  │  edges: QAOA cost graph │  │
                       │  │  fields: QFT spectrum   │  │
                       │  │  state:  GHZ consensus  │  │
                       │  │  trust:  BB84 QKD keys  │  │
                       │  └────────────────────────┘  │
                       │            │                  │
                       │  FusionEngine                 │
                       │  ┌────────────────────────┐  │
                       │  │ FrequencyAgent insights │  │
                       │  │ ModulationAgent signals │  │
                       │  │ AIAgent recommendations │  │
                       │  │ CommsAgent telemetry    │  │
                       │  │ FirmwareAgent builds    │  │
                       │  └────────────────────────┘  │
                       │            │                  │
                       │  Decision layer               │
                       │  ┌────────────────────────┐  │
                       │  │ superNAi_insight()      │  │
                       │  │ fuse_agents()           │  │
                       │  │ optimise_mesh()         │  │
                       │  │ rebalance_topology()    │  │
                       │  └────────────────────────┘  │
                       └─────────────────────────────┘

Quantum Topology Mesh
---------------------
Each device is a node.  An edge (i, j) carries a weight that combines:

    w(i,j) = α * qaoa_separation(i,j)
           + β * qft_coherence(i,j)
           + γ * ghz_consensus_score(i,j)
           + δ * qkd_trust(i,j)

where α+β+γ+δ = 1 and each factor is normalised to [0, 1].

High-weight edges indicate *strongly cooperative* node pairs; low-weight
edges flag interference / trust gaps.  SuperNAi uses this mesh to:

1. Route optimal frequencies across the fleet (mesh-aware QAOA).
2. Propagate AI recommendations only through trusted (high-QKD) paths.
3. Detect topology partitions (isolated clusters) via eigenvector analysis
   of the adjacency matrix — a classical proxy for quantum graph states.
4. Generate a single unified *fleet intelligence score* that drives every
   downstream agent action.
"""

import logging
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default mesh weighting coefficients (must sum to 1.0)
_ALPHA_QAOA = 0.35    # QAOA frequency-separation contribution
_BETA_QFT = 0.25      # QFT spectral-coherence contribution
_GAMMA_GHZ = 0.25     # GHZ entanglement-consensus contribution
_DELTA_QKD = 0.15     # BB84 QKD trust contribution

# Fleet intelligence score thresholds
_SCORE_OPTIMAL = 0.75
_SCORE_DEGRADED = 0.50


# ---------------------------------------------------------------------------
# Quantum Topology Mesh
# ---------------------------------------------------------------------------

class QuantumTopologyMesh:
    """
    A dynamically-updated weighted graph representing the quantum connectivity
    of the device fleet.

    Nodes  — device IDs.
    Edges  — pairwise cooperation weights derived from quantum algorithm
             outputs (QAOA, QFT, GHZ, QKD).
    Fields — per-node scalar fields: frequency, RSSI, spectral energy.
    """

    def __init__(self) -> None:
        # Adjacency: {device_id: {device_id: weight}}
        self._edges: Dict[str, Dict[str, float]] = {}
        # Per-node fields
        self._frequency: Dict[str, float] = {}       # Hz
        self._rssi: Dict[str, float] = {}             # dBm
        self._spectral_energy: Dict[str, float] = {}  # QFT dominant magnitude
        self._qkd_trust: Dict[str, Dict[str, float]] = {}  # pairwise [0,1]
        self._ghz_consensus: Optional[float] = None  # last GHZ consensus freq
        self._updated_at: Optional[str] = None

    # ------------------------------------------------------------------
    # Node / edge management
    # ------------------------------------------------------------------

    def add_node(self, device_id: str) -> None:
        if device_id not in self._edges:
            self._edges[device_id] = {}
            logger.debug("Mesh node added: %s", device_id)

    def remove_node(self, device_id: str) -> None:
        self._edges.pop(device_id, None)
        for neighbors in self._edges.values():
            neighbors.pop(device_id, None)
        self._frequency.pop(device_id, None)
        self._rssi.pop(device_id, None)
        self._spectral_energy.pop(device_id, None)
        self._qkd_trust.pop(device_id, None)
        logger.debug("Mesh node removed: %s", device_id)

    def set_edge(self, a: str, b: str, weight: float) -> None:
        weight = max(0.0, min(1.0, weight))
        self._edges.setdefault(a, {})[b] = weight
        self._edges.setdefault(b, {})[a] = weight  # undirected

    def edge_weight(self, a: str, b: str) -> float:
        return self._edges.get(a, {}).get(b, 0.0)

    # ------------------------------------------------------------------
    # Field updates (fed by agent task results)
    # ------------------------------------------------------------------

    def update_frequency(self, device_id: str, freq_hz: float) -> None:
        self._frequency[device_id] = freq_hz
        self._touch()

    def update_rssi(self, device_id: str, rssi_dbm: float) -> None:
        self._rssi[device_id] = rssi_dbm
        self._touch()

    def update_spectral_energy(self, device_id: str, magnitude: float) -> None:
        self._spectral_energy[device_id] = magnitude
        self._touch()

    def update_qkd_trust(self, device_id: str, peer_id: str, score: float) -> None:
        score = max(0.0, min(1.0, score))
        self._qkd_trust.setdefault(device_id, {})[peer_id] = score
        self._qkd_trust.setdefault(peer_id, {})[device_id] = score
        self._touch()

    def set_ghz_consensus(self, freq_hz: float) -> None:
        self._ghz_consensus = freq_hz
        self._touch()

    # ------------------------------------------------------------------
    # Mesh recomputation
    # ------------------------------------------------------------------

    def recompute_edges(self) -> None:
        """
        Recompute all pairwise edge weights from current field values using
        the quantum cooperation formula:

            w(i,j) = α * qaoa_sep(i,j)
                   + β * qft_coh(i,j)
                   + γ * ghz_score(i,j)
                   + δ * qkd_trust(i,j)
        """
        nodes = list(self._edges.keys())
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                w = (
                    _ALPHA_QAOA * self._qaoa_separation(a, b)
                    + _BETA_QFT * self._qft_coherence(a, b)
                    + _GAMMA_GHZ * self._ghz_score(a, b)
                    + _DELTA_QKD * self._qkd_score(a, b)
                )
                self.set_edge(a, b, w)
        logger.debug("Mesh edges recomputed for %d nodes", len(nodes))

    # ------------------------------------------------------------------
    # Topology analytics
    # ------------------------------------------------------------------

    def average_edge_weight(self) -> float:
        """Mean pairwise cooperation weight across the mesh."""
        weights: List[float] = []
        seen: set = set()
        for a, neighbors in self._edges.items():
            for b, w in neighbors.items():
                key = tuple(sorted([a, b]))
                if key not in seen:
                    weights.append(w)
                    seen.add(key)
        return sum(weights) / len(weights) if weights else 0.0

    def weakest_links(self, top_n: int = 3) -> List[Tuple[str, str, float]]:
        """Return the top_n lowest-weight edges (most problematic pairs)."""
        pairs: List[Tuple[str, str, float]] = []
        seen: set = set()
        for a, neighbors in self._edges.items():
            for b, w in neighbors.items():
                key = tuple(sorted([a, b]))
                if key not in seen:
                    pairs.append((a, b, w))
                    seen.add(key)
        pairs.sort(key=lambda t: t[2])
        return pairs[:top_n]

    def strongest_links(self, top_n: int = 3) -> List[Tuple[str, str, float]]:
        """Return the top_n highest-weight edges (best-cooperating pairs)."""
        pairs: List[Tuple[str, str, float]] = []
        seen: set = set()
        for a, neighbors in self._edges.items():
            for b, w in neighbors.items():
                key = tuple(sorted([a, b]))
                if key not in seen:
                    pairs.append((a, b, w))
                    seen.add(key)
        pairs.sort(key=lambda t: t[2], reverse=True)
        return pairs[:top_n]

    def node_centrality(self) -> Dict[str, float]:
        """
        Degree-weighted centrality: sum of edge weights incident to each node,
        normalised by the maximum possible (N-1 fully-connected mesh weight).
        """
        nodes = list(self._edges.keys())
        n = len(nodes)
        if n <= 1:
            return {nid: 1.0 for nid in nodes}
        max_weight = n - 1  # all edges weight=1
        centrality = {}
        for node in nodes:
            total = sum(self._edges[node].values())
            centrality[node] = total / max_weight
        return centrality

    def partition_count(self) -> int:
        """
        Count connected components via BFS — detects topology fragmentation.
        A partition count > 1 means isolated device clusters.
        """
        nodes = set(self._edges.keys())
        visited: set = set()
        components = 0
        for start in nodes:
            if start in visited:
                continue
            components += 1
            queue = [start]
            while queue:
                node = queue.pop()
                if node in visited:
                    continue
                visited.add(node)
                for neighbor, w in self._edges.get(node, {}).items():
                    if neighbor not in visited and w > 0:
                        queue.append(neighbor)
        return components

    def to_dict(self) -> Dict[str, Any]:
        nodes = list(self._edges.keys())
        edges_out = []
        seen: set = set()
        for a, neighbors in self._edges.items():
            for b, w in neighbors.items():
                key = tuple(sorted([a, b]))
                if key not in seen:
                    edges_out.append({"a": a, "b": b, "weight": round(w, 4)})
                    seen.add(key)
        return {
            "nodes": nodes,
            "node_count": len(nodes),
            "edges": edges_out,
            "edge_count": len(edges_out),
            "average_weight": round(self.average_edge_weight(), 4),
            "partition_count": self.partition_count(),
            "centrality": {k: round(v, 4) for k, v in self.node_centrality().items()},
            "ghz_consensus_mhz": (
                round(self._ghz_consensus / 1e6, 3) if self._ghz_consensus else None
            ),
            "updated_at": self._updated_at,
        }

    # ------------------------------------------------------------------
    # Private factor computations
    # ------------------------------------------------------------------

    def _qaoa_separation(self, a: str, b: str) -> float:
        """
        Frequency separation factor: 1.0 when devices are on well-separated
        channels (≥ 20 MHz apart), 0.0 when on the same frequency.
        """
        fa = self._frequency.get(a)
        fb = self._frequency.get(b)
        if fa is None or fb is None:
            return 0.5  # neutral when unknown
        sep_mhz = abs(fa - fb) / 1e6
        # Logistic mapping: full score at 20 MHz, zero at 0 MHz
        return min(1.0, sep_mhz / 20.0)

    def _qft_coherence(self, a: str, b: str) -> float:
        """
        Spectral coherence: low interference energy on both nodes → high score.
        """
        ea = self._spectral_energy.get(a, 0.0)
        eb = self._spectral_energy.get(b, 0.0)
        combined = (ea + eb) / 2.0
        # Energy is a raw magnitude; normalise against a practical max
        max_energy = 100.0
        return max(0.0, 1.0 - combined / max_energy)

    def _ghz_score(self, a: str, b: str) -> float:
        """
        GHZ consensus score: 1.0 if both nodes are on the consensus frequency,
        0.5 if only one is, 0.0 if neither.
        """
        if self._ghz_consensus is None:
            return 0.5
        fa = self._frequency.get(a)
        fb = self._frequency.get(b)
        tol_hz = 1e6  # 1 MHz tolerance
        on_a = fa is not None and abs(fa - self._ghz_consensus) <= tol_hz
        on_b = fb is not None and abs(fb - self._ghz_consensus) <= tol_hz
        if on_a and on_b:
            return 1.0
        if on_a or on_b:
            return 0.5
        return 0.0

    def _qkd_score(self, a: str, b: str) -> float:
        """QKD trust score for the pair (a, b)."""
        return self._qkd_trust.get(a, {}).get(b, 0.5)  # 0.5 = unknown trust

    def _touch(self) -> None:
        self._updated_at = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Fusion Engine
# ---------------------------------------------------------------------------

class FusionEngine:
    """
    Collects result snapshots from every agent type and synthesises them into
    a unified *fleet intelligence report*.
    """

    def __init__(self) -> None:
        self._snapshots: Dict[str, Any] = {}    # agent_type → latest result
        self._history: List[Dict[str, Any]] = []
        self._max_history = 100

    def ingest(self, agent_type: str, task: str, result: Any) -> None:
        """Record the latest result from a given agent."""
        entry = {
            "agent_type": agent_type,
            "task": task,
            "result": result,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        self._snapshots[agent_type] = entry
        self._history.append(entry)
        if len(self._history) > self._max_history:
            self._history.pop(0)

    def latest(self, agent_type: str) -> Optional[Dict[str, Any]]:
        return self._snapshots.get(agent_type)

    def synthesise(self) -> Dict[str, Any]:
        """
        Merge all latest agent snapshots into a single intelligence report.

        Priority rules (highest wins):
        - quantum_agent QAOA/GHZ → topology guidance
        - ai_agent recommendations → action directives
        - frequency_agent scan    → band snapshot
        - modulation_agent        → scheme snapshot
        - comms_agent telemetry   → link quality
        - firmware_agent          → build inventory
        """
        report: Dict[str, Any] = {
            "sources": list(self._snapshots.keys()),
            "synthesised_at": datetime.now(timezone.utc).isoformat(),
        }

        q = self._snapshots.get("quantum_agent", {}).get("result", {})
        ai = self._snapshots.get("ai_agent", {}).get("result", {})
        freq = self._snapshots.get("frequency_agent", {}).get("result", {})
        mod = self._snapshots.get("modulation_agent", {}).get("result", {})
        comms = self._snapshots.get("comms_agent", {}).get("result", {})
        fw = self._snapshots.get("firmware_agent", {}).get("result", {})

        # Dominant frequency — prefer GHZ consensus, then QAOA, then freq scan
        report["recommended_frequency_hz"] = (
            q.get("consensus_frequency_hz")
            or q.get("optimal_frequency_hz")
            or freq.get("locked_frequency_hz")
        )

        # Recommended modulation — from AI if present, else from modulation agent
        report["recommended_modulation"] = (
            ai.get("recommended_modulation")
            or mod.get("scheme")
        )

        # AI directives (list of recommendation strings)
        report["ai_directives"] = ai.get("recommendations", [])

        # Comms link quality
        report["link_quality_rssi"] = comms.get("wifi_rssi")

        # Latest firmware build_id
        report["latest_build_id"] = fw.get("build_id")

        # Quantum entropy (from QRNG if available)
        report["quantum_entropy_bpb"] = q.get("entropy_bits_per_byte")

        return report


# ---------------------------------------------------------------------------
# SuperNAi
# ---------------------------------------------------------------------------

class SuperNAi:
    """
    Quantum Topology Mesh Super Network AI.

    SuperNAi is the meta-intelligence coordinator for the entire fleet.
    It maintains a live quantum topology mesh, ingests results from every
    agent, fuses them into unified directives, and exposes a single
    decision interface for the orchestrator.

    Core operations
    ---------------
    fuse_agents(results)          — absorb a batch of agent results
    optimise_mesh()               — rebuild edge weights, return topology state
    fleet_intelligence_score()    — scalar [0,1] health/cooperation metric
    superNAi_insight(context)     — natural-language-style insight dict
    rebalance_topology()          — emit per-device recommended actions
    """

    VERSION = "1.0.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.mesh = QuantumTopologyMesh()
        self.fusion = FusionEngine()
        self._insight_cache: Optional[Dict[str, Any]] = None
        self._last_optimised: Optional[str] = None
        logger.info("SuperNAi v%s initialised", self.VERSION)

    # ------------------------------------------------------------------
    # Fleet topology registration
    # ------------------------------------------------------------------

    def register_device(self, device_id: str) -> None:
        """Add a device node to the quantum topology mesh."""
        self.mesh.add_node(device_id)

    def unregister_device(self, device_id: str) -> None:
        """Remove a device node from the mesh."""
        self.mesh.remove_node(device_id)

    # ------------------------------------------------------------------
    # Agent result ingestion
    # ------------------------------------------------------------------

    def fuse_agents(self, agent_results: List[Dict[str, Any]]) -> None:
        """
        Ingest a batch of agent task results.

        Each entry must have: ``agent_type``, ``task``, ``result``.
        SuperNAi extracts mesh-relevant fields (frequency, RSSI, QKD trust,
        GHZ consensus, QFT spectral energy) and feeds them into the topology.
        """
        for entry in agent_results:
            agent_type = entry.get("agent_type", "")
            task = entry.get("task", "")
            result = entry.get("result") or {}
            device_id = entry.get("device_id")

            self.fusion.ingest(agent_type, task, result)

            # Extract frequency
            if device_id:
                freq = (
                    result.get("optimal_frequency_hz")
                    or result.get("consensus_frequency_hz")
                    or result.get("locked_frequency_hz")
                    or result.get("frequency_hz")
                )
                if freq:
                    self.mesh.add_node(device_id)
                    self.mesh.update_frequency(device_id, float(freq))

                rssi = result.get("rssi") or result.get("wifi_rssi")
                if rssi is not None:
                    self.mesh.update_rssi(device_id, float(rssi))

            # Extract QFT spectral energy
            if task in ("qft_spectrum",) and device_id:
                mag = result.get("mean_magnitude")
                if mag is not None:
                    self.mesh.update_spectral_energy(device_id, float(mag))

            # Extract GHZ consensus
            if task in ("entangle_fleet",):
                consensus = result.get("consensus_frequency_hz")
                if consensus:
                    self.mesh.set_ghz_consensus(float(consensus))

            # Extract QKD trust — pair the device with every other mesh node
            if task in ("qkd_simulate",) and device_id:
                key_rate = result.get("key_rate_bps", 0)
                qber = result.get("qber", 1.0)
                # Trust = key-rate-normalised * (1 - qber)
                trust = min(1.0, key_rate / 1000.0) * max(0.0, 1.0 - qber)
                for other in list(self.mesh._edges.keys()):  # pylint: disable=protected-access
                    if other != device_id:
                        self.mesh.update_qkd_trust(device_id, other, trust)

        self._insight_cache = None  # invalidate cache

    # ------------------------------------------------------------------
    # Mesh optimisation
    # ------------------------------------------------------------------

    def optimise_mesh(self) -> Dict[str, Any]:
        """
        Trigger a full edge-weight recomputation and return the current
        topology snapshot.
        """
        self.mesh.recompute_edges()
        self._last_optimised = datetime.now(timezone.utc).isoformat()
        topology = self.mesh.to_dict()
        score = self.fleet_intelligence_score()
        logger.info(
            "SuperNAi mesh optimised: %d nodes, avg_weight=%.3f, score=%.3f",
            topology["node_count"], topology["average_weight"], score,
        )
        return {
            "topology": topology,
            "fleet_intelligence_score": round(score, 4),
            "score_label": self._score_label(score),
            "optimised_at": self._last_optimised,
        }

    # ------------------------------------------------------------------
    # Fleet intelligence score
    # ------------------------------------------------------------------

    def fleet_intelligence_score(self) -> float:
        """
        Scalar [0, 1] metric combining:
          - Average mesh edge weight          (40%)
          - Topology connectedness bonus      (20%)
          - Fusion data coverage              (20%)
          - QRNG entropy normalised           (20%)
        """
        avg_w = self.mesh.average_edge_weight()
        n = self.mesh.to_dict()["node_count"]
        partitions = self.mesh.partition_count()
        connectivity = 1.0 / partitions if partitions > 0 else 0.0
        coverage = len(self.fusion._snapshots) / max(6, 1)  # pylint: disable=protected-access
        coverage = min(1.0, coverage)

        q_snap = self.fusion.latest("quantum_agent")
        entropy_norm = 0.5  # neutral default
        if q_snap:
            entropy = q_snap.get("result", {}).get("entropy_bits_per_byte")
            if entropy is not None:
                entropy_norm = min(1.0, float(entropy) / 8.0)

        score = (
            0.40 * avg_w
            + 0.20 * connectivity
            + 0.20 * coverage
            + 0.20 * entropy_norm
        )
        return min(1.0, max(0.0, score))

    # ------------------------------------------------------------------
    # Insight generation
    # ------------------------------------------------------------------

    def superNAi_insight(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a unified fleet intelligence insight report.

        Combines quantum topology analysis with fused agent data to produce:
        - A fleet intelligence score
        - Topology health summary
        - Weakest / strongest links
        - Cross-agent directives
        - Per-device action recommendations
        """
        if self._insight_cache and not context:
            return self._insight_cache

        score = self.fleet_intelligence_score()
        topology = self.mesh.to_dict()
        fusion_report = self.fusion.synthesise()
        rebalance = self.rebalance_topology()

        # Assemble alerts
        alerts: List[str] = []
        partitions = topology["partition_count"]
        if partitions > 1:
            alerts.append(
                f"TOPOLOGY PARTITION DETECTED: {partitions} isolated clusters — "
                "run GHZ entanglement to re-synchronise."
            )
        avg_w = topology["average_weight"]
        if avg_w < 0.3:
            alerts.append(
                "LOW MESH COHERENCE: average edge weight below 30% — "
                "consider QAOA frequency sweep and QKD key refresh."
            )
        weak = self.mesh.weakest_links(3)
        for a, b, w in weak:
            if w < 0.2:
                alerts.append(
                    f"WEAK LINK {a}↔{b} (weight={w:.2f}): "
                    "QKD trust or frequency separation critically low."
                )

        insight: Dict[str, Any] = {
            "version": self.VERSION,
            "fleet_intelligence_score": round(score, 4),
            "score_label": self._score_label(score),
            "topology_summary": {
                "node_count": topology["node_count"],
                "edge_count": topology["edge_count"],
                "average_edge_weight": topology["average_weight"],
                "partition_count": partitions,
                "strongest_links": [
                    {"pair": f"{a}↔{b}", "weight": round(w, 4)}
                    for a, b, w in self.mesh.strongest_links(3)
                ],
                "weakest_links": [
                    {"pair": f"{a}↔{b}", "weight": round(w, 4)}
                    for a, b, w in self.mesh.weakest_links(3)
                ],
                "node_centrality": topology["centrality"],
                "ghz_consensus_mhz": topology["ghz_consensus_mhz"],
            },
            "fusion_report": fusion_report,
            "device_actions": rebalance,
            "alerts": alerts,
            "context": context or {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        self._insight_cache = insight
        return insight

    # ------------------------------------------------------------------
    # Topology rebalancing
    # ------------------------------------------------------------------

    def rebalance_topology(self) -> List[Dict[str, Any]]:
        """
        Emit per-device action recommendations based on mesh state.

        Devices with low centrality → recommend frequency re-tune (QAOA).
        Devices with low QKD trust  → recommend QKD key refresh.
        Devices on wrong consensus  → recommend GHZ re-entanglement.
        """
        actions: List[Dict[str, Any]] = []
        centrality = self.mesh.node_centrality()
        consensus = self.mesh._ghz_consensus  # pylint: disable=protected-access
        frequencies = self.mesh._frequency    # pylint: disable=protected-access
        qkd_trust = self.mesh._qkd_trust      # pylint: disable=protected-access

        for device_id, c in centrality.items():
            device_actions: List[str] = []

            if c < 0.4:
                device_actions.append("qaoa_optimise: low mesh centrality, re-tune frequency")

            freq = frequencies.get(device_id)
            if consensus and freq and abs(freq - consensus) > 1e6:
                device_actions.append(
                    f"entangle_fleet: off-consensus by "
                    f"{abs(freq - consensus) / 1e6:.1f} MHz"
                )

            peers = qkd_trust.get(device_id, {})
            low_trust_peers = [p for p, t in peers.items() if t < 0.4]
            if low_trust_peers:
                device_actions.append(
                    f"qkd_simulate: low trust with {', '.join(low_trust_peers)}"
                )

            if device_actions:
                actions.append({
                    "device_id": device_id,
                    "centrality": round(c, 4),
                    "recommended_actions": device_actions,
                })

        return actions

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_label(score: float) -> str:
        if score >= _SCORE_OPTIMAL:
            return "optimal"
        if score >= _SCORE_DEGRADED:
            return "degraded"
        return "critical"

    def get_status(self) -> Dict[str, Any]:
        """Return a compact status snapshot."""
        score = self.fleet_intelligence_score()
        topo = self.mesh.to_dict()
        return {
            "version": self.VERSION,
            "fleet_intelligence_score": round(score, 4),
            "score_label": self._score_label(score),
            "node_count": topo["node_count"],
            "edge_count": topo["edge_count"],
            "average_edge_weight": topo["average_weight"],
            "partition_count": topo["partition_count"],
            "fusion_sources": list(self.fusion._snapshots.keys()),  # pylint: disable=protected-access
            "last_optimised": self._last_optimised,
        }
