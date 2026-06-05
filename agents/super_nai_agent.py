"""
SuperNAiAgent — orchestrator agent wrapping SuperNAi.

Exposes all SuperNAi capabilities as dispatchable tasks so the orchestrator
can route them through the standard task-dispatch mechanism and they appear
alongside the other agents in the REST API.

Tasks
-----
insight             – Generate a full fleet intelligence insight report
optimise_mesh       – Rebuild quantum topology edge weights and return snapshot
fleet_score         – Return the scalar fleet intelligence score
fuse                – Absorb a list of agent results into the mesh
rebalance           – Emit per-device topology rebalancing recommendations
register_device     – Add a device node to the quantum topology mesh
unregister_device   – Remove a device node from the mesh
mesh_status         – Return compact mesh status
"""

import logging
from typing import Any, Dict, List, Optional

from orchestrator.agent import AgentBase
from orchestrator.device import ESP32Device
from ai.super_nai import SuperNAi

logger = logging.getLogger(__name__)


class SuperNAiAgent(AgentBase):
    """
    Quantum Topology Mesh Super Network AI — orchestrator agent.

    Wraps ``SuperNAi`` as a first-class agent so the orchestrator treats it
    identically to every other agent (registration, dispatch, health metrics).

    On each task execution SuperNAiAgent also auto-fuses the result with the
    device's latest telemetry, keeping the topology mesh continuously updated.
    """

    TASKS = {
        "insight",
        "optimise_mesh",
        "fleet_score",
        "fuse",
        "rebalance",
        "register_device",
        "unregister_device",
        "mesh_status",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__("super_nai_agent", config)
        self.super_nai = SuperNAi(config)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _on_start(self) -> None:
        """Seed the mesh with any devices already registered on the orchestrator."""
        if self.orchestrator:
            for device in self.orchestrator.list_devices():
                self.super_nai.register_device(device.device_id)
            logger.info(
                "SuperNAiAgent seeded mesh with %d existing devices",
                len(self.orchestrator.list_devices()),
            )

    # ------------------------------------------------------------------
    # AgentBase interface
    # ------------------------------------------------------------------

    async def _execute(
        self,
        task: str,
        params: Dict[str, Any],
        device: Optional[ESP32Device],
    ) -> Any:
        # Auto-register the target device in the mesh
        if device:
            self.super_nai.register_device(device.device_id)
            # Auto-fuse any telemetry available on the device object
            self._auto_fuse_device(device)

        if task == "insight":
            return self.super_nai.superNAi_insight(params.get("context"))
        if task == "optimise_mesh":
            return self.super_nai.optimise_mesh()
        if task == "fleet_score":
            score = self.super_nai.fleet_intelligence_score()
            return {
                "fleet_intelligence_score": round(score, 4),
                "score_label": self.super_nai._score_label(score),  # pylint: disable=protected-access
            }
        if task == "fuse":
            results: List[Dict[str, Any]] = params.get("results", [])
            self.super_nai.fuse_agents(results)
            return {"fused": len(results), "ok": True}
        if task == "rebalance":
            return {"actions": self.super_nai.rebalance_topology()}
        if task == "register_device":
            device_id = params.get("device_id", device.device_id if device else None)
            if not device_id:
                return {"ok": False, "reason": "device_id required"}
            self.super_nai.register_device(device_id)
            return {"ok": True, "device_id": device_id}
        if task == "unregister_device":
            device_id = params.get("device_id", device.device_id if device else None)
            if not device_id:
                return {"ok": False, "reason": "device_id required"}
            self.super_nai.unregister_device(device_id)
            return {"ok": True, "device_id": device_id}
        if task == "mesh_status":
            return self.super_nai.get_status()
        raise ValueError(f"Unknown SuperNAiAgent task: {task}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _auto_fuse_device(self, device: ESP32Device) -> None:
        """Push available telemetry from a device object into the mesh."""
        telemetry = device.telemetry if hasattr(device, "telemetry") else {}
        results: List[Dict[str, Any]] = []

        freq = getattr(device, "frequency_hz", None) or telemetry.get("frequency_hz")
        rssi = telemetry.get("wifi_rssi") or telemetry.get("rssi")

        if freq is not None:
            results.append({
                "agent_type": "frequency_agent",
                "task": "get_frequency",
                "device_id": device.device_id,
                "result": {"frequency_hz": freq},
            })
        if rssi is not None:
            results.append({
                "agent_type": "comms_agent",
                "task": "diagnostics",
                "device_id": device.device_id,
                "result": {"wifi_rssi": rssi},
            })

        if results:
            self.super_nai.fuse_agents(results)
