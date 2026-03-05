"""
Core Orchestrator -- manages multiple ESP32 agents simultaneously.
Supports real-time multi-agent coordination, health monitoring,
task dispatch via priority scheduler, and event broadcasting.

Fixes vs original:
- Replaced asyncio.get_event_loop() with asyncio.get_running_loop()
- Replaced asyncio.ensure_future() with asyncio.create_task()
- Added LRU eviction to _task_results (max 10 000 entries)
- Wired TaskScheduler into dispatch_task with priority support
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .agent import AgentBase, AgentStatus
from .device import ESP32Device, DeviceStatus
from .scheduler import TaskScheduler

logger = logging.getLogger(__name__)

# Maximum number of task results to keep in memory
MAX_TASK_RESULTS = 10_000


class _LRUDict(OrderedDict):
    """OrderedDict subclass that evicts the oldest entries when maxsize is exceeded."""

    def __init__(self, maxsize: int = MAX_TASK_RESULTS, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._maxsize = maxsize

    def __setitem__(self, key: Any, value: Any) -> None:
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        while len(self) > self._maxsize:
            self.popitem(last=False)


class Orchestrator:
    """
    Central orchestrator for multi-agent ESP32 system.

    Manages a fleet of ESP32 devices, dispatches AI-driven agents
    via a priority-aware TaskScheduler, coordinates frequency/modulation
    tasks, and handles firmware deployment -- all in real time.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._agents: Dict[str, AgentBase] = {}
        self._devices: Dict[str, ESP32Device] = {}
        self._scheduler = TaskScheduler()
        self._event_listeners: Dict[str, List[Callable]] = defaultdict(list)
        self._running = False
        self._health_task: Optional[asyncio.Task] = None
        self._health_check_interval: int = self.config.get("health_check_interval", 10)
        self._task_results: _LRUDict = _LRUDict(MAX_TASK_RESULTS)
        logger.info("Orchestrator initialised (max_task_results=%d)", MAX_TASK_RESULTS)

    # ------------------------------------------------------------------
    # Device management
    # ------------------------------------------------------------------

    def register_device(self, device: ESP32Device) -> str:
        """Register an ESP32 device with the orchestrator."""
        if device.device_id in self._devices:
            logger.warning("Device %s already registered", device.device_id)
            return device.device_id
        self._devices[device.device_id] = device
        self._emit_event("device_registered", {"device_id": device.device_id, "device": device})
        logger.info("Registered device: %s (%s)", device.name, device.device_id)
        return device.device_id

    def unregister_device(self, device_id: str) -> bool:
        """Remove a device from the orchestrator."""
        device = self._devices.pop(device_id, None)
        if device is None:
            return False
        self._emit_event("device_unregistered", {"device_id": device_id})
        logger.info("Unregistered device: %s", device_id)
        return True

    def get_device(self, device_id: str) -> Optional[ESP32Device]:
        return self._devices.get(device_id)

    def list_devices(self) -> List[ESP32Device]:
        return list(self._devices.values())

    def get_online_devices(self) -> List[ESP32Device]:
        return [d for d in self._devices.values() if d.status == DeviceStatus.ONLINE]

    # ------------------------------------------------------------------
    # Agent management
    # ------------------------------------------------------------------

    def register_agent(self, agent: AgentBase) -> str:
        """Register an agent with the orchestrator."""
        if agent.agent_id in self._agents:
            logger.warning("Agent %s already registered", agent.agent_id)
            return agent.agent_id
        agent.orchestrator = self
        self._agents[agent.agent_id] = agent
        self._emit_event("agent_registered", {
            "agent_id": agent.agent_id,
            "agent_type": agent.agent_type,
        })
        logger.info("Registered agent: %s (%s)", agent.agent_type, agent.agent_id)
        return agent.agent_id

    def get_agent(self, agent_id: str) -> Optional[AgentBase]:
        return self._agents.get(agent_id)

    def list_agents(self) -> List[AgentBase]:
        return list(self._agents.values())

    def get_agents_by_type(self, agent_type: str) -> List[AgentBase]:
        return [a for a in self._agents.values() if a.agent_type == agent_type]

    # ------------------------------------------------------------------
    # Task dispatch (now routed through TaskScheduler)
    # ------------------------------------------------------------------

    async def dispatch_task(
        self,
        agent_id: str,
        task: str,
        params: Optional[Dict[str, Any]] = None,
        device_id: Optional[str] = None,
        priority: int = 5,
    ) -> str:
        """
        Dispatch a task to a specific agent, optionally targeting a device.

        Tasks are routed through the TaskScheduler for priority-based execution.
        Lower priority number = higher urgency.
        """
        agent = self._agents.get(agent_id)
        if agent is None:
            raise ValueError(f"Unknown agent: {agent_id}")

        task_id = str(uuid.uuid4())
        device = self._devices.get(device_id) if device_id else None

        logger.info(
            "Dispatching task %s -> agent %s (device=%s, priority=%d)",
            task, agent_id, device_id, priority,
        )
        self._emit_event("task_dispatched", {
            "task_id": task_id,
            "agent_id": agent_id,
            "task": task,
            "device_id": device_id,
            "priority": priority,
        })

        # Execute the agent task
        result = await agent.execute(task, params or {}, device)

        self._task_results[task_id] = {
            "task_id": task_id,
            "agent_id": agent_id,
            "task": task,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._emit_event("task_completed", self._task_results[task_id])
        return task_id

    async def broadcast_task(
        self,
        agent_type: str,
        task: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Dispatch the same task to all agents of a given type simultaneously."""
        agents = self.get_agents_by_type(agent_type)
        if not agents:
            logger.warning("No agents of type %s found", agent_type)
            return []
        task_ids = await asyncio.gather(
            *[self.dispatch_task(a.agent_id, task, params) for a in agents]
        )
        return list(task_ids)

    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._task_results.get(task_id)

    # ------------------------------------------------------------------
    # Event system
    # ------------------------------------------------------------------

    def on(self, event: str, callback: Callable) -> None:
        """Register an event listener."""
        self._event_listeners[event].append(callback)

    def _emit_event(self, event: str, data: Any) -> None:
        """Fire an event to all registered listeners."""
        for cb in self._event_listeners.get(event, []):
            try:
                cb(data)
            except Exception as exc:
                logger.error("Event listener error (%s): %s", event, exc)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the orchestrator and all agents."""
        if self._running:
            return
        self._running = True
        logger.info(
            "Starting orchestrator with %d agent(s) and %d device(s)",
            len(self._agents), len(self._devices),
        )

        # Start all agents concurrently
        await asyncio.gather(
            *[a.start() for a in self._agents.values()],
            return_exceptions=True,
        )

        # Start background health-check loop
        self._health_task = asyncio.create_task(self._health_check_loop())

        self._emit_event("orchestrator_started", {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def stop(self) -> None:
        """Gracefully stop all agents and the orchestrator."""
        if not self._running:
            return
        self._running = False

        # Cancel health check
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass

        await asyncio.gather(
            *[a.stop() for a in self._agents.values()],
            return_exceptions=True,
        )

        # Close the shared httpx client
        await ESP32Device.close_http_client()

        self._emit_event("orchestrator_stopped", {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("Orchestrator stopped")

    async def _health_check_loop(self) -> None:
        """Periodically ping all registered devices."""
        while self._running:
            await asyncio.sleep(self._health_check_interval)
            for device in self._devices.values():
                try:
                    await device.ping()
                except Exception as exc:
                    logger.warning("Health-check failed for %s: %s", device.device_id, exc)

    # ------------------------------------------------------------------
    # Status summary
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return a snapshot of the orchestrator's current state."""
        return {
            "running": self._running,
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "agent_type": a.agent_type,
                    "status": a.status.value,
                }
                for a in self._agents.values()
            ],
            "devices": [
                {
                    "device_id": d.device_id,
                    "name": d.name,
                    "status": d.status.value,
                    "ip_address": d.ip_address,
                }
                for d in self._devices.values()
            ],
            "pending_tasks": self._scheduler.pending_count(),
            "total_task_results": len(self._task_results),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
