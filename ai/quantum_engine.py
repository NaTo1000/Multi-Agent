"""
Quantum Engine — quantum-enhanced AI automation layer.

Extends the classical AutomationEngine with quantum-algorithm-driven
policies for interference mitigation, frequency optimisation, and
fleet-wide key distribution.
"""

import asyncio
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class QuantumPolicy:
    """A quantum-enhanced automation policy."""

    def __init__(
        self,
        name: str,
        quantum_task: str,
        params: Optional[Dict[str, Any]] = None,
        interval_sec: int = 60,
        enabled: bool = True,
    ):
        self.name = name
        self.quantum_task = quantum_task
        self.params = params or {}
        self.interval_sec = interval_sec
        self.enabled = enabled
        self.last_run: Optional[str] = None
        self.run_count: int = 0


class QuantumEngine:
    """
    Quantum-enhanced automation engine.

    Augments the classical AutomationEngine with QAOA, Grover, and QFT
    policies dispatched to the QuantumAgent on a configurable schedule.

    Architecture
    ------------
    ClassicalAutomationEngine (reactive, statistical)
           +
    QuantumEngine (proactive, combinatorial, cryptographic)
           =
    Supercharged V2.1 dual-mode automation stack
    """

    DEFAULT_QUANTUM_POLICIES: List[QuantumPolicy] = [
        QuantumPolicy(
            "qaoa_frequency_sweep",
            "qaoa_optimise",
            params={"layers": 4},
            interval_sec=90,
        ),
        QuantumPolicy(
            "grover_channel_search",
            "grover_search",
            interval_sec=45,
        ),
        QuantumPolicy(
            "qft_interference_scan",
            "qft_spectrum",
            interval_sec=30,
        ),
        QuantumPolicy(
            "fleet_entanglement_sync",
            "entangle_fleet",
            params={"layers": 4},
            interval_sec=180,
        ),
        QuantumPolicy(
            "qkd_key_refresh",
            "qkd_simulate",
            params={"n_qubits": 512},
            interval_sec=600,
        ),
    ]

    def __init__(self, orchestrator: Any, config: Optional[Dict[str, Any]] = None):
        self.orchestrator = orchestrator
        self.config = config or {}
        self._policies: List[QuantumPolicy] = list(self.DEFAULT_QUANTUM_POLICIES)
        self._running = False

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def add_policy(self, policy: QuantumPolicy) -> None:
        self._policies.append(policy)

    def remove_policy(self, name: str) -> bool:
        before = len(self._policies)
        self._policies = [p for p in self._policies if p.name != name]
        return len(self._policies) < before

    def enable_policy(self, name: str, enabled: bool = True) -> None:
        for p in self._policies:
            if p.name == name:
                p.enabled = enabled
                return

    def list_policies(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": p.name,
                "quantum_task": p.quantum_task,
                "interval_sec": p.interval_sec,
                "enabled": p.enabled,
                "last_run": p.last_run,
                "run_count": p.run_count,
            }
            for p in self._policies
        ]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        asyncio.ensure_future(self._quantum_loop())
        logger.info("QuantumEngine started with %d quantum policies", len(self._policies))

    async def stop(self) -> None:
        self._running = False
        logger.info("QuantumEngine stopped")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def _quantum_loop(self) -> None:
        """Background loop that fires quantum policies on schedule."""
        timers: Dict[str, float] = {}
        start = asyncio.get_event_loop().time()

        while self._running:
            now = asyncio.get_event_loop().time()
            for policy in self._policies:
                if not policy.enabled:
                    continue
                last = timers.get(policy.name, start - policy.interval_sec)
                if now - last >= policy.interval_sec:
                    timers[policy.name] = now
                    asyncio.ensure_future(self._run_quantum_policy(policy))
            await asyncio.sleep(1)

    async def _run_quantum_policy(self, policy: QuantumPolicy) -> None:
        """Dispatch a quantum policy task to the QuantumAgent."""
        q_agents = self.orchestrator.get_agents_by_type("quantum_agent")
        if not q_agents:
            return
        try:
            task_id = await self.orchestrator.dispatch_task(
                q_agents[0].agent_id,
                policy.quantum_task,
                policy.params,
            )
            policy.last_run = datetime.now(timezone.utc).isoformat()
            policy.run_count += 1
            logger.debug("Quantum policy '%s' fired → task %s", policy.name, task_id)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Quantum policy '%s' failed: %s", policy.name, exc)
