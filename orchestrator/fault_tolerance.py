"""
Fault Tolerance & Sequencing Engine for the Multi-Agent ESP32 Orchestrator.

This module provides three tightly-integrated components:

``SequencingEngine``
    DAG-based task sequencer.  Steps declare explicit dependencies so the
    engine can determine the correct execution order, run independent steps in
    parallel, and detect cycles before execution begins.

``FaultDetector``
    Behavioural anomaly detector.  Uses Exponentially Weighted Moving Average
    (EWMA) to model normal metric values and raises configurable alerts when
    observations deviate beyond a threshold.  Faults are recorded with severity
    and a human-readable description.

``RollbackManager``
    Checkpoint / snapshot system.  Before each risky operation the caller
    takes a snapshot.  If a fault is detected, ``RollbackManager`` applies the
    most recent clean snapshot *without* interrupting the main process — the
    rollback is dispatched as a background task so the primary workload
    continues unaffected.
"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ===========================================================================
# Shared enums / types
# ===========================================================================

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


class FaultSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ===========================================================================
# SequencingEngine
# ===========================================================================

@dataclass
class SequenceStep:
    """
    One step in a processing sequence.

    Parameters
    ----------
    step_id:
        Unique identifier within the sequence.
    coro_factory:
        Zero-argument callable that returns a coroutine to execute.  A factory
        is used (rather than a pre-created coroutine) so the step can be
        retried or re-run after a rollback.
    depends_on:
        IDs of steps that must complete successfully before this step starts.
    priority:
        Numeric priority — lower numbers run first among steps that are
        concurrently eligible (all dependencies satisfied).
    metadata:
        Arbitrary key-value pairs attached to the step for reporting.
    max_retries:
        Number of automatic retry attempts on failure (default 0 = no retry).
    retry_delay_s:
        Seconds to wait between retry attempts.
    """
    step_id: str
    coro_factory: Callable[[], Coroutine]
    depends_on: List[str] = field(default_factory=list)
    priority: int = 5
    metadata: Dict[str, Any] = field(default_factory=dict)
    max_retries: int = 0
    retry_delay_s: float = 0.5


@dataclass
class StepResult:
    """Result record for a single completed (or failed) step."""
    step_id: str
    status: StepStatus
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    attempts: int = 1

    @property
    def duration_s(self) -> Optional[float]:
        if self.started_at is not None and self.finished_at is not None:
            return self.finished_at - self.started_at
        return None


class CyclicDependencyError(ValueError):
    """Raised when the step dependency graph contains a cycle."""


class SequencingEngine:
    """
    DAG-based task sequencing engine with parallel execution support.

    Execution semantics
    -------------------
    * Steps whose dependencies are all *completed* become *eligible*.
    * Eligible steps are launched concurrently (up to ``max_parallel``).
    * A step failure marks it as *failed*; all steps that (transitively)
      depend on a failed step are *skipped*.
    * The engine supports automatic retry with configurable back-off.
    """

    def __init__(self, max_parallel: int = 8):
        self._steps: Dict[str, SequenceStep] = {}
        self._max_parallel = max_parallel
        self._results: Dict[str, StepResult] = {}

    # ------------------------------------------------------------------
    # Step registration
    # ------------------------------------------------------------------

    def add_step(self, step: SequenceStep) -> None:
        """Register a step with the engine."""
        self._steps[step.step_id] = step

    def add_steps(self, steps: List[SequenceStep]) -> None:
        """Register multiple steps at once."""
        for s in steps:
            self.add_step(s)

    def clear(self) -> None:
        """Remove all steps and results."""
        self._steps.clear()
        self._results.clear()

    # ------------------------------------------------------------------
    # Graph validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """
        Ensure the dependency graph is a DAG (no cycles, no missing deps).

        Raises
        ------
        CyclicDependencyError
            If a dependency cycle is detected.
        ValueError
            If a dependency references a step that does not exist.
        """
        for step in self._steps.values():
            for dep in step.depends_on:
                if dep not in self._steps:
                    raise ValueError(
                        f"Step '{step.step_id}' depends on unknown step '{dep}'"
                    )
        self._topo_sort()   # raises CyclicDependencyError if cycle found

    def _topo_sort(self) -> List[str]:
        """Kahn's algorithm — returns topological order or raises on cycle."""
        in_degree: Dict[str, int] = defaultdict(int)
        for step in self._steps.values():
            if step.step_id not in in_degree:
                in_degree[step.step_id] = 0
            for dep in step.depends_on:
                in_degree[step.step_id] += 1

        queue = deque(sid for sid, deg in in_degree.items() if deg == 0)
        order = []
        while queue:
            sid = queue.popleft()
            order.append(sid)
            # Notify steps that depend on *sid*
            for step in self._steps.values():
                if sid in step.depends_on:
                    in_degree[step.step_id] -= 1
                    if in_degree[step.step_id] == 0:
                        queue.append(step.step_id)

        if len(order) != len(self._steps):
            raise CyclicDependencyError(
                "Dependency cycle detected in sequence steps"
            )
        return order

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run(
        self,
        fault_detector: Optional["FaultDetector"] = None,
        rollback_manager: Optional["RollbackManager"] = None,
    ) -> Dict[str, StepResult]:
        """
        Execute all registered steps respecting dependency order.

        Parameters
        ----------
        fault_detector:
            Optional fault detector — if supplied, metric observations are
            fed to it after each step completes and a non-blocking rollback
            is triggered on high/critical faults.
        rollback_manager:
            Optional rollback manager — used when fault_detector raises a
            high-severity fault.

        Returns
        -------
        dict
            Mapping of step_id → StepResult.
        """
        self.validate()
        self._results.clear()

        completed: Set[str] = set()
        failed: Set[str] = set()
        running: Dict[str, asyncio.Task] = {}

        pending = set(self._steps)
        semaphore = asyncio.Semaphore(self._max_parallel)

        async def _run_step(step: SequenceStep) -> None:
            attempt = 0
            last_exc: Optional[Exception] = None
            while attempt <= step.max_retries:
                attempt += 1
                self._results[step.step_id] = StepResult(
                    step_id=step.step_id,
                    status=StepStatus.RUNNING,
                    started_at=time.monotonic(),
                    attempts=attempt,
                )
                try:
                    async with semaphore:
                        result = await step.coro_factory()
                    self._results[step.step_id].result = result
                    self._results[step.step_id].status = StepStatus.COMPLETED
                    self._results[step.step_id].finished_at = time.monotonic()
                    logger.debug(
                        "Step '%s' completed (attempt %d)", step.step_id, attempt
                    )
                    # Feed duration as an observation to the fault detector
                    if fault_detector and self._results[step.step_id].duration_s is not None:
                        dur = self._results[step.step_id].duration_s
                        fault_detector.observe(f"step_duration_{step.step_id}", dur)
                    return
                except Exception as exc:  # pylint: disable=broad-except
                    last_exc = exc
                    logger.warning(
                        "Step '%s' failed (attempt %d/%d): %s",
                        step.step_id, attempt, step.max_retries + 1, exc,
                    )
                    self._results[step.step_id].error = str(exc)
                    if attempt <= step.max_retries:
                        await asyncio.sleep(step.retry_delay_s)

            # All attempts exhausted
            self._results[step.step_id].status = StepStatus.FAILED
            self._results[step.step_id].finished_at = time.monotonic()
            failed.add(step.step_id)

            if fault_detector:
                fault = fault_detector.record_fault(
                    metric=f"step_{step.step_id}",
                    description=f"Step '{step.step_id}' failed after {attempt} attempt(s): {last_exc}",
                    severity=FaultSeverity.HIGH,
                )
                if rollback_manager and fault.severity in (
                    FaultSeverity.HIGH, FaultSeverity.CRITICAL
                ):
                    asyncio.ensure_future(
                        rollback_manager.non_blocking_rollback(fault.fault_id)
                    )

        while pending or running:
            # Find newly eligible steps
            newly_eligible = []
            for sid in list(pending):
                step = self._steps[sid]
                # A step can be evaluated when all its dependencies are "settled"
                # (either completed, failed, or skipped)
                skipped_ids = {
                    s for s, r in self._results.items()
                    if r.status in (StepStatus.SKIPPED, StepStatus.ROLLED_BACK)
                }
                all_settled = all(
                    d in completed or d in failed or d in skipped_ids
                    for d in step.depends_on
                )
                if all_settled:
                    # Skip if any dependency failed or was skipped
                    has_failed_dep = any(
                        d in failed or d in skipped_ids
                        for d in step.depends_on
                    )
                    if has_failed_dep:
                        self._results[sid] = StepResult(
                            step_id=sid, status=StepStatus.SKIPPED
                        )
                        pending.discard(sid)
                    else:
                        newly_eligible.append(step)
                        pending.discard(sid)

            # Sort by priority before launching
            newly_eligible.sort(key=lambda s: s.priority)
            for step in newly_eligible:
                t = asyncio.ensure_future(_run_step(step))
                running[step.step_id] = t

            if not running:
                # Nothing running and nothing newly eligible — stall
                # (should not happen after validate(), but guard anyway)
                break

            # Wait for at least one running task to finish
            done, _ = await asyncio.wait(
                running.values(), return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                # Identify which step this task belongs to
                for sid, t in list(running.items()):
                    if t is task:
                        del running[sid]
                        if self._results.get(sid, StepResult(sid, StepStatus.PENDING)).status == StepStatus.COMPLETED:
                            completed.add(sid)
                        # failed steps were already added inside _run_step
                        break

        return dict(self._results)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_summary(self) -> Dict[str, Any]:
        """Return a structured execution summary for reporting."""
        total = len(self._results)
        by_status: Dict[str, int] = defaultdict(int)
        total_duration = 0.0
        for r in self._results.values():
            by_status[r.status.value] += 1
            if r.duration_s:
                total_duration += r.duration_s
        return {
            "total_steps": total,
            "by_status": dict(by_status),
            "total_duration_s": round(total_duration, 4),
            "steps": [
                {
                    "step_id": r.step_id,
                    "status": r.status.value,
                    "duration_s": round(r.duration_s, 4) if r.duration_s else None,
                    "attempts": r.attempts,
                    "error": r.error,
                }
                for r in self._results.values()
            ],
        }


# ===========================================================================
# FaultDetector
# ===========================================================================

@dataclass
class FaultRecord:
    """A recorded fault event."""
    fault_id: str
    metric: str
    description: str
    severity: FaultSeverity
    value: Optional[float]
    threshold: Optional[float]
    timestamp: float = field(default_factory=time.monotonic)
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fault_id": self.fault_id,
            "metric": self.metric,
            "description": self.description,
            "severity": self.severity.value,
            "value": self.value,
            "threshold": self.threshold,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
        }


