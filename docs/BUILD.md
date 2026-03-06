# Build & Run – MultiAgent C# Solution

## Prerequisites

| Tool | Minimum version |
|---|---|
| [.NET SDK](https://dotnet.microsoft.com/download) | 8.0 |

```bash
dotnet --version  # should print 8.x.x or later
```

---

## Repository layout

```
MultiAgent.slnx              Solution file (all projects)
src/
  MultiAgent.Core/           Core library – domain models, interfaces, engine
  MultiAgent.App/            CLI / host entry point
tests/
  MultiAgent.Tests/          xUnit unit tests
LOG.md                       Staged build progress log
docs/BUILD.md                This file
```

---

## Build

```bash
# From repo root
dotnet build MultiAgent.slnx -c Release
```

---

## Run tests

```bash
dotnet test MultiAgent.slnx -c Release
```

All tests are in `tests/MultiAgent.Tests/`.  They cover:

- `SequencingEngineTests` – priority queue, concurrency limits, drain
- `EwmaFaultDetectorTests` – EWMA anomaly detection (stable series, spikes, alpha sensitivity)
- `RollbackManagerTests` – fire-and-forget rollback registration and execution
- `FaultTolerantSequencerTests` – end-to-end fault-triggered rollback
- `OrchestratorTests` – device/agent management, task dispatch, broadcast, event system

---

## Run the CLI

```bash
# Demo mode (exercises all subsystems)
dotnet run --project src/MultiAgent.App -- demo

# Status mode
dotnet run --project src/MultiAgent.App -- status
```

---

## Project structure detail

### `MultiAgent.Core`

| Folder | Purpose |
|---|---|
| `Models/` | Enums (`DeviceStatus`, `AgentStatus`, `DeviceCapability`) and records (`Device`, `TaskResult`) |
| `Interfaces/` | `IAgent`, `IOrchestrator`, `ISequencingEngine`, `IFaultDetector`, `IRollbackManager` |
| `Agents/` | `AgentBase` (abstract) + concrete: `FrequencyAgent`, `ModulationAgent`, `FirmwareAgent`, `CommsAgent`, `AiAgent` |
| `Orchestration/` | `Orchestrator` (central coordinator) + `SequencingEngine` (priority task queue) |
| `FaultTolerance/` | `EwmaFaultDetector`, `RollbackManager`, `FaultTolerantSequencer` |
| `FlipperZero/` | `FlipperZeroShim` – platform stub for Flipper Zero hardware integration |
| `Interop/` | `IosInterop` – iOS/Swift interop façade + `StubIosInterop` |

### `MultiAgent.App`

Single-file top-level program (`Program.cs`) wires DI, creates the orchestrator,
and exposes `demo` and `status` CLI modes.

### `MultiAgent.Tests`

xUnit 2 test project.  No test infrastructure setup required — `dotnet test` is sufficient.

---

## Adding a new agent

1. Create `src/MultiAgent.Core/Agents/MyAgent.cs` extending `AgentBase`.
2. Override `ExecuteCoreAsync` and handle your task names with a `switch` expression.
3. Register the agent in `Program.cs` (or via DI in your host).
4. Add unit tests in `tests/MultiAgent.Tests/`.

---

## Extending Flipper Zero / iOS interop

- **Flipper Zero**: replace stub methods in `FlipperZeroShim` with real serial/USB protocol calls.
- **iOS**: implement `IIosInterop` and call `IosInteropFacade.Register(new MyRealImpl())` at startup.
