"""
AI Council — multi-member AI panel with API-key vault, parallel/series
execution switching, and real-time leveraged formula updates.

Architecture
------------

                       ┌─────────────────────────────────────┐
                       │            AICouncil                │
                       │                                     │
                       │  ApiKeyVault                        │
                       │  ┌───────────────────────────────┐  │
                       │  │  key_id → masked/raw key      │  │
                       │  └───────────────────────────────┘  │
                       │                                     │
                       │  CouncilMembers  [A, B, C, …]       │
                       │  each with: name, endpoint,         │
                       │             key_id, role            │
                       │                                     │
                       │  ExecutionMode                      │
                       │  ┌─────────────┐  ┌─────────────┐  │
                       │  │  PARALLEL   │  │   SERIES    │  │
                       │  │ all members │  │ A→B→C chain │  │
                       │  │ concurrently│  │ output feeds│  │
                       │  │ → aggregate │  │ next input  │  │
                       │  └─────────────┘  └─────────────┘  │
                       │                                     │
                       │  Leveraged Formulas (live update)   │
                       │  ┌───────────────────────────────┐  │
                       │  │  name → value (float/dict)    │  │
                       │  │  injected into every call     │  │
                       │  └───────────────────────────────┘  │
                       └─────────────────────────────────────┘

Key concepts
------------
- ApiKeyVault  — stores API keys by opaque key_id; keys are never logged.
- CouncilMember — an AI endpoint registered in the council with a vaulted key.
- ExecutionMode — PARALLEL (gather) or SERIES (chain); switchable at runtime.
- Leveraged formulas — named float/dict parameters merged into every request
  and updatable mid-run so behaviour adapts in real time.
"""

import asyncio
import json
import logging
import secrets
import urllib.request
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# API Key Vault
# ---------------------------------------------------------------------------

class ApiKeyVault:
    """
    Secure in-process vault for API keys.

    Keys are stored by an opaque ``key_id`` generated at registration time.
    The raw key is never surfaced in logs or status dictionaries; only the
    masked form (first 4 chars + ``****``) is exposed externally.
    """

    def __init__(self) -> None:
        self._store: Dict[str, str] = {}

    def store(self, api_key: str) -> str:
        """Store a key and return its opaque ``key_id``."""
        if not api_key:
            raise ValueError("api_key must not be empty")
        key_id = secrets.token_hex(16)
        self._store[key_id] = api_key
        logger.debug("ApiKeyVault: stored key %s", self._masked(key_id))
        return key_id

    def retrieve(self, key_id: str) -> str:
        """Return the raw key.  Raises ``KeyError`` if not found."""
        try:
            return self._store[key_id]
        except KeyError:
            raise KeyError(f"ApiKeyVault: key_id '{key_id}' not found") from None

    def rotate(self, key_id: str, new_api_key: str) -> None:
        """Replace the key stored under ``key_id``."""
        if key_id not in self._store:
            raise KeyError(f"ApiKeyVault: key_id '{key_id}' not found")
        if not new_api_key:
            raise ValueError("new_api_key must not be empty")
        self._store[key_id] = new_api_key
        logger.debug("ApiKeyVault: rotated key %s", self._masked(key_id))

    def remove(self, key_id: str) -> bool:
        """Delete a key from the vault.  Returns True if it existed."""
        existed = key_id in self._store
        self._store.pop(key_id, None)
        return existed

    def masked(self, key_id: str) -> str:
        """Return a safe display form of the key (first 4 chars + *****)."""
        return self._masked(key_id)

    def _masked(self, key_id: str) -> str:
        raw = self._store.get(key_id, "")
        if not raw:
            return "****"
        return raw[:4] + "****"

    def __len__(self) -> int:
        return len(self._store)


# ---------------------------------------------------------------------------
# Execution mode
# ---------------------------------------------------------------------------

class ExecutionMode(str, Enum):
    """Controls how the council processes a task across its members."""

    PARALLEL = "parallel"
    """All members execute concurrently; results are aggregated."""

    SERIES = "series"
    """Members execute sequentially; each member's output feeds the next."""


# ---------------------------------------------------------------------------
# Council member
# ---------------------------------------------------------------------------

class CouncilMember:
    """
    A single seat on the AI council.

    Attributes
    ----------
    name      : Human-readable identifier (e.g. ``"strategist"``).
    endpoint  : HTTP URL of the AI service this member calls.
    key_id    : Opaque reference into the ``ApiKeyVault``.
    role      : Free-form description of this member's speciality.
    position  : Integer seat order — governs series execution order.
    enabled   : Toggle a member in/out without removing it.
    """

    def __init__(
        self,
        name: str,
        endpoint: str,
        key_id: str,
        role: str = "",
        position: int = 0,
        enabled: bool = True,
    ) -> None:
        self.name = name
        self.endpoint = endpoint
        self.key_id = key_id
        self.role = role
        self.position = position
        self.enabled = enabled
        self.calls_made: int = 0
        self.last_called: Optional[str] = None

    def to_dict(self, vault: "ApiKeyVault") -> Dict[str, Any]:
        """Return a safe status snapshot (key is masked)."""
        return {
            "name": self.name,
            "endpoint": self.endpoint,
            "key_masked": vault.masked(self.key_id),
            "role": self.role,
            "position": self.position,
            "enabled": self.enabled,
            "calls_made": self.calls_made,
            "last_called": self.last_called,
        }


