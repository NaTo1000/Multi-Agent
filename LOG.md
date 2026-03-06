# MultiAgent C# Rewrite – Build-Stage Log

This document records every stage of the full C# rewrite, including decisions made,
optimisation notes, and what was completed before the next stage began.

---

## Stage 1 – Project Scaffolding

**Date:** 2026-03-06
**Branch:** `copilot/full-csharp-rewrite`

### What was done
- Created `MultiAgent.slnx` (SDK-style solution) at the repo root.
- Scaffolded three projects targeting **net8.0**:
  - `src/MultiAgent.Core` – class library for all domain logic.
  - `src/MultiAgent.App` – console application (CLI entry point).
  - `tests/MultiAgent.Tests` – xUnit test project.
- Wired project references: `App → Core`, `Tests → Core`.
- Added `Microsoft.Extensions.Logging` (8.0.1) and `Microsoft.Extensions.Logging.Console`
  (8.0.1) to `Core` and `App`; `Microsoft.Extensions.Logging.Abstractions` (8.0.2) to `Tests`.
- Advisory-DB scan: **no vulnerabilities** found in any added package.

### Decisions
- Used `net8.0` (LTS, current minimum) rather than `net9.0` for maximum CI compatibility.
- Used `.slnx` (the SDK-style XML solution format introduced in .NET 10 tooling) rather than
  the legacy `.sln` text format — `dotnet new sln` now defaults to `.slnx`.
- Kept all domain logic in `MultiAgent.Core` so the `App` project is purely a thin host.

### Next steps → Stage 2

---

## Stage 2 – Core Domain Models & Interfaces

**Date:** 2026-03-06

### What was done
- Created `Models/` directory with:
  - `DeviceStatus` enum (`Unknown`, `Online`, `Offline`, `Updating`, `Error`)
  - `DeviceCapability` `[Flags]` enum (`Wifi`, `Ble`, `Gps`, `Gnss`, `Lora`)
  - `AgentStatus` enum (`Idle`, `Running`, `Busy`, `Error`, `Stopped`)
  - `Device` record — represents a physical ESP32 module with telemetry helpers
  - `TaskResult` record — immutable snapshot of task outcome
- Created `Interfaces/` directory with:
  - `IAgent` – agent lifecycle + task execution contract
  - `IOrchestrator` – device/agent management + task dispatch + event contract
  - `ISequencingEngine` – priority queue contract
  - `IFaultDetector` / `IRollbackManager` – fault-tolerance contracts
- Created `OrchestratorEventArgs` as a typed event payload.

### Decisions
- Used C# 12 primary constructors and collection literals (`[]`) for concise record syntax.
- `DeviceCapability` uses `[Flags]` so multiple capabilities can be combined with `|`.
- `TaskResult` is a `record` (immutable) to match the Python `dict` snapshot semantics.

### Next steps → Stage 3

---

## Stage 3 – Agents & Agent Base

**Date:** 2026-03-06

### What was done
- Created `Agents/AgentBase.cs` — abstract base with:
  - Thread-safe metrics via `Interlocked` counters.
  - `ExecuteAsync` wraps `ExecuteCoreAsync` with status tracking and error capture.
  - `GetMetrics()` returns a plain `Dictionary<string, object>` snapshot.
- Created five concrete agents (all sealed):
  - `FrequencyAgent` – scan, lock, fleet sync
  - `ModulationAgent` – list/set modes, adaptive selection
  - `FirmwareAgent` – build, OTA flash
  - `CommsAgent` – cloud push, BLE advertise, ping
  - `AiAgent` – adaptive optimise, research query

### Decisions
- Agents use `switch` expressions for task dispatch — exhaustive and compile-checked.
- `sealed` on all concrete agents prevents accidental inheritance and enables JIT devirt.
- Logging injected via `ILogger<T>` so it participates in the standard DI pipeline.

### Next steps → Stage 4

---

## Stage 4 – Sequencing / Coordination Engine

**Date:** 2026-03-06

### What was done
- Created `Orchestration/Orchestrator.cs`:
  - `ConcurrentDictionary` for thread-safe device/agent/result stores.
  - `DispatchTaskAsync` stores `TaskResult` (success and failure paths).
  - `BroadcastTaskAsync` fans out to all agents of a given type with `Task.WhenAll`.
  - `EventHandler<OrchestratorEventArgs>` for typed event subscriptions.
  - Background health-check loop via `Task.Run` with `CancellationToken`.
- Created `Orchestration/SequencingEngine.cs` (`ISequencingEngine`):
  - In-memory priority-sorted list protected by a `lock`.
  - `SemaphoreSlim` limits concurrency to `maxConcurrent`.
  - `RunNextAsync` pops and runs the highest-priority item.
  - `RunAllAsync` drains the queue in priority-ordered batches.

### Decisions
- Priority-sorted list (`List<QueuedWork>` with `Sort`) preferred over a `PriorityQueue`
  because it lets us inspect and clear the queue easily; for typical queue depths (< 1000)
  the O(n log n) re-sort cost is negligible.
- Health-check loop uses `Task.Run` (fire-and-forget background task) and does not `await`
  it so it never blocks `StartAsync`.

### Next steps → Stage 5

---

## Stage 5 – Fault Detection & Non-Blocking Rollback

**Date:** 2026-03-06

