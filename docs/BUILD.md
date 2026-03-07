# Building with Visual Studio

This document explains how to open, build, and test the **Multi-Agent** .NET
solution in Visual Studio 2022 (or later) and from the command line.

---

## Prerequisites

| Tool | Minimum version |
|---|---|
| [.NET SDK](https://dot.net/download) | 8.0 |
| [Visual Studio 2022](https://visualstudio.microsoft.com/) | 17.8+ *(optional)* |

Verify your SDK version:

```bash
dotnet --version
# expected: 8.0.x or later
```

---

## Opening in Visual Studio 2022

1. Clone or pull the repository.
2. **File → Open → Project/Solution** and select **`MultiAgent.sln`** at the
   repository root.
3. Visual Studio will automatically detect the `.editorconfig` and
   `.runsettings` files and apply code-style and analyser settings.
4. **Build → Build Solution** (or <kbd>Ctrl+Shift+B</kbd>) to restore NuGet
   packages and compile.

---

## Command-line workflow

All commands should be run from the repository root.

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

### Run the host application

```bash
dotnet run --project src/MultiAgent.App
```

### Run unit / integration tests

```bash
dotnet test MultiAgent.sln
```

With code coverage and the `.runsettings` file:

```bash
dotnet test MultiAgent.sln --settings .runsettings
```

---

## Solution structure

```
MultiAgent.sln
├── src/
│   ├── MultiAgent.Core/      # Core orchestration library (net8.0)
│   └── MultiAgent.App/       # Console host / CLI entry point (net8.0)
└── tests/
    └── MultiAgent.Tests/     # xUnit unit & integration tests (net8.0)
```

---

## Code style

The repository ships an `.editorconfig` that enforces the coding conventions
used across all C# projects.  Roslyn analysers are enabled and nullable
reference types are required.  Visual Studio 2022 picks these up automatically;
Rider and VS Code with the C# extension also honour the file.

---

## Continuous integration

The solution is verified on every push via `dotnet build` and `dotnet test`.
See the workflow files in `.github/workflows/` for details.