class FaultDetector:
    """
    Behavioural anomaly detector using Exponentially Weighted Moving Average.

    How it works
    ------------
    For each named metric the detector maintains an EWMA of observed values
    and a rolling variance estimate.  When a new observation deviates by more
    than ``sigma_threshold`` standard deviations from the EWMA, a fault is
    raised with the appropriate severity.

    Severity mapping (deviation in σ)
    ----------------------------------
    * 2 ≤ σ < 3  → LOW
    * 3 ≤ σ < 4  → MEDIUM
    * 4 ≤ σ < 6  → HIGH
    * σ ≥ 6      → CRITICAL
    """

    def __init__(
        self,
        alpha: float = 0.1,          # EWMA smoothing factor (0 < α ≤ 1)
        sigma_threshold: float = 2.0, # deviation to start raising faults
        window: int = 50,             # keep last N observations per metric
    ):
        if not 0 < alpha <= 1:
            raise ValueError("alpha must be in (0, 1]")
        self._alpha = alpha
        self._sigma_threshold = sigma_threshold
        self._window = window

        # Per-metric state
        self._ewma: Dict[str, float] = {}
        self._ewma_var: Dict[str, float] = {}   # EWMA of squared deviation
        self._history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window))
        self._faults: List[FaultRecord] = []
        self._fault_callbacks: List[Callable[[FaultRecord], None]] = []

    # ------------------------------------------------------------------
    # Observation
    # ------------------------------------------------------------------

    def observe(self, metric: str, value: float) -> Optional[FaultRecord]:
        """
        Feed a new observation for *metric*.

        Returns a FaultRecord if an anomaly is detected, else None.
        """
        self._history[metric].append(value)

        if metric not in self._ewma:
            # Bootstrap: first observation
            self._ewma[metric] = value
            self._ewma_var[metric] = 0.0
            return None

        ewma = self._ewma[metric]
        ewma_var = self._ewma_var[metric]

        deviation = value - ewma
        self._ewma[metric] = ewma + self._alpha * deviation
        self._ewma_var[metric] = (1 - self._alpha) * (ewma_var + self._alpha * deviation ** 2)

        std = self._ewma_var[metric] ** 0.5
        if std < 1e-12:
            return None   # No variance yet — cannot assess anomaly

        sigma = abs(deviation) / std
        if sigma < self._sigma_threshold:
            return None

        severity = self._sigma_to_severity(sigma)
        fault = self.record_fault(
            metric=metric,
            description=(
                f"Anomaly on '{metric}': observed {value:.4g}, "
                f"EWMA {ewma:.4g}, deviation {sigma:.2f}σ"
            ),
            severity=severity,
            value=value,
            threshold=ewma + self._sigma_threshold * std,
        )
        return fault

    @staticmethod
    def _sigma_to_severity(sigma: float) -> FaultSeverity:
        if sigma >= 6:
            return FaultSeverity.CRITICAL
        if sigma >= 4:
            return FaultSeverity.HIGH
        if sigma >= 3:
            return FaultSeverity.MEDIUM
        return FaultSeverity.LOW

    # ------------------------------------------------------------------
    # Manual fault recording
    # ------------------------------------------------------------------

    def record_fault(
        self,
        metric: str,
        description: str,
        severity: FaultSeverity = FaultSeverity.MEDIUM,
        value: Optional[float] = None,
        threshold: Optional[float] = None,
    ) -> FaultRecord:
        """Explicitly record a fault (e.g. from step failure)."""
        fault = FaultRecord(
            fault_id=str(uuid.uuid4()),
            metric=metric,
            description=description,
            severity=severity,
            value=value,
            threshold=threshold,
        )
        self._faults.append(fault)
        logger.warning(
            "Fault detected [%s] on '%s': %s", severity.value, metric, description
        )
        for cb in self._fault_callbacks:
            try:
                cb(fault)
            except Exception:  # pylint: disable=broad-except
                pass
        return fault

    def on_fault(self, callback: Callable[[FaultRecord], None]) -> None:
        """Register a callback invoked whenever a fault is raised."""
        self._fault_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_faults(
        self,
        metric: Optional[str] = None,
        severity: Optional[FaultSeverity] = None,
        unresolved_only: bool = False,
    ) -> List[FaultRecord]:
        faults = self._faults
        if metric:
            faults = [f for f in faults if f.metric == metric]
        if severity:
            faults = [f for f in faults if f.severity == severity]
        if unresolved_only:
            faults = [f for f in faults if not f.resolved]
        return list(faults)

    def resolve_fault(self, fault_id: str) -> bool:
        """Mark a fault as resolved."""
        for fault in self._faults:
            if fault.fault_id == fault_id:
                fault.resolved = True
                return True
        return False

    def get_ewma(self, metric: str) -> Optional[float]:
        """Return the current EWMA estimate for a metric."""
        return self._ewma.get(metric)

    def get_history(self, metric: str) -> List[float]:
        """Return the recent observation history for a metric."""
        return list(self._history.get(metric, []))

    def reset(self, metric: Optional[str] = None) -> None:
        """Reset state, optionally for a single metric."""
        if metric:
            self._ewma.pop(metric, None)
            self._ewma_var.pop(metric, None)
            self._history.pop(metric, None)
        else:
            self._ewma.clear()
            self._ewma_var.clear()
            self._history.clear()


