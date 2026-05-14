"""
Core Orchestrator - manages multiple ESP32 agents simultaneously.
Supports real-time multi-agent coordination, health monitoring,
task dispatch, and event broadcasting.
"""

import asyncio
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .agent import AgentBase, AgentStatus
from .device import ESP32Device, DeviceStatus
from .scheduler import TaskScheduler
from .router import TaskRouter

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Central orchestrator for multi-agent ESP32 system.

    Manages a fleet of ESP32 devices, dispatches AI-driven agents,
    coordinates frequency/modulation tasks, and handles firmware
    deployment — all in real time.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._agents: Dict[str, AgentBase] = {}
        self._devices: Dict[str, ESP32Device] = {}
        self._scheduler = TaskScheduler()
        self._router = TaskRouter(config.get("router_weights") if config else None)
        self._event_listeners: Dict[str, List[Callable]] = defaultdict(list)
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._health_check_interval = self.config.get("health_check_interval", 10)
        self._task_results: Dict[str, Any] = {}
        logger.info("Orchestrator initialised")

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
        self._emit_event("agent_registered", {"agent_id": agent.agent_id, "agent_type": agent.agent_type})
        logger.info("Registered agent: %s (%s)", agent.agent_type, agent.agent_id)
        return agent.agent_id

    def get_agent(self, agent_id: str) -> Optional[AgentBase]:
        return self._agents.get(agent_id)

    def list_agents(self) -> List[AgentBase]:
        return list(self._agents.values())

    def get_agents_by_type(self, agent_type: str) -> List[AgentBase]:
        return [a for a in self._agents.values() if a.agent_type == agent_type]

    # ------------------------------------------------------------------
    # Task dispatch
    # ------------------------------------------------------------------

    async def dispatch_task(
        self,
        agent_id: str,
        task: str,
        params: Optional[Dict[str, Any]] = None,
        device_id: Optional[str] = None,
    ) -> str:
        """Dispatch a task to a specific agent, optionally targeting a device."""
        agent = self._agents.get(agent_id)
        if agent is None:
            raise ValueError(f"Unknown agent: {agent_id}")

        task_id = str(uuid.uuid4())
        device = self._devices.get(device_id) if device_id else None

        logger.info("Dispatching task %s → agent %s (device=%s)", task, agent_id, device_id)
        self._emit_event(
            "task_dispatched",
            {"task_id": task_id, "agent_id": agent_id, "task": task, "device_id": device_id},
        )

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

    async def route_task(
        self,
        agent_type: str,
        task: str,
        params: Optional[Dict[str, Any]] = None,
        device_id: Optional[str] = None,
        priority: int = 5,
    ) -> str:
        """
        Route a task to the *best available* agent of *agent_type* using the
        built-in :class:`TaskRouter` scoring algorithm.

        The router evaluates all registered agents of the requested type on
        three weighted criteria (availability, success-rate, recency) and
        dispatches to the highest-scoring candidate.  The coroutine is queued
        through the :class:`TaskScheduler` at the given *priority* (lower
        value = higher urgency) so that concurrent workloads are scheduled
        fairly.

        Parameters
        ----------
        agent_type : str
            The type of agent to target (e.g. ``"frequency_agent"``).
        task : str
            The task name understood by that agent type.
        params : dict, optional
            Task-specific parameters forwarded to the agent.
        device_id : str, optional
            Target ESP32 device identifier.
        priority : int
            Scheduler priority (default 5; lower = higher urgency).

        Returns
        -------
        str
            The unique task ID that can be passed to :meth:`get_task_result`.

        Raises
        ------
        ValueError
            If no agents of *agent_type* are registered.
        """
        candidates = self.get_agents_by_type(agent_type)
        if not candidates:
            raise ValueError(f"No agents of type '{agent_type}' registered")

        agent = self._router.select(candidates)
        if agent is None:
            raise ValueError(
                f"TaskRouter could not select an agent of type '{agent_type}'"
            )

        task_id = str(uuid.uuid4())
        dispatch_coro = self.dispatch_task(agent.agent_id, task, params, device_id)
        self._scheduler.schedule(dispatch_coro, task_id, priority=priority,
                                 metadata={"agent_type": agent_type, "task": task})
        inner_id = await self._scheduler.run_next()
        # Expose the result under the outer task_id as well so callers can
        # use either identifier with get_task_result().
        if inner_id and inner_id != task_id:
            self._task_results[task_id] = self._task_results.get(inner_id)
        logger.info(
            "route_task: %s → agent %s (priority=%d)",
            task, agent.agent_id[:8], priority,
        )
        return inner_id or task_id

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
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Event listener error (%s): %s", event, exc)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the orchestrator and all agents."""
        if self._running:
            return
        self._running = True
        self._loop = asyncio.get_event_loop()
        logger.info("Starting orchestrator with %d agent(s) and %d device(s)",
                    len(self._agents), len(self._devices))

        # Start all agents concurrently
        await asyncio.gather(*[a.start() for a in self._agents.values()], return_exceptions=True)
        # Start background health-check loop
        asyncio.ensure_future(self._health_check_loop())
        self._emit_event("orchestrator_started", {"timestamp": datetime.now(timezone.utc).isoformat()})

    async def stop(self) -> None:
        """Gracefully stop all agents and the orchestrator."""
        if not self._running:
            return
        self._running = False
        await asyncio.gather(*[a.stop() for a in self._agents.values()], return_exceptions=True)
        self._emit_event("orchestrator_stopped", {"timestamp": datetime.now(timezone.utc).isoformat()})
        logger.info("Orchestrator stopped")

    async def _health_check_loop(self) -> None:
        """Periodically ping all registered devices."""
        while self._running:
            await asyncio.sleep(self._health_check_interval)
            for device in self._devices.values():
                try:
                    await device.ping()
                except Exception as exc:  # pylint: disable=broad-except
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
