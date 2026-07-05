"""
Multi-Agent CLI — collaborative prompt execution across all configured AI workers.

When a user enters a prompt the session runs three phases:

  1. **Deliberation** — every active worker reviews the prompt against its
     skill profile (the MCP Skills Registry) and claims the tasks it can best
     handle.  Task assignment follows a least-loaded, best-skill strategy.

  2. **Execution** — all claimed tasks are launched concurrently with
     ``asyncio.gather``.  Each worker runs an async work-stealing loop: once
     it finishes its own tasks it immediately pulls the next available task
     from the shared queue, using whichever skill fits.

  3. **Summary** — results are printed per task; per-worker stats show how
     many tasks each worker completed as primary handler vs. as a helper.

Short-key prompting
-------------------
Instead of a full natural-language sentence you can type one or more
space-separated *short keys* to trigger specific tasks directly.  Keys
can be combined freely — the system queues all matched tasks in a single
pass:

    ▸ f          → read frequency
    ▸ w b        → wifi scan + BLE scan
    ▸ f m o      → frequency + modulation + auto-optimise
    ▸ ?          → show the full key reference table

Type ``help`` or ``?`` inside the interactive session to see the complete
key reference.

Usage::

    python main.py --mode multi-agent                    # interactive
    python main.py --mode multi-agent --prompt "w b d"  # one-shot via short keys
    python -m cli.multi_agent_cli                        # direct entry
    python -m cli.multi_agent_cli -p "research lora"     # one-shot NL
"""

import asyncio
import logging
import sys
import textwrap
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task model
# ---------------------------------------------------------------------------

