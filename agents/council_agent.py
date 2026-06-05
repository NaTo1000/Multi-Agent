"""
CouncilAgent — orchestrator agent wrapping AICouncil.

Exposes the AI council's parallel/series execution, API-key vault,
real-time formula updates, 369 cluster cross-examination, and build
token metering as dispatchable tasks.

Tasks
-----
run             – Execute the council against a task (honours current mode)
set_mode        – Switch execution mode at runtime (parallel | series)
add_member      – Register a new council member with a vaulted API key
remove_member   – Remove a member and wipe their key from the vault
rotate_key      – Replace a member's API key without downtime
enable_member   – Enable or disable a member without removing them
update_formula  – Set / update a leveraged formula parameter in real time
remove_formula  – Delete a formula parameter
form_clusters   – Partition enabled members into 3-6-9 clusters
rotate_roles    – Advance musical-chairs role rotation by one seat
current_roles   – Return current role assignment for all clustered members
get_token_meter – Return token usage and fairness report
get_status      – Return a safe council status snapshot (keys masked)
"""

import logging
from typing import Any, Dict, Optional

from orchestrator.agent import AgentBase
from orchestrator.device import ESP32Device
from ai.council import AICouncil, ExecutionMode

logger = logging.getLogger(__name__)


class CouncilAgent(AgentBase):
    """
    AI Council orchestrator agent.

    Wraps ``AICouncil`` as a first-class agent so the orchestrator treats it
    identically to every other agent (registration, dispatch, health metrics).

    Configuration keys (``config`` dict / ``council_agent`` YAML section)
    -----------------------------------------------------------------------
    execution_mode          : ``"parallel"`` (default) or ``"series"``
    formulas                : dict of initial formula name → value pairs
    cluster_size            : preferred cluster size, one of 3 / 6 / 9
    token_budget_per_member : token budget before a member is flagged (default 2048)
    hallucination_threshold : score threshold for hallucination flagging (default 0.4)
    members                 : list of dicts with keys ``name``, ``endpoint``,
                              ``api_key``, ``role`` (optional), ``position`` (optional)
    """

    TASKS = {
        "run",
        "set_mode",
        "add_member",
        "remove_member",
        "rotate_key",
        "enable_member",
        "update_formula",
        "remove_formula",
        "form_clusters",
        "rotate_roles",
        "current_roles",
        "get_token_meter",
        "get_status",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__("council_agent", config)
        self.council = AICouncil(config)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _on_start(self) -> None:
        """Pre-register any members defined in the config."""
        for member_cfg in self.config.get("members", []):
            name = member_cfg.get("name")
            endpoint = member_cfg.get("endpoint", "")
            api_key = member_cfg.get("api_key", "")
            role = member_cfg.get("role", "")
            position = member_cfg.get("position")
            if not name:
                logger.warning("CouncilAgent: skipping member with no name in config")
                continue
            if not api_key:
                logger.warning(
                    "CouncilAgent: member '%s' has no api_key — skipping", name
                )
                continue
            try:
                self.council.add_member(name, endpoint, api_key, role=role, position=position)
                logger.info("CouncilAgent: pre-registered member '%s'", name)
            except ValueError as exc:
                logger.warning("CouncilAgent: could not add member '%s': %s", name, exc)

    # ------------------------------------------------------------------
    # AgentBase interface
    # ------------------------------------------------------------------

    async def _execute(
        self,
        task: str,
        params: Dict[str, Any],
        device: Optional[ESP32Device],
    ) -> Any:
        if task == "run":
            return await self.council.run(
                task=params.get("task", "research"),
                params=params.get("params"),
                cross_examine=bool(params.get("cross_examine", False)),
                rotate_before_run=bool(params.get("rotate_before_run", False)),
            )

        if task == "set_mode":
            raw_mode = params.get("mode", ExecutionMode.PARALLEL)
            try:
                mode = ExecutionMode(raw_mode)
            except ValueError:
                raise ValueError(
                    f"Invalid mode '{raw_mode}'. Use 'parallel' or 'series'."
                ) from None
            self.council.set_mode(mode)
            return {"mode": mode.value, "ok": True}

        if task == "add_member":
            name = params.get("name")
            endpoint = params.get("endpoint", "")
            api_key = params.get("api_key", "")
            role = params.get("role", "")
            position = params.get("position")
            if not name:
                raise ValueError("add_member requires 'name'")
            if not api_key:
                raise ValueError("add_member requires 'api_key'")
            key_id = self.council.add_member(name, endpoint, api_key, role=role, position=position)
            return {"ok": True, "name": name, "key_id": key_id}

        if task == "remove_member":
            name = params.get("name")
            if not name:
                raise ValueError("remove_member requires 'name'")
            removed = self.council.remove_member(name)
            return {"ok": removed, "name": name}

        if task == "rotate_key":
            name = params.get("name")
            new_key = params.get("api_key", "")
            if not name:
                raise ValueError("rotate_key requires 'name'")
            if not new_key:
                raise ValueError("rotate_key requires 'api_key'")
            self.council.rotate_key(name, new_key)
            return {"ok": True, "name": name}

        if task == "enable_member":
            name = params.get("name")
            enabled = bool(params.get("enabled", True))
            if not name:
                raise ValueError("enable_member requires 'name'")
            self.council.enable_member(name, enabled)
            return {"ok": True, "name": name, "enabled": enabled}

        if task == "update_formula":
            name = params.get("name")
            value = params.get("value")
            if not name:
                raise ValueError("update_formula requires 'name'")
            self.council.update_formula(name, value)
            return {"ok": True, "name": name, "value": value}

        if task == "remove_formula":
            name = params.get("name")
            if not name:
                raise ValueError("remove_formula requires 'name'")
            removed = self.council.remove_formula(name)
            return {"ok": removed, "name": name}

        if task == "form_clusters":
            preferred_size = params.get("preferred_size")
            return self.council.form_clusters(preferred_size=preferred_size)

        if task == "rotate_roles":
            return {"roles": self.council.rotate_roles(), "ok": True}

        if task == "current_roles":
            return {"roles": self.council.current_roles()}

        if task == "get_token_meter":
            return {
                "fairness": self.council._token_meter.fairness_report(),  # pylint: disable=protected-access
                "innovation": self.council._token_meter.innovation_score(),  # pylint: disable=protected-access
            }

        if task == "get_status":
            return self.council.get_status()

        raise ValueError(f"Unknown CouncilAgent task: {task}")
