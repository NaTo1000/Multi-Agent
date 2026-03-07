# Build & Test Guide

This document covers how to build and test the **C# components** of the Multi-Agent project using either Visual Studio 2022+ or the `dotnet` CLI.

---

## Prerequisites

| Tool | Minimum version |
|---|---|
| [.NET SDK](https://dotnet.microsoft.com/download) | 8.0 |
| [Visual Studio 2022](https://visualstudio.microsoft.com/) | 17.x (Community or higher) |
| *or* VS Code with C# Dev Kit | latest |

---

## Project Structure

```
MultiAgent.sln
├── src/
│   ├── MultiAgent.Core/    # Core orchestration library (net8.0)
│   └── MultiAgent.App/     # CLI host / entry point (net8.0)
└── tests/
    └── MultiAgent.Tests/   # xUnit unit-test project (net8.0)
```

---

## Visual Studio 2022+

1. **Open** `MultiAgent.sln` in Visual Studio 2022 or later.
2. **Select configuration** — `Debug` or `Release` — from the toolbar dropdown.
3. **Restore & build** — Visual Studio restores NuGet packages automatically on open.  
   Press **Ctrl+Shift+B** (or **Build → Build Solution**) to compile all projects.
4. **Run** — Set `MultiAgent.App` as the startup project and press **F5** (or **Ctrl+F5**).
5. **Test** — Open **Test → Test Explorer** and click **Run All Tests**.  
   Test results appear in the Test Explorer pane with pass/fail indicators.

> **Tip:** The `.runsettings` file at the repository root is picked up automatically by
> Visual Studio's Test Explorer for coverage and timeout configuration.

---

## dotnet CLI

### Restore dependencies

```bash
dotnet restore MultiAgent.sln
```

### Build (Debug)

```bash
dotnet build MultiAgent.sln
```

### Build (Release)

```bash
dotnet build MultiAgent.sln -c Release
```

### Run the CLI app

```bash
dotnet run --project src/MultiAgent.App
```

### Run all tests

```bash
dotnet test MultiAgent.sln
```

### Run tests with detailed output

```bash
dotnet test MultiAgent.sln --logger "console;verbosity=detailed"
```

### Run tests with code coverage (Coverlet)

```bash
dotnet test MultiAgent.sln --collect:"XPlat Code Coverage"
```

---

## Continuous Integration

The solution is validated on every push via the CI workflow.  
Required checks: `dotnet build MultiAgent.sln -c Release` and `dotnet test MultiAgent.sln`.
