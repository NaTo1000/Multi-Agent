"""
Automation Engine — high-level AI automation coordinator.

Orchestrates AI agents to perform autonomous operations across the fleet:
- Periodic health-checks
- Proactive interference mitigation
- Fleet-wide optimisation sweeps
- Research-driven configuration updates
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AutomationPolicy:
    """Defines when and how an automation action fires."""

    def __init__(
        self,
        name: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        interval_sec: int = 60,
        enabled: bool = True,
    ):
        self.name = name
        self.action = action
        self.params = params or {}
        self.interval_sec = interval_sec
        self.enabled = enabled
        self.last_run: Optional[str] = None
        self.run_count: int = 0


class AutomationEngine:
    """
    Autonomous policy-driven automation engine.

    Runs a background loop that evaluates registered policies at their
    configured intervals and dispatches the corresponding agent tasks.
    """

    DEFAULT_POLICIES = [
        AutomationPolicy("interference_check", "detect_interference", interval_sec=30),
        AutomationPolicy("fleet_optimise", "auto_tune_fleet", interval_sec=120),
        AutomationPolicy("anomaly_scan", "anomaly_detect", interval_sec=15),
        AutomationPolicy("config_recommend", "recommend_config", interval_sec=300),
    ]

    def __init__(self, orchestrator: Any, config: Optional[Dict[str, Any]] = None):
        self.orchestrator = orchestrator
        self.config = config or {}
        self._policies: List[AutomationPolicy] = list(self.DEFAULT_POLICIES)
        self._running = False
        self._callbacks: Dict[str, List[Callable]] = {}

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def add_policy(self, policy: AutomationPolicy) -> None:
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
                "action": p.action,
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
        asyncio.ensure_future(self._automation_loop())
        logger.info("AutomationEngine started with %d policies", len(self._policies))

    async def stop(self) -> None:
        self._running = False
        logger.info("AutomationEngine stopped")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def _automation_loop(self) -> None:
        """Background loop that evaluates and fires automation policies."""
        policy_timers: Dict[str, float] = {}
        loop_start = asyncio.get_event_loop().time()

        while self._running:
            now = asyncio.get_event_loop().time()
            for policy in self._policies:
                if not policy.enabled:
                    continue
                last = policy_timers.get(policy.name, loop_start - policy.interval_sec)
                if now - last >= policy.interval_sec:
                    policy_timers[policy.name] = now
                    asyncio.ensure_future(self._run_policy(policy))
            await asyncio.sleep(1)

    async def _run_policy(self, policy: AutomationPolicy) -> None:
        """Execute a single automation policy against all AI agents."""
        ai_agents = self.orchestrator.get_agents_by_type("ai_agent")
        if not ai_agents:
            return
        try:
            task_id = await self.orchestrator.dispatch_task(
                ai_agents[0].agent_id,
                policy.action,
                policy.params,
            )
            policy.last_run = datetime.now(timezone.utc).isoformat()
            policy.run_count += 1
            logger.debug("Policy '%s' fired → task %s", policy.name, task_id)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Policy '%s' execution failed: %s", policy.name, exc)