# ---------------------------------------------------------------------------
# AI Council
# ---------------------------------------------------------------------------

class AICouncil:
    """
    Multi-member AI council with vaulted API keys, parallel/series execution,
    and real-time leveraged formula injection.

    Usage
    -----
    ::

        vault = ApiKeyVault()
        council = AICouncil()

        # Register members
        council.add_member("strategist", "https://api.openai.com/v1/chat/completions",
                           "sk-...", role="High-level planning")
        council.add_member("analyst",    "https://api.anthropic.com/v1/messages",
                           "sk-ant-...", role="Deep analysis")

        # Set dynamic formulas
        council.update_formula("temperature", 0.7)
        council.update_formula("max_tokens", 512)

        # Run in parallel (default)
        result = await council.run("research", {"query": "Best LoRa config for ESP32"})

        # Switch to series at runtime
        council.set_mode(ExecutionMode.SERIES)
        result = await council.run("research", {"query": "Best LoRa config for ESP32"})
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._vault = ApiKeyVault()
        self._members: Dict[str, CouncilMember] = {}
        self._mode: ExecutionMode = ExecutionMode(
            self.config.get("execution_mode", ExecutionMode.PARALLEL)
        )
        # Leveraged formulas — injected into every member call
        self._formulas: Dict[str, Any] = dict(self.config.get("formulas", {}))
        self._run_count: int = 0

    # ------------------------------------------------------------------
    # Member management
    # ------------------------------------------------------------------

    def add_member(
        self,
        name: str,
        endpoint: str,
        api_key: str,
        role: str = "",
        position: Optional[int] = None,
    ) -> str:
        """
        Register a new council member.

        Parameters
        ----------
        name     : Unique member identifier.
        endpoint : AI service URL.
        api_key  : Raw API key — stored in the vault immediately.
        role     : Optional description of the member's speciality.
        position : Series execution order (auto-assigned if omitted).

        Returns
        -------
        str
            The opaque ``key_id`` assigned in the vault.
        """
        if name in self._members:
            raise ValueError(f"Council member '{name}' already exists")
        key_id = self._vault.store(api_key)
        pos = position if position is not None else len(self._members)
        member = CouncilMember(name, endpoint, key_id, role=role, position=pos)
        self._members[name] = member
        logger.info("AICouncil: added member '%s' (role=%s, position=%d)", name, role, pos)
        return key_id

    def remove_member(self, name: str) -> bool:
        """Remove a member and wipe their key from the vault."""
        member = self._members.pop(name, None)
        if member is None:
            return False
        self._vault.remove(member.key_id)
        logger.info("AICouncil: removed member '%s'", name)
        return True

    def enable_member(self, name: str, enabled: bool = True) -> None:
        """Enable or disable a council member without removing them."""
        member = self._members.get(name)
        if member is None:
            raise KeyError(f"No council member named '{name}'")
        member.enabled = enabled

    def rotate_key(self, name: str, new_api_key: str) -> None:
        """Replace the API key for a member in the vault."""
        member = self._members.get(name)
        if member is None:
            raise KeyError(f"No council member named '{name}'")
        self._vault.rotate(member.key_id, new_api_key)
        logger.info("AICouncil: rotated key for member '%s'", name)

    # ------------------------------------------------------------------
    # Mode switching (parallel ↔ series)
    # ------------------------------------------------------------------

    def set_mode(self, mode: ExecutionMode) -> None:
        """Switch execution mode at runtime (takes effect on the next run)."""
        if self._mode != mode:
            logger.info("AICouncil: switched execution mode %s → %s", self._mode.value, mode.value)
        self._mode = mode

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    # ------------------------------------------------------------------
    # Leveraged formulas (real-time updates)
    # ------------------------------------------------------------------

    def update_formula(self, name: str, value: Any) -> None:
        """
        Set or update a leveraged formula parameter.

        Formula values are merged into every member's request params on
        each ``run()`` call, so changes take effect immediately without
        restarting the council.

        Parameters
        ----------
        name  : Formula name (e.g. ``"temperature"``, ``"gain"``).
        value : New value (float, int, dict, or any JSON-serialisable type).
        """
        self._formulas[name] = value
        logger.debug("AICouncil: formula '%s' updated → %r", name, value)

    def remove_formula(self, name: str) -> bool:
        """Remove a formula parameter."""
        existed = name in self._formulas
        self._formulas.pop(name, None)
        return existed

    @property
    def formulas(self) -> Dict[str, Any]:
        """Read-only snapshot of current formula values."""
        return dict(self._formulas)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run(
        self,
        task: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the council against a task.

        Current formula values are merged into ``params`` before dispatch.
        Execution follows the configured ``ExecutionMode``.

        Parameters
        ----------
        task   : Logical task name passed to each member.
        params : Base parameters; formulas are merged on top.

        Returns
        -------
        dict
            ``mode``, ``task``, ``formulas_applied``, and ``results`` (list).
        """
        effective_params = {**(params or {}), **self._formulas}
        active = sorted(
            [m for m in self._members.values() if m.enabled],
            key=lambda m: m.position,
        )
        if not active:
            logger.warning("AICouncil.run: no enabled members")
            return {
                "mode": self._mode.value,
                "task": task,
                "formulas_applied": dict(self._formulas),
                "results": [],
                "warning": "no_enabled_members",
            }

        self._run_count += 1
        logger.info(
            "AICouncil.run #%d: task='%s' mode=%s members=%d",
            self._run_count, task, self._mode.value, len(active),
        )

        if self._mode == ExecutionMode.PARALLEL:
            results = await self._run_parallel(task, effective_params, active)
        else:
            results = await self._run_series(task, effective_params, active)

        return {
            "mode": self._mode.value,
            "task": task,
            "formulas_applied": dict(self._formulas),
            "run_index": self._run_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": results,
        }

    async def _run_parallel(
        self,
        task: str,
        params: Dict[str, Any],
        members: List[CouncilMember],
    ) -> List[Dict[str, Any]]:
        """Dispatch task to all members concurrently and collect results."""
        coros = [self._call_member(m, task, params, chain_input=None) for m in members]
        return list(await asyncio.gather(*coros, return_exceptions=False))

    async def _run_series(
        self,
        task: str,
        params: Dict[str, Any],
        members: List[CouncilMember],
    ) -> List[Dict[str, Any]]:
        """
        Execute members sequentially, feeding each member's output as
        ``chain_input`` into the next member's request.
        """
        results: List[Dict[str, Any]] = []
        chain_input: Optional[Any] = None
        for member in members:
            result = await self._call_member(member, task, params, chain_input=chain_input)
            results.append(result)
            # The raw response becomes the next member's chain input
            chain_input = result.get("response")
        return results

    # ------------------------------------------------------------------
    # Per-member HTTP call
    # ------------------------------------------------------------------

    async def _call_member(
        self,
        member: CouncilMember,
        task: str,
        params: Dict[str, Any],
        chain_input: Optional[Any],
    ) -> Dict[str, Any]:
        """
        Invoke one council member's AI endpoint.

        Falls back to a built-in heuristic response when no endpoint is
        configured or when the HTTP call fails, so the council degrades
        gracefully without crashing the pipeline.
        """
        member.calls_made += 1
        member.last_called = datetime.now(timezone.utc).isoformat()

        if not member.endpoint:
            return self._heuristic_response(member, task, params, chain_input)

        try:
            raw_key = self._vault.retrieve(member.key_id)
            body = json.dumps({
                "task": task,
                "params": params,
                "chain_input": chain_input,
                "member_role": member.role,
            }).encode()
            req = urllib.request.Request(
                member.endpoint,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"******",
                },
            )
            loop = asyncio.get_event_loop()
            raw_response = await loop.run_in_executor(
                None, lambda: self._http_call(req)
            )
            return {
                "member": member.name,
                "role": member.role,
                "source": "endpoint",
                "response": raw_response,
                "chain_input_received": chain_input is not None,
            }
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "AICouncil member '%s' endpoint call failed: %s — using heuristics",
                member.name, exc,
            )
            return self._heuristic_response(member, task, params, chain_input)

    @staticmethod
    def _http_call(req: urllib.request.Request) -> Any:
        """Synchronous HTTP call executed in a thread-pool executor."""
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    @staticmethod
    def _heuristic_response(
        member: CouncilMember,
        task: str,
        params: Dict[str, Any],
        chain_input: Optional[Any],
    ) -> Dict[str, Any]:
        """Built-in fallback when no live endpoint is available."""
        query = params.get("query", task)
        prior = f" (building on: {str(chain_input)[:80]})" if chain_input else ""
        return {
            "member": member.name,
            "role": member.role,
            "source": "builtin_heuristics",
            "response": (
                f"[{member.name}/{member.role}] Heuristic analysis of '{query}'{prior}: "
                "Recommended approach — evaluate signal conditions, apply adaptive "
                "frequency selection, and leverage real-time telemetry feedback loops "
                "for continuous optimisation across the device fleet."
            ),
            "chain_input_received": chain_input is not None,
        }

    # ------------------------------------------------------------------
    # Status / introspection
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return a safe status snapshot (API keys masked)."""
        return {
            "mode": self._mode.value,
            "members": [m.to_dict(self._vault) for m in sorted(
                self._members.values(), key=lambda m: m.position
            )],
            "formulas": dict(self._formulas),
            "vault_size": len(self._vault),
            "total_runs": self._run_count,
        }
