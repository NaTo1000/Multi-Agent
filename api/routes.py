"""
REST API routes.

Provides endpoints for:
- Orchestrator status
- Device CRUD
- Agent management
- Task dispatch with priority
- Firmware builds
- AI recommendations
- Automation policy management
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def build_router():
    try:
        from fastapi import APIRouter, HTTPException, Request
        from pydantic import BaseModel, Field
    except ImportError:
        raise RuntimeError("fastapi and pydantic are required")

    router = APIRouter()

    # ------------------------------------------------------------------
    # Pydantic request/response models
    # ------------------------------------------------------------------

    class DeviceCreate(BaseModel):
        device_id: str = Field(..., min_length=1, max_length=128, description="Unique device identifier")
        name: str = Field(..., min_length=1, max_length=256, description="Human-readable device name")
        ip_address: Optional[str] = Field(None, description="IPv4 address of the device")
        mac_address: Optional[str] = Field(None, description="MAC address of the device")
        capabilities: Optional[List[str]] = Field(None, description="List of device capabilities (wifi, ble, gps, lora)")

    class TaskRequest(BaseModel):
        agent_id: str = Field(..., description="Target agent ID")
        task: str = Field(..., description="Task name to execute")
        params: Optional[Dict[str, Any]] = Field(None, description="Task parameters")
        device_id: Optional[str] = Field(None, description="Target device ID (optional)")
        priority: int = Field(5, ge=1, le=10, description="Priority (1=highest, 10=lowest)")

    class BroadcastRequest(BaseModel):
        agent_type: str = Field(..., description="Agent type to broadcast to")
        task: str = Field(..., description="Task name to execute")
        params: Optional[Dict[str, Any]] = Field(None, description="Task parameters")

    class FirmwareBuildRequest(BaseModel):
        template: str = Field("base", description="Template name")
        features: List[str] = Field(default=["wifi"], description="Feature flags to enable")
        version: Optional[str] = Field(None, description="Semantic version string")
        extra: Optional[Dict[str, Any]] = Field(None, description="Extra #define key-value pairs")

    class AutomationPolicyCreate(BaseModel):
        name: str = Field(..., min_length=1, max_length=128)
        agent_type: str
        task: str
        params: Optional[Dict[str, Any]] = None
        interval_sec: float = Field(60.0, gt=0)
        enabled: bool = True

    class AIResearchRequest(BaseModel):
        query: str = Field(..., min_length=1, max_length=2000, description="Research query")
        context: Optional[Dict[str, Any]] = Field(None, description="Additional context")

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

    @router.post("/devices", tags=["Devices"], status_code=201)
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
    # Tasks (with priority support)
    # ------------------------------------------------------------------

    @router.post("/tasks", tags=["Tasks"])
    async def dispatch_task(body: TaskRequest, request: Request):
        try:
            task_id = await request.app.state.orchestrator.dispatch_task(
                body.agent_id, body.task, body.params, body.device_id,
                priority=body.priority,
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
    async def ai_research(body: AIResearchRequest, request: Request):
        ai_agents = request.app.state.orchestrator.get_agents_by_type("ai_agent")
        if not ai_agents:
            raise HTTPException(status_code=503, detail="No AI agent registered")
        task_id = await request.app.state.orchestrator.dispatch_task(
            ai_agents[0].agent_id, "research",
            {"query": body.query, "context": body.context or {}},
        )
        return request.app.state.orchestrator.get_task_result(task_id)

    # ------------------------------------------------------------------
    # Automation
    # ------------------------------------------------------------------

    @router.get("/automation/policies", tags=["Automation"])
    async def list_policies(request: Request):
        orch = request.app.state.orchestrator
        if not hasattr(orch, "automation_engine") or not orch.automation_engine:
            return {"policies": []}
        return {"policies": orch.automation_engine.list_policies()}

    @router.post("/automation/policies", tags=["Automation"], status_code=201)
    async def add_policy(body: AutomationPolicyCreate, request: Request):
        orch = request.app.state.orchestrator
        if not hasattr(orch, "automation_engine") or not orch.automation_engine:
            raise HTTPException(status_code=503, detail="Automation engine not configured")
        from ai.automation import AutomationPolicy
        policy = AutomationPolicy(
            name=body.name,
            agent_type=body.agent_type,
            task=body.task,
            params=body.params or {},
            interval_sec=body.interval_sec,
            enabled=body.enabled,
        )
        orch.automation_engine.add_policy(policy)
        return {"name": policy.name, "added": True}

    @router.delete("/automation/policies/{policy_name}", tags=["Automation"])
    async def remove_policy(policy_name: str, request: Request):
        orch = request.app.state.orchestrator
        if not hasattr(orch, "automation_engine") or not orch.automation_engine:
            raise HTTPException(status_code=503, detail="Automation engine not configured")
        ok = orch.automation_engine.remove_policy(policy_name)
        if not ok:
            raise HTTPException(status_code=404, detail="Policy not found")
        return {"ok": True}

    return router
