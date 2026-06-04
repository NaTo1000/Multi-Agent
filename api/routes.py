"""
REST API routes.

Provides endpoints for:
- Orchestrator status
- Device CRUD
- Agent management
- Task dispatch
- Firmware builds
- AI recommendations
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def build_router():
    try:
        from fastapi import APIRouter, HTTPException, Request
        from pydantic import BaseModel
    except ImportError:
        raise RuntimeError("fastapi and pydantic are required")

    router = APIRouter()

    # ------------------------------------------------------------------
    # Pydantic models
    # ------------------------------------------------------------------

    class DeviceCreate(BaseModel):
        device_id: str
        name: str
        ip_address: Optional[str] = None
        mac_address: Optional[str] = None
        capabilities: Optional[List[str]] = None

    class TaskRequest(BaseModel):
        agent_id: str
        task: str
        params: Optional[Dict[str, Any]] = None
        device_id: Optional[str] = None

    class BroadcastRequest(BaseModel):
        agent_type: str
        task: str
        params: Optional[Dict[str, Any]] = None

    class FirmwareBuildRequest(BaseModel):
        template: str = "base"
        features: List[str] = ["wifi"]
        version: Optional[str] = None
        extra: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------

    @router.get("/status", tags=["System"])
    async def get_status(request: Request):
        return request.app.state.orchestrator.get_status()

    # ------------------------------------------------------------------
    # Devices
    # ------------------------------------------------------------------

    @router.get("/devices", tags=["Devices"])
    async def list_devices(request: Request):
        return [d.to_dict() for d in request.app.state.orchestrator.list_devices()]

    @router.get("/devices/{device_id}", tags=["Devices"])
    async def get_device(device_id: str, request: Request):
        device = request.app.state.orchestrator.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        return device.to_dict()

    @router.post("/devices", tags=["Devices"])
    async def register_device(body: DeviceCreate, request: Request):
        from orchestrator.device import ESP32Device, DeviceCapability
        caps = []
        for c in (body.capabilities or []):
            try:
                caps.append(DeviceCapability(c))
            except ValueError:
                pass
        device = ESP32Device(
            device_id=body.device_id,
            name=body.name,
            ip_address=body.ip_address,
            mac_address=body.mac_address,
            capabilities=caps or None,
        )
        device_id = request.app.state.orchestrator.register_device(device)
        return {"device_id": device_id}

    @router.delete("/devices/{device_id}", tags=["Devices"])
    async def unregister_device(device_id: str, request: Request):
        ok = request.app.state.orchestrator.unregister_device(device_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Device not found")
        return {"ok": True}

    @router.post("/devices/{device_id}/ping", tags=["Devices"])
    async def ping_device(device_id: str, request: Request):
        device = request.app.state.orchestrator.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        online = await device.ping()
        return {"device_id": device_id, "online": online}

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    @router.get("/agents", tags=["Agents"])
    async def list_agents(request: Request):
        return [a.get_metrics() for a in request.app.state.orchestrator.list_agents()]

    @router.get("/agents/{agent_id}", tags=["Agents"])
    async def get_agent(agent_id: str, request: Request):
        agent = request.app.state.orchestrator.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent.get_metrics()

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    @router.post("/tasks", tags=["Tasks"])
    async def dispatch_task(body: TaskRequest, request: Request):
        try:
            task_id = await request.app.state.orchestrator.dispatch_task(
                body.agent_id, body.task, body.params, body.device_id
            )
            return {"task_id": task_id}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post("/tasks/broadcast", tags=["Tasks"])
    async def broadcast_task(body: BroadcastRequest, request: Request):
        task_ids = await request.app.state.orchestrator.broadcast_task(
            body.agent_type, body.task, body.params
        )
        return {"task_ids": task_ids}

    @router.get("/tasks/{task_id}", tags=["Tasks"])
    async def get_task_result(task_id: str, request: Request):
        result = request.app.state.orchestrator.get_task_result(task_id)
        if not result:
            raise HTTPException(status_code=404, detail="Task not found")
        return result

    # ------------------------------------------------------------------
    # Firmware
    # ------------------------------------------------------------------

    @router.post("/firmware/build", tags=["Firmware"])
    async def build_firmware(body: FirmwareBuildRequest, request: Request):
        fw_agents = request.app.state.orchestrator.get_agents_by_type("firmware_agent")
        if not fw_agents:
            raise HTTPException(status_code=503, detail="No firmware agent registered")
        task_id = await request.app.state.orchestrator.dispatch_task(
            fw_agents[0].agent_id,
            "build",
            {
                "template": body.template,
                "features": body.features,
                "version": body.version,
                "extra": body.extra or {},
            },
        )
        result = request.app.state.orchestrator.get_task_result(task_id)
        return result

    @router.post("/firmware/flash/{device_id}", tags=["Firmware"])
    async def flash_firmware(device_id: str, body: Dict[str, Any], request: Request):
        fw_agents = request.app.state.orchestrator.get_agents_by_type("firmware_agent")
        if not fw_agents:
            raise HTTPException(status_code=503, detail="No firmware agent registered")
        task_id = await request.app.state.orchestrator.dispatch_task(
            fw_agents[0].agent_id, "flash", body, device_id
        )
        result = request.app.state.orchestrator.get_task_result(task_id)
        return result

    # ------------------------------------------------------------------
    # AI
    # ------------------------------------------------------------------

    @router.post("/ai/optimise/{device_id}", tags=["AI"])
    async def ai_optimise(device_id: str, request: Request):
        ai_agents = request.app.state.orchestrator.get_agents_by_type("ai_agent")
        if not ai_agents:
            raise HTTPException(status_code=503, detail="No AI agent registered")
        task_id = await request.app.state.orchestrator.dispatch_task(
            ai_agents[0].agent_id, "auto_optimise", {}, device_id
        )
        return request.app.state.orchestrator.get_task_result(task_id)

    @router.post("/ai/research", tags=["AI"])
    async def ai_research(body: Dict[str, Any], request: Request):
        ai_agents = request.app.state.orchestrator.get_agents_by_type("ai_agent")
        if not ai_agents:
            raise HTTPException(status_code=503, detail="No AI agent registered")
        task_id = await request.app.state.orchestrator.dispatch_task(
            ai_agents[0].agent_id, "research", body
        )
        return request.app.state.orchestrator.get_task_result(task_id)

    # ------------------------------------------------------------------
    # Quantum  (V2.1)
    # ------------------------------------------------------------------

    class QuantumTaskRequest(BaseModel):
        task: str
        params: Optional[Dict[str, Any]] = None
        device_id: Optional[str] = None

    @router.post("/quantum/task", tags=["Quantum"])
    async def quantum_task(body: QuantumTaskRequest, request: Request):
        """Dispatch any task to the QuantumAgent."""
        q_agents = request.app.state.orchestrator.get_agents_by_type("quantum_agent")
        if not q_agents:
            raise HTTPException(status_code=503, detail="No quantum agent registered")
        try:
            task_id = await request.app.state.orchestrator.dispatch_task(
                q_agents[0].agent_id, body.task, body.params or {}, body.device_id
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return request.app.state.orchestrator.get_task_result(task_id)

    @router.post("/quantum/qaoa/{device_id}", tags=["Quantum"])
    async def quantum_qaoa_optimise(device_id: str, body: Dict[str, Any], request: Request):
        """Run QAOA frequency optimisation on a specific device."""
        q_agents = request.app.state.orchestrator.get_agents_by_type("quantum_agent")
        if not q_agents:
            raise HTTPException(status_code=503, detail="No quantum agent registered")
        task_id = await request.app.state.orchestrator.dispatch_task(
            q_agents[0].agent_id, "qaoa_optimise", body, device_id
        )
        return request.app.state.orchestrator.get_task_result(task_id)

    @router.post("/quantum/qkd/{device_id}", tags=["Quantum"])
    async def quantum_qkd(device_id: str, body: Dict[str, Any], request: Request):
        """Run BB84 QKD key exchange with a device."""
        q_agents = request.app.state.orchestrator.get_agents_by_type("quantum_agent")
        if not q_agents:
            raise HTTPException(status_code=503, detail="No quantum agent registered")
        task_id = await request.app.state.orchestrator.dispatch_task(
            q_agents[0].agent_id, "qkd_simulate", body, device_id
        )
        return request.app.state.orchestrator.get_task_result(task_id)

    @router.post("/quantum/grover", tags=["Quantum"])
    async def quantum_grover_search(body: Dict[str, Any], request: Request):
        """Run Grover-inspired channel search over a candidate set."""
        q_agents = request.app.state.orchestrator.get_agents_by_type("quantum_agent")
        if not q_agents:
            raise HTTPException(status_code=503, detail="No quantum agent registered")
        task_id = await request.app.state.orchestrator.dispatch_task(
            q_agents[0].agent_id, "grover_search", body
        )
        return request.app.state.orchestrator.get_task_result(task_id)

    @router.post("/quantum/qft", tags=["Quantum"])
    async def quantum_qft_spectrum(body: Dict[str, Any], request: Request):
        """Perform QFT-based interference spectrum analysis."""
        q_agents = request.app.state.orchestrator.get_agents_by_type("quantum_agent")
        if not q_agents:
            raise HTTPException(status_code=503, detail="No quantum agent registered")
        task_id = await request.app.state.orchestrator.dispatch_task(
            q_agents[0].agent_id, "qft_spectrum", body
        )
        return request.app.state.orchestrator.get_task_result(task_id)

    @router.post("/quantum/qrng", tags=["Quantum"])
    async def quantum_qrng(body: Dict[str, Any], request: Request):
        """Generate quantum-random bytes."""
        q_agents = request.app.state.orchestrator.get_agents_by_type("quantum_agent")
        if not q_agents:
            raise HTTPException(status_code=503, detail="No quantum agent registered")
        task_id = await request.app.state.orchestrator.dispatch_task(
            q_agents[0].agent_id, "qrng", body
        )
        return request.app.state.orchestrator.get_task_result(task_id)

    @router.post("/quantum/entangle", tags=["Quantum"])
    async def quantum_entangle_fleet(body: Dict[str, Any], request: Request):
        """Synchronise the entire fleet via GHZ quantum-entanglement-inspired consensus."""
        q_agents = request.app.state.orchestrator.get_agents_by_type("quantum_agent")
        if not q_agents:
            raise HTTPException(status_code=503, detail="No quantum agent registered")
        task_id = await request.app.state.orchestrator.dispatch_task(
            q_agents[0].agent_id, "entangle_fleet", body
        )
        return request.app.state.orchestrator.get_task_result(task_id)

    # ------------------------------------------------------------------
    # SuperNAi — Quantum Topology Mesh Super Network AI
    # ------------------------------------------------------------------

    def _get_super_nai_agent(request: Request):
        agents = request.app.state.orchestrator.get_agents_by_type("super_nai_agent")
        if not agents:
            raise HTTPException(status_code=503, detail="No SuperNAi agent registered")
        return agents[0]

    @router.get("/supernai/status", tags=["SuperNAi"])
    async def supernai_status(request: Request):
        """Return the current quantum topology mesh status and fleet intelligence score."""
        agent = _get_super_nai_agent(request)
        task_id = await request.app.state.orchestrator.dispatch_task(
            agent.agent_id, "mesh_status", {}
        )
        return request.app.state.orchestrator.get_task_result(task_id)

    @router.get("/supernai/insight", tags=["SuperNAi"])
    async def supernai_insight(request: Request):
        """Generate a full fleet intelligence insight report from the quantum topology mesh."""
        agent = _get_super_nai_agent(request)
        task_id = await request.app.state.orchestrator.dispatch_task(
            agent.agent_id, "insight", {}
        )
        return request.app.state.orchestrator.get_task_result(task_id)

    @router.post("/supernai/insight", tags=["SuperNAi"])
    async def supernai_insight_with_context(body: Dict[str, Any], request: Request):
        """Generate a fleet intelligence insight report enriched with caller-supplied context."""
        agent = _get_super_nai_agent(request)
        task_id = await request.app.state.orchestrator.dispatch_task(
            agent.agent_id, "insight", {"context": body}
        )
        return request.app.state.orchestrator.get_task_result(task_id)

    @router.post("/supernai/optimise", tags=["SuperNAi"])
    async def supernai_optimise_mesh(request: Request):
        """Trigger a full quantum topology mesh edge-weight recomputation."""
        agent = _get_super_nai_agent(request)
        task_id = await request.app.state.orchestrator.dispatch_task(
            agent.agent_id, "optimise_mesh", {}
        )
        return request.app.state.orchestrator.get_task_result(task_id)

    @router.get("/supernai/score", tags=["SuperNAi"])
    async def supernai_fleet_score(request: Request):
        """Return the scalar fleet intelligence score [0, 1]."""
        agent = _get_super_nai_agent(request)
        task_id = await request.app.state.orchestrator.dispatch_task(
            agent.agent_id, "fleet_score", {}
        )
        return request.app.state.orchestrator.get_task_result(task_id)

    @router.post("/supernai/fuse", tags=["SuperNAi"])
    async def supernai_fuse(body: Dict[str, Any], request: Request):
        """Inject agent result snapshots into the quantum topology mesh."""
        agent = _get_super_nai_agent(request)
        results = body.get("results", [])
        task_id = await request.app.state.orchestrator.dispatch_task(
            agent.agent_id, "fuse", {"results": results}
        )
        return request.app.state.orchestrator.get_task_result(task_id)

    @router.post("/supernai/rebalance", tags=["SuperNAi"])
    async def supernai_rebalance(request: Request):
        """Emit per-device topology rebalancing recommendations."""
        agent = _get_super_nai_agent(request)
        task_id = await request.app.state.orchestrator.dispatch_task(
            agent.agent_id, "rebalance", {}
        )
        return request.app.state.orchestrator.get_task_result(task_id)

    return router
