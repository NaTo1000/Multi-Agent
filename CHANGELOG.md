# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added — Visual Studio readiness (benchmarking/failsafe branch polish)

- **`MultiAgent.sln`** — top-level SDK-style solution targeting .NET 8,
  referencing all three projects with Debug and Release configurations.
- **`src/MultiAgent.Core`** — portable class library (`net8.0`) exposing
  `Orchestrator`, `IAgent`, and `AgentResult` as the public API surface.
- **`src/MultiAgent.App`** — console host / CLI entry point (`net8.0`)
  referencing `MultiAgent.Core`.
- **`tests/MultiAgent.Tests`** — xUnit test project (`net8.0`) with
  5 unit tests covering `Orchestrator` registration and dispatch logic;
  references `MultiAgent.Core`.
- **`.editorconfig`** — repository-wide code-style rules aligned with Visual
  Studio 2022 defaults: nullable enabled, naming conventions, formatting,
  and Roslyn analyser severities.
- **`.runsettings`** — test-run configuration for Visual Studio Test Explorer
  and `dotnet test`: timeout, code-coverage collection, and console logger.
- **`docs/BUILD.md`** — concise Visual Studio 2022 and CLI instructions
  (`dotnet restore`, `dotnet build`, `dotnet test`).

### Verified

- `dotnet build MultiAgent.sln -c Release` → **0 warnings, 0 errors**.
- `dotnet test MultiAgent.sln` → **5 passed, 0 failed**.

---

## Earlier history

See `git log` for the full project history prior to the VS-readiness step.