### What was done
- Created `FaultTolerance/EwmaFaultDetector.cs`:
  - EWMA variance tracking with configurable `alpha` (smoothing) and `threshold` (σ multiplier).
  - **Key optimisation**: anomaly check uses the **prior variance** (before the current sample
    updates it), preventing the spike itself from inflating the variance and suppressing
    detection in the same step.
  - **Zero-variance fallback**: when prior stdDev = 0 (constant baseline), falls back to a
    relative check (`|deviation| / |ewma| > 0.5`) to catch clear outliers without false
    positives on normal noise.
  - `Reset()` clears all state for reuse.
- Created `FaultTolerance/RollbackManager.cs`:
  - Rollbacks are **fire-and-forget** (`Task.Run` + `_ = ...`) — the caller is never blocked,
    matching the Python `asyncio.ensure_future` semantics.
  - Insertion-order list tracked separately so `TriggerAllRollbacks` can replay in LIFO order.
  - Concurrent overwrite via `ConcurrentDictionary` allows registering a new rollback for an
    existing operation ID.
- Created `FaultTolerance/FaultTolerantSequencer.cs`:
  - Façade combining detector + rollback manager + sequencing engine.
  - `Enqueue` checks the health metric; if a fault is detected, triggers all rollbacks before
    adding the new work item.

### Decisions
- Non-blocking rollback is implemented as `Task.Run` + discard (`_ =`) rather than
  `Task.Factory.StartNew` — simpler, uses the default scheduler, and avoids capturing context.
- LIFO rollback order: added before the affected operation; matches the "undo in reverse"
  intuition for stack-like operations.

### Optimisation notes
- EWMA α = 0.3 (default): trades off responsiveness vs. noise sensitivity. Increase for faster
  reaction to trends; decrease for more stable baselines.
- σ threshold = 3.0 (default): equivalent to a 99.7 % confidence interval under Gaussian
  noise. Reduce for more sensitive fault detection.

### Next steps → Stage 6

---

## Stage 6 – Flipper Zero Shim & iOS Interop Stubs

**Date:** 2026-03-06

### What was done
- Created `FlipperZero/FlipperZeroShim.cs`:
  - Stub methods for: `ConnectAsync`, `DisconnectAsync`, `CaptureSubGhzAsync`,
    `TransmitSubGhzAsync`, `ReadNfcAsync`, `InfraredReplayAsync`.
  - All methods return empty/success payloads and log their invocations.
  - Replace with real serial/USB protocol code when running on a platform with
    Flipper Zero access.
- Created `Interop/IosInterop.cs`:
  - `IIosInterop` interface defining Bluetooth permission, location permission,
    current-location query, and BLE device scan.
  - `StubIosInterop` returns safe defaults (permission granted, no location, empty scan).
  - `IosInteropFacade` static façade with `Register()` injection point — avoids polluting
    the DI container with platform-specific types.

### Decisions
- Flipper Zero integration is a shim only — the device requires a proprietary serial
  protocol and is platform-specific (Linux/macOS/Windows USB). The shim records intent
  so integration can be dropped in without restructuring the call sites.
- iOS interop uses a static façade rather than constructor injection to match the pattern
  used by Xamarin.iOS / .NET MAUI platform services.

### Next steps → Stage 7

---

## Stage 7 – CLI Host Entry Point

**Date:** 2026-03-06

### What was done
- Created `src/MultiAgent.App/Program.cs` (top-level statements):
  - DI container with `Microsoft.Extensions.DependencyInjection` + console logging.
  - `demo` mode: exercises all subsystems sequentially and prints output.
  - `status` mode: starts the orchestrator and prints agent status table.
  - Unknown mode → error message + `Environment.Exit(1)`.

### Decisions
- Top-level statements (C# 9+) keep the entry point concise without a `Main` method.
- `ILoggerFactory` is resolved from the DI container rather than using `NullLoggerFactory`
  so the CLI always has real console logging without extra configuration.

### Next steps → Stage 8

---

## Stage 8 – Unit Tests

**Date:** 2026-03-06

### What was done
Added 30 xUnit tests across five test classes:

| Class | Tests | Focus |
|---|---|---|
| `SequencingEngineTests` | 6 | Priority ordering, concurrency limits, drain, count |
| `EwmaFaultDetectorTests` | 5 | First sample, stable series, spikes, alpha sensitivity, reset |
| `RollbackManagerTests` | 4 | Fire-and-forget execution, all-rollback, unknown id, overwrite |
| `FaultTolerantSequencerTests` | 3 | Normal flow, fault-triggered rollback, pending count |
| `OrchestratorTests` | 12 | Device/agent CRUD, dispatch, broadcast, events |

All 30 tests pass.  Run with:

```bash
dotnet test MultiAgent.slnx -c Release
```

### Decisions
- Used `NullLogger<T>.Instance` throughout tests — eliminates log-output noise and avoids
  ILoggerFactory DI setup in each test class.
- LIFO ordering test checks *presence* of all rollbacks rather than strict completion order,
  because the rollbacks run concurrently (fire-and-forget) and completion order is
  non-deterministic.
- `FaultTolerantSequencerTests.FaultMetric_TriggersRollbackBeforeEnqueue` uses a
  `Task.Delay(300)` after triggering rollbacks to allow fire-and-forget tasks to finish
  before asserting — consistent with the `RollbackManagerTests` approach.

### Next steps → Done

---

## Summary

All eight stages have been completed:

- [x] Project scaffolding (solution + three projects)
- [x] Core domain models & interfaces
- [x] Agent base + 5 concrete agents
- [x] Sequencing / coordination engine
- [x] Fault detection & non-blocking rollback
- [x] Flipper Zero shim (platform placeholder)
- [x] iOS/Swift interop stubs
- [x] CLI host entry point
- [x] 30 unit tests (all passing)
- [x] `docs/BUILD.md` with build/run instructions