# ===========================================================================
# RollbackManager
# ===========================================================================

@dataclass
class Checkpoint:
    """A named system-state snapshot."""
    checkpoint_id: str
    label: str
    state: Any                   # Arbitrary serialisable state dict
    timestamp: float = field(default_factory=time.monotonic)
    fault_id: Optional[str] = None   # Fault that triggered this rollback (if any)


class RollbackManager:
    """
    Non-blocking checkpoint / rollback manager.

    The caller takes snapshots of relevant system state before risky
    operations.  If a fault is detected, ``non_blocking_rollback`` launches
    the restore coroutine as a background task so the main process keeps
    running.

    Parameters
    ----------
    restore_callback:
        ``async def restore(state: Any) -> None`` coroutine factory.  Called
        with the state dict from the most recent clean checkpoint.
    max_checkpoints:
        Maximum number of checkpoints to retain (FIFO eviction).
    """

    def __init__(
        self,
        restore_callback: Callable[[Any], Coroutine],
        max_checkpoints: int = 20,
    ):
        self._restore = restore_callback
        self._max = max_checkpoints
        self._checkpoints: deque[Checkpoint] = deque(maxlen=max_checkpoints)
        self._rollback_history: List[Dict[str, Any]] = []
        self._active_rollbacks: Set[str] = set()

    # ------------------------------------------------------------------
    # Checkpoint management
    # ------------------------------------------------------------------

    def take_checkpoint(self, label: str, state: Any) -> Checkpoint:
        """
        Record a named snapshot of the current system state.

        Parameters
        ----------
        label:
            Human-readable description (e.g. ``"before_ota_flash"``).
        state:
            Arbitrary object representing the state to restore.  Typically a
            ``dict`` with relevant field values.
        """
        cp = Checkpoint(
            checkpoint_id=str(uuid.uuid4()),
            label=label,
            state=state,
        )
        self._checkpoints.append(cp)
        logger.debug(
            "Checkpoint '%s' taken (id=%s)", label, cp.checkpoint_id
        )
        return cp

    def get_latest_checkpoint(self) -> Optional[Checkpoint]:
        """Return the most recently taken checkpoint, or None."""
        return self._checkpoints[-1] if self._checkpoints else None

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Return a specific checkpoint by ID."""
        for cp in reversed(self._checkpoints):
            if cp.checkpoint_id == checkpoint_id:
                return cp
        return None

    def list_checkpoints(self) -> List[Checkpoint]:
        """Return all retained checkpoints (oldest first)."""
        return list(self._checkpoints)

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    async def non_blocking_rollback(
        self,
        fault_id: str,
        checkpoint: Optional[Checkpoint] = None,
    ) -> None:
        """
        Initiate a rollback *without* blocking the caller.

        The restore coroutine is run as a background asyncio task.  The main
        execution sequence continues while the rollback is in progress.

        Parameters
        ----------
        fault_id:
            ID of the fault that triggered this rollback (for audit logging).
        checkpoint:
            Specific checkpoint to restore.  If ``None``, the most recent
            checkpoint is used.
        """
        if fault_id in self._active_rollbacks:
            logger.debug("Rollback already in progress for fault %s", fault_id)
            return

        cp = checkpoint or self.get_latest_checkpoint()
        if cp is None:
            logger.warning("No checkpoint available — rollback aborted")
            return

        self._active_rollbacks.add(fault_id)
        logger.info(
            "Non-blocking rollback initiated (fault=%s, checkpoint=%s '%s')",
            fault_id, cp.checkpoint_id, cp.label,
        )

        async def _do_rollback() -> None:
            try:
                await self._restore(cp.state)
                self._rollback_history.append({
                    "fault_id": fault_id,
                    "checkpoint_id": cp.checkpoint_id,
                    "label": cp.label,
                    "timestamp": time.monotonic(),
                    "success": True,
                })
                logger.info("Rollback completed (fault=%s)", fault_id)
            except Exception as exc:  # pylint: disable=broad-except
                self._rollback_history.append({
                    "fault_id": fault_id,
                    "checkpoint_id": cp.checkpoint_id,
                    "label": cp.label,
                    "timestamp": time.monotonic(),
                    "success": False,
                    "error": str(exc),
                })
                logger.error("Rollback failed (fault=%s): %s", fault_id, exc)
            finally:
                self._active_rollbacks.discard(fault_id)

        asyncio.ensure_future(_do_rollback())

    async def blocking_rollback(
        self,
        checkpoint: Optional[Checkpoint] = None,
    ) -> bool:
        """
        Perform a rollback and *wait* for it to complete.

        Use this only when you explicitly want to pause until the state is
        restored (e.g. in test helpers or CLI operations).
        """
        cp = checkpoint or self.get_latest_checkpoint()
        if cp is None:
            logger.warning("No checkpoint available")
            return False
        try:
            await self._restore(cp.state)
            return True
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Blocking rollback failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_rollback_history(self) -> List[Dict[str, Any]]:
        """Return the list of completed rollback records."""
        return list(self._rollback_history)

    def is_rollback_active(self) -> bool:
        """Return True if any rollback is currently in progress."""
        return bool(self._active_rollbacks)


# ===========================================================================
# Convenience: FaultTolerantSequencer
# ===========================================================================

class FaultTolerantSequencer:
    """
    High-level façade that combines the three engines.

    Provides a single entry point for building and executing fault-tolerant
    task sequences.

    Parameters
    ----------
    restore_callback:
        Async callable invoked with a state dict when a rollback is triggered.
    max_parallel:
        Maximum number of steps to run concurrently.
    ewma_alpha:
        EWMA smoothing factor for the fault detector.
    sigma_threshold:
        Anomaly detection threshold (standard deviations).
    """

    def __init__(
        self,
        restore_callback: Optional[Callable[[Any], Coroutine]] = None,
        max_parallel: int = 8,
        ewma_alpha: float = 0.1,
        sigma_threshold: float = 2.0,
    ):
        self.sequencer = SequencingEngine(max_parallel=max_parallel)
        self.detector = FaultDetector(alpha=ewma_alpha, sigma_threshold=sigma_threshold)

        async def _noop_restore(_state: Any) -> None:
            pass

        self.rollback_manager = RollbackManager(
            restore_callback=restore_callback or _noop_restore
        )

    def add_step(self, step: SequenceStep) -> None:
        self.sequencer.add_step(step)

    def checkpoint(self, label: str, state: Any) -> Checkpoint:
        return self.rollback_manager.take_checkpoint(label, state)

    async def execute(self) -> Dict[str, StepResult]:
        """Execute the sequence with full fault detection and rollback support."""
        return await self.sequencer.run(
            fault_detector=self.detector,
            rollback_manager=self.rollback_manager,
        )

    def summary(self) -> Dict[str, Any]:
        """Return a combined report from sequencer, detector, and rollback manager."""
        seq_summary = self.sequencer.get_summary()
        return {
            "sequence": seq_summary,
            "faults": [f.to_dict() for f in self.detector.get_faults()],
            "rollbacks": self.rollback_manager.get_rollback_history(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
