"""
Agent base class.  All specialised agents inherit from AgentBase.
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from .core import Orchestrator
    from .device import ESP32Device

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    BUSY = "busy"
    ERROR = "error"
    STOPPED = "stopped"


class AgentBase(ABC):
    """
    Base class for all orchestrator agents.

    Concrete agents override `execute()` to implement their
    domain-specific logic (frequency control, firmware flashing, etc.).
    """

    def __init__(self, agent_type: str, config: Optional[Dict[str, Any]] = None):
        self.agent_id: str = str(uuid.uuid4())
        self.agent_type: str = agent_type
        self.config: Dict[str, Any] = config or {}
        self.status: AgentStatus = AgentStatus.IDLE
        self.orchestrator: Optional["Orchestrator"] = None
        self._metrics: Dict[str, Any] = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "last_task_at": None,
        }
        logger.debug("Agent created: %s (%s)", agent_type, self.agent_id)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Called by the orchestrator when it starts."""
        self.status = AgentStatus.IDLE
        await self._on_start()
        logger.info("Agent started: %s (%s)", self.agent_type, self.agent_id)

    async def stop(self) -> None:
        """Called by the orchestrator during shutdown."""
        self.status = AgentStatus.STOPPED
        await self._on_stop()
        logger.info("Agent stopped: %s (%s)", self.agent_type, self.agent_id)

    async def _on_start(self) -> None:  # pylint: disable=no-self-use
        """Override for custom start-up logic."""

    async def _on_stop(self) -> None:  # pylint: disable=no-self-use
        """Override for custom teardown logic."""

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        task: str,
        params: Dict[str, Any],
        device: Optional["ESP32Device"] = None,
    ) -> Any:
        """Execute a task.  Wraps `_execute` with status tracking."""
        self.status = AgentStatus.BUSY
        self._metrics["last_task_at"] = datetime.now(timezone.utc).isoformat()
        try:
            result = await self._execute(task, params, device)
            self._metrics["tasks_completed"] += 1
            self.status = AgentStatus.IDLE
            return result
        except Exception as exc:  # pylint: disable=broad-except
            self._metrics["tasks_failed"] += 1
            self.status = AgentStatus.ERROR
            logger.error("Agent %s task '%s' failed: %s", self.agent_type, task, exc)
            raise

    @abstractmethod
    async def _execute(
        self,
        task: str,
        params: Dict[str, Any],
        device: Optional["ESP32Device"],
    ) -> Any:
        """Domain-specific task implementation."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "status": self.status.value,
            **self._metrics,
        }