class TaskStatus(Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    RUNNING = "running"
    DONE    = "done"
    FAILED  = "failed"


@dataclass
class WorkTask:
    task_id:     str
    name:        str              # matches an agent's TASKS set
    agent_type:  str              # orchestrator agent type
    params:      Dict[str, Any]
    description: str
    status:      TaskStatus = TaskStatus.PENDING
    claimed_by:  str        = ""
    result:      Any        = None
    started_at:  float      = 0.0
    finished_at: float      = 0.0


# ---------------------------------------------------------------------------
# MCP Skills Registry
# ---------------------------------------------------------------------------
# Skill profiles declare which orchestrator agent types each AI provider
# handles best.  This is the "MCP server list" used during deliberation.

SKILLS_REGISTRY: Dict[str, List[str]] = {
    "watsonx": ["ai_agent", "firmware_agent"],
    "kimi":    ["ai_agent", "comms_agent"],
    "kai9000": ["frequency_agent", "modulation_agent"],
    "manus":   ["ai_agent", "frequency_agent", "modulation_agent",
                "firmware_agent", "comms_agent"],
    "builtin": ["ai_agent", "frequency_agent", "modulation_agent",
                "firmware_agent", "comms_agent"],
}


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

@dataclass
class Worker:
    name:              str
    skills:            List[str]
    provider_instance: Any = None     # CHAiMERAProvider or None for builtin
    tasks_completed:   int = 0
    tasks_helped:      int = 0        # tasks stolen from another worker's queue


# ---------------------------------------------------------------------------
# Prompt → task decomposition
# ---------------------------------------------------------------------------
# Each entry: (trigger_keywords, agent_type, task_name, description, extra_params)

_TASK_PATTERNS = [
    # Frequency
    ({"frequency", "freq", "channel", "band", "hop", "rf", "ghz", "mhz"},
     "frequency_agent", "get_frequency",
     "Read current operating frequency", {}),
    ({"tune", "fine_tune", "fine-tune"},
     "frequency_agent", "fine_tune",
     "Fine-tune frequency for best RSSI",
     {"step_hz": 500_000, "iterations": 5}),
    # Modulation
    ({"modulation", "modulate", "gfsk", "lora", "qam", "scheme"},
     "modulation_agent", "get_scheme",
     "Get current modulation scheme", {}),
    # Firmware
    ({"firmware", "flash", "build", "compile", "update firmware"},
     "firmware_agent", "build",
     "Build firmware image",
     {"template": "base", "features": ["wifi", "ble"], "version": "auto"}),
    # WiFi
    ({"wifi", "ssid", "network", "scan wifi"},
     "comms_agent", "wifi_scan",
     "Scan for WiFi networks", {}),
    # BLE
    ({"ble", "bluetooth", "advertise"},
     "comms_agent", "ble_scan",
     "Scan BLE neighbourhood", {"duration_sec": 3}),
    # GPS
    ({"gps", "location", "gnss", "position"},
     "comms_agent", "get_gps",
     "Get GPS fix", {}),
    # Cloud
    ({"cloud", "telemetry", "push", "upload"},
     "comms_agent", "cloud_push",
     "Push telemetry to cloud", {}),
    # Diagnostics
    ({"diagnose", "diagnostics", "health", "status"},
     "comms_agent", "diagnostics",
     "Run device diagnostics", {}),
    # AI optimisation
    ({"optimise", "optimize", "auto", "auto-tune"},
     "ai_agent", "auto_optimise",
     "Auto-optimise frequency & modulation", {}),
    # Interference
    ({"interference", "noise", "congestion"},
     "ai_agent", "detect_interference",
     "Detect RF interference", {}),
    # Anomaly
    ({"anomaly", "anomalies", "outlier"},
     "ai_agent", "anomaly_detect",
     "Run anomaly detection on telemetry", {}),
    # Recommendations
    ({"recommend", "suggestion", "advise"},
     "ai_agent", "recommend_config",
     "Generate configuration recommendations", {}),
    # Research / catch-all (checked last)
    ({"research", "analyse", "analyze", "explain", "what", "how", "why",
      "tell", "describe", "query", "ask", "show", "list"},
     "ai_agent", "research",
     "AI research / natural-language answer", {}),
]


def decompose_prompt(prompt: str) -> List[WorkTask]:
    """
    Map a natural-language *prompt* to a list of :class:`WorkTask` objects.

    Matches keywords case-insensitively; each task name is added at most once.
    A ``research`` task is always included so the user gets a natural-language
    response even when no other keywords matched.
    """
    lower = prompt.lower()
    matched: List[WorkTask] = []
    seen_names: Set[str] = set()

    for keywords, agent_type, task_name, description, params in _TASK_PATTERNS:
        if task_name in seen_names:
            continue
        if any(kw in lower for kw in keywords):
            extra: Dict[str, Any] = {}
            if agent_type == "ai_agent":
                extra = {"query": prompt}
            matched.append(WorkTask(
                task_id=str(uuid.uuid4())[:8],
                name=task_name,
                agent_type=agent_type,
                params={**params, **extra},
                description=description,
            ))
            seen_names.add(task_name)

    # Ensure at least one research task is always present
    if "research" not in seen_names:
        matched.append(WorkTask(
            task_id=str(uuid.uuid4())[:8],
            name="research",
            agent_type="ai_agent",
            params={"query": prompt},
            description="AI research / natural-language answer",
        ))

    return matched


# ---------------------------------------------------------------------------
# Short-key prompting system
# ---------------------------------------------------------------------------
# Each entry: key → (task_name, agent_type, description, params)
# Keys are intentionally mnemonic: first letter of the primary word, with
# two-character keys used when the initial would be ambiguous (fw, ft, bl).

SHORT_KEYS: Dict[str, tuple] = {
    # Frequency
    "f":  ("get_frequency",       "frequency_agent",  "Read current operating frequency",
           {}),
    "ft": ("fine_tune",           "frequency_agent",  "Fine-tune frequency for best RSSI",
           {"step_hz": 500_000, "iterations": 5}),
    # Modulation
    "m":  ("get_scheme",          "modulation_agent", "Get current modulation scheme",
           {}),
    # Firmware
    "fw": ("build",               "firmware_agent",   "Build firmware image",
           {"template": "base", "features": ["wifi", "ble"], "version": "auto"}),
    # Comms
    "w":  ("wifi_scan",           "comms_agent",      "Scan for WiFi networks",
           {}),
    "bl": ("ble_scan",            "comms_agent",      "Scan BLE neighbourhood",
           {"duration_sec": 3}),
    "g":  ("get_gps",             "comms_agent",      "Get GPS fix",
           {}),
    "c":  ("cloud_push",          "comms_agent",      "Push telemetry to cloud",
           {}),
    "d":  ("diagnostics",         "comms_agent",      "Run device diagnostics",
           {}),
    # AI
    "o":  ("auto_optimise",       "ai_agent",         "Auto-optimise frequency & modulation",
           {}),
    "i":  ("detect_interference", "ai_agent",         "Detect RF interference",
           {}),
    "a":  ("anomaly_detect",      "ai_agent",         "Run anomaly detection on telemetry",
           {}),
    "r":  ("recommend_config",    "ai_agent",         "Generate configuration recommendations",
           {}),
    "q?": ("research",            "ai_agent",         "AI research / natural-language answer",
           {}),
    # Full AI series (single / double / triple pass) — runs via CHAiMERA3sp
    "s":   ("full_series",        "ai_agent",         "Full AI analysis series (1 pass)",
            {"passes": 1}),
    "ss":  ("full_series",        "ai_agent",         "Full AI analysis series (double pass)",
            {"passes": 2}),
    "sss": ("full_series",        "ai_agent",         "Full AI analysis series (triple pass)",
            {"passes": 3}),
}

# Human-readable group ordering used by the help table
_KEY_GROUPS: List[tuple] = [
    ("Frequency",  ["f", "ft"]),
    ("Modulation", ["m"]),
    ("Firmware",   ["fw"]),
    ("Comms",      ["w", "bl", "g", "c", "d"]),
    ("AI",         ["o", "i", "a", "r"]),
    ("AI Series",  ["s", "ss", "sss"]),
]


def resolve_short_keys(line: str) -> Optional[List[WorkTask]]:
    """
    Try to interpret *line* as a space-separated sequence of short keys.

    Returns a list of :class:`WorkTask` objects when **every** whitespace-
    separated token in *line* is a valid key in :data:`SHORT_KEYS`.  Returns
    ``None`` when any token is unrecognised (the caller should fall back to
    natural-language matching via :func:`decompose_prompt`).

    Duplicate keys are silently de-duplicated; order is preserved.
    """
    tokens = line.lower().split()
    if not tokens:
        return None

    tasks: List[WorkTask] = []
    seen_names: Set[str] = set()

    for token in tokens:
        entry = SHORT_KEYS.get(token)
        if entry is None:
            return None   # unknown token → fall through to NL matching
        task_name, agent_type, description, params = entry
        if task_name in seen_names:
            continue      # de-duplicate within a single input line
        extra: Dict[str, Any] = {}
        if agent_type == "ai_agent":
            extra = {"query": line}
        tasks.append(WorkTask(
            task_id=str(uuid.uuid4())[:8],
            name=task_name,
            agent_type=agent_type,
            params={**params, **extra},
            description=description,
        ))
        seen_names.add(task_name)

    return tasks or None


# ---------------------------------------------------------------------------
# Deliberation
# ---------------------------------------------------------------------------

def deliberate(workers: List[Worker], tasks: List[WorkTask]) -> None:
    """
    Assign each task to the best available worker.

    Strategy:
      - Workers whose skill profile includes the task's ``agent_type`` are
        preferred candidates.
      - Among candidates, the one with the fewest already-claimed tasks is
        chosen (least-loaded assignment).
      - If no skilled worker exists every worker is eligible (any worker can
        help any task — this is the "open positions" mechanism).
    """
    load: Dict[str, int] = {w.name: 0 for w in workers}

    for task in tasks:
        skilled = [w for w in workers if task.agent_type in w.skills]
        candidates = skilled if skilled else workers
        chosen = min(candidates, key=lambda w: load[w.name])
        task.claimed_by = chosen.name
        task.status = TaskStatus.CLAIMED
        load[chosen.name] += 1


# ---------------------------------------------------------------------------
# Multi-Agent Session
# ---------------------------------------------------------------------------

class MultiAgentSession:
    """
    One interactive CLI session.

    Call :meth:`process` with a user prompt to run a full deliberation +
    execution cycle.  Workers that finish early steal remaining tasks from
    the shared queue.
    """

    def __init__(self, orchestrator: Any, config: Dict[str, Any]) -> None:
        self._orchestrator = orchestrator
        self._config = config
        self._workers: List[Worker] = self._build_workers()

    # ------------------------------------------------------------------
    # Worker construction
    # ------------------------------------------------------------------

    def _build_workers(self) -> List[Worker]:
        workers: List[Worker] = []

        try:
            from ai.chaimera3sp import CHAiMERA3sp
            chaimera_cfg = (
                self._config
                .get("ai_agent", {})
                .get("chaimera3sp", {})
            )
            router = CHAiMERA3sp(chaimera_cfg)
            for name in router.configured_providers:
                provider = router._providers[name]  # pylint: disable=protected-access
                workers.append(Worker(
                    name=name,
                    skills=SKILLS_REGISTRY.get(name, ["ai_agent"]),
                    provider_instance=provider,
                ))
                logger.debug("Registered worker: %s  skills=%s", name,
                             SKILLS_REGISTRY.get(name))
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug("Could not load CHAiMERA3sp workers: %s", exc)

        # The built-in worker is always present as a reliable fallback
        workers.append(Worker(
            name="builtin",
            skills=SKILLS_REGISTRY["builtin"],
            provider_instance=None,
        ))
        return workers

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def process(self, prompt: str) -> None:
        """Run a full prompt → deliberate → execute → summarise cycle.

        Input is first tested against the short-key table
        (:func:`resolve_short_keys`).  If every space-separated token is a
        valid key the corresponding tasks are queued directly.  Otherwise
        natural-language keyword matching (:func:`decompose_prompt`) is used.
        """
        tasks = resolve_short_keys(prompt) or decompose_prompt(prompt)
        print()
        self._print_skills_registry()
        self._print_deliberation(tasks)
        await self._execute(tasks)
        self._print_summary(tasks)

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _box(title: str, width: int = 58) -> str:
        return f"  ┌─ {title} {'─' * max(0, width - len(title) - 4)}┐"

    @staticmethod
    def _box_end(width: int = 58) -> str:
        return f"  └{'─' * (width - 1)}┘"

    def _print_skills_registry(self) -> None:
        print(self._box("MCP Skills Registry"))
        for w in self._workers:
            skills_str = ", ".join(w.skills)
            print(f"  │  [{w.name:10s}]  {skills_str}")
        print(self._box_end())
        print()

    def _print_deliberation(self, tasks: List[WorkTask]) -> None:
        print(self._box("Deliberation"))
        deliberate(self._workers, tasks)
        for task in tasks:
            print(f"  │  {task.claimed_by:10s}  ←→  [{task.agent_type}]  {task.description}")
        print(self._box_end())
        print()

    # ------------------------------------------------------------------
    # Concurrent execution with work-stealing
    # ------------------------------------------------------------------

    async def _execute(self, tasks: List[WorkTask]) -> None:
        """
        Launch one async loop per worker; each loop drains the shared queue.
        A worker that completes its own tasks immediately steals the next
        available task — this is the "open positions" mechanism.
        """
        queue: asyncio.Queue = asyncio.Queue()
        for task in tasks:
            await queue.put(task)

        print(self._box("Execution"))

        async def worker_loop(worker: Worker) -> None:
            while True:
                try:
                    task: WorkTask = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                is_primary = task.claimed_by == worker.name
                verb = "starting " if is_primary else "helping  "
                icon = "▶" if is_primary else "⟳"
                print(f"  │  {icon}  {worker.name:10s}  {verb}  [{task.agent_type}]  {task.description}")

                task.status = TaskStatus.RUNNING
                task.started_at = time.monotonic()
                task.claimed_by = worker.name   # track actual executor

                try:
                    task.result = await self._run_task(task, worker)
                    task.status = TaskStatus.DONE
                    elapsed = time.monotonic() - task.started_at
                    if is_primary:
                        worker.tasks_completed += 1
                    else:
                        worker.tasks_helped += 1
                    print(f"  │  ✓  {worker.name:10s}  done      [{task.agent_type}]  {task.description}  ({elapsed:.1f}s)")
                except Exception as exc:  # pylint: disable=broad-except
                    task.status = TaskStatus.FAILED
                    task.result = {"error": str(exc)}
                    elapsed = time.monotonic() - task.started_at
                    print(f"  │  ✗  {worker.name:10s}  failed    [{task.agent_type}]  {task.description}  ({elapsed:.1f}s)")
                    logger.debug("Task %s failed: %s", task.name, exc)

                queue.task_done()

        await asyncio.gather(*[worker_loop(w) for w in self._workers])
        print(self._box_end())
        print()

    # ------------------------------------------------------------------
    # Task dispatcher
    # ------------------------------------------------------------------

    async def _run_task(self, task: WorkTask, worker: Worker) -> Any:
        """
        Execute one task.

        Priority:
          1. Orchestrator agent (if the right agent type is registered).
          2. Worker's own AI provider (for ``research`` tasks).
          3. Built-in heuristic fallback.
        """
        # 1 — Orchestrator agent
        agents = self._orchestrator.get_agents_by_type(task.agent_type)
        if agents:
            try:
                task_id = await self._orchestrator.dispatch_task(
                    agents[0].agent_id,
                    task.name,
                    task.params,
                    device_id=None,
                )
                result = self._orchestrator.get_task_result(task_id)
                return result.get("result") if result else {}
            except Exception as exc:
                logger.debug("Orchestrator dispatch failed (%s): %s", task.name, exc)

        # 2 — Provider AI (research / NL tasks)
        if task.name == "research" and worker.provider_instance is not None:
            try:
                return await worker.provider_instance.query(
                    task.params.get("query", ""), {}
                )
            except Exception as exc:
                logger.debug("Provider %s research failed: %s", worker.name, exc)

        # 3 — Built-in heuristic
        if task.name == "research":
            return {
                "provider": "builtin",
                "response": (
                    "Heuristic answer for "
                    f"\"{task.params.get('query', '')}\": "
                    "For ESP32 multi-agent tasks, use 2.4 GHz WiFi for coverage, "
                    "5 GHz for throughput, 915 MHz LoRa for low-power long-range, "
                    "and BLE 5 for mesh topology.  Pair adaptive modulation with "
                    "real-time RSSI feedback for best performance."
                ),
            }

        return {"status": "ok", "agent_type": task.agent_type, "task": task.name}

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _print_summary(self, tasks: List[WorkTask]) -> None:
        done   = [t for t in tasks if t.status == TaskStatus.DONE]
        failed = [t for t in tasks if t.status == TaskStatus.FAILED]

        print(f"  Tasks: {len(done)}/{len(tasks)} succeeded"
              + (f",  {len(failed)} failed" if failed else ""))
        print()

        for task in done:
            result = task.result or {}
            if not isinstance(result, dict):
                continue
            response = (
                result.get("response")
                or result.get("result")
                or result.get("status")
            )
            if isinstance(response, str) and response:
                wrapped = textwrap.fill(
                    response, width=70,
                    initial_indent="    ", subsequent_indent="    ",
                )
                print(f"  [{task.description}]")
                print(wrapped)
                print()
            elif isinstance(response, dict) and response:
                print(f"  [{task.description}]  →  {response}")
                print()

        if failed:
            print("  Failed tasks:")
            for task in failed:
                err = (task.result.get("error", "unknown")
                       if isinstance(task.result, dict) else str(task.result))
                print(f"    • {task.description}: {err}")
            print()

        # Per-worker contribution
        active = [w for w in self._workers if w.tasks_completed + w.tasks_helped > 0]
        if active:
            print("  Worker contributions:")
            for w in active:
                total = w.tasks_completed + w.tasks_helped
                bar = "█" * w.tasks_completed + "░" * w.tasks_helped
                print(f"    {w.name:10s}  {bar}  primary={w.tasks_completed}  helped={w.tasks_helped}  total={total}")
            print()


# ---------------------------------------------------------------------------
# Interactive loop
# ---------------------------------------------------------------------------

async def run_multi_agent(
    orchestrator: Any,
    config: Dict[str, Any],
    prompt: Optional[str] = None,
) -> None:
    """
    Start the multi-agent CLI session.

    If *prompt* is provided the session runs a single non-interactive
    inference pass and exits.  Otherwise an interactive read-eval loop
    is started (the original behaviour).

    Args:
        orchestrator: The wired-up :class:`Orchestrator` instance.
        config:       Full application config dict.
        prompt:       Optional one-shot prompt for non-interactive inference.
    """
    from logging_system.logger import setup_logging  # noqa: F401  (already set up by main.py)

    session = MultiAgentSession(orchestrator, config)

    await orchestrator.start()

    # ------------------------------------------------------------------
    # Non-interactive: single inference pass then exit
    # ------------------------------------------------------------------
    if prompt is not None:
        await session.process(prompt)
        await orchestrator.stop()
        return

    # ------------------------------------------------------------------
    # Interactive loop
    # ------------------------------------------------------------------
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║        Multi-Agent CLI  —  ESP32 Orchestration       ║")
    print("  ║                                                      ║")
    print("  ║  Workers   : " + f"{len(session._workers)}" + " active" + " " * (38 - len(str(len(session._workers)))) + "║")  # noqa: E501
    print("  ║  Type '?' for short keys  •  'exit' to quit         ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()

    while True:
        try:
            # Run input() in a thread so the event loop stays unblocked
            loop = asyncio.get_event_loop()
            line = await loop.run_in_executor(None, lambda: input("  ▸ ").strip())
        except (KeyboardInterrupt, EOFError):
            break

        if not line:
            continue
        if line.lower() in {"exit", "quit", "q"}:
            break
        if line.lower() in {"help", "?"}:
            _print_help()
            continue
        if line.lower() == "workers":
            _print_workers(session._workers)
            continue

        await session.process(line)

    await orchestrator.stop()
    print("\n  Goodbye.\n")


def _print_help() -> None:
    """Print the short-key reference table and natural-language examples."""
    W = 58   # box inner width

    def _box(title: str) -> str:
        return f"  ┌─ {title} {'─' * max(0, W - len(title) - 4)}┐"

    def _box_end() -> str:
        return f"  └{'─' * (W - 1)}┘"

    def _row(key: str, desc: str) -> None:
        line = f"  │  {key:<4s}  {desc}"
        pad  = W - len(line) + 2   # +2 for leading "  "
        print(line + " " * max(0, pad) + "│")

    def _sep() -> None:
        print(f"  │{'─' * (W - 1)}│")

    print()
    print(_box("Short-Key Reference"))
    for group_name, keys in _KEY_GROUPS:
        _sep()
        print(f"  │  {group_name:<{W - 3}}│")
        for key in keys:
            entry = SHORT_KEYS.get(key)
            if entry:
                _row(key, entry[2])
    print(_box_end())

    print()
    print("  Combine keys freely (space-separated):")
    print("    ▸ f m          — frequency + modulation")
    print("    ▸ w bl d       — wifi + BLE + diagnostics")
    print("    ▸ f ft m o     — freq + fine-tune + modulation + optimise")
    print("    ▸ i a r        — interference + anomaly + recommendations")
    print("    ▸ s            — full AI series (1 pass via CHAiMERA3sp)")
    print("    ▸ ss           — full AI series, double pass")
    print("    ▸ sss          — full AI series, triple pass")
    print()
    print("  Natural-language prompts are also accepted:")
    print("    ▸ research best modulation for long-range ESP32")
    print("    ▸ scan wifi and check diagnostics")
    print("    ▸ optimise frequency and detect interference")
    print()
    print("  Session commands:")
    print("    workers  — list active workers and their skills")
    print("    ?        — show this key reference")
    print("    exit     — quit the CLI")
    print()


def _print_workers(workers: List[Worker]) -> None:
    print()
    print("  Active workers:")
    for w in workers:
        print(f"    {w.name:10s}  skills: {', '.join(w.skills)}")
    print()


# ---------------------------------------------------------------------------
# Direct entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point when run as ``python -m cli.multi_agent_cli``."""
    import argparse
    from logging_system.logger import setup_logging

    parser = argparse.ArgumentParser(
        description="Multi-Agent CLI — collaborative prompt execution"
    )
    parser.add_argument("--config", default="config/default.yaml",
                        help="Path to YAML config (default: config/default.yaml)")
    parser.add_argument("--log-level", default="WARNING",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument(
        "--prompt", "-p", default=None, metavar="PROMPT",
        help=(
            "Run a single non-interactive inference pass with PROMPT and exit. "
            "Omit to start the interactive session."
        ),
    )
    args = parser.parse_args()

    setup_logging(level=args.log_level)

    # Lazy import to avoid circular deps
    import sys
    sys.path.insert(0, ".")
    from main import load_config, build_orchestrator  # type: ignore[import]

    config = load_config(args.config)
    orchestrator = build_orchestrator(config)
    asyncio.run(run_multi_agent(orchestrator, config, prompt=args.prompt))


if __name__ == "__main__":
    main()
