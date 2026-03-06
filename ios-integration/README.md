# iOS Integration

Swift-based iOS integration module for the **Multi-Agent ESP32 Orchestration System**.

## Overview

This module provides a native Swift iOS application that serves as a companion to the Multi-Agent back-end. It is built with **SwiftUI** and managed via **Swift Package Manager (SPM)**, making it straightforward to embed as a library or extend into a full-featured standalone app.

## Directory Structure

```
ios-integration/
├── Package.swift                          # SPM manifest (iOS 16+)
├── Sources/
│   └── IOSIntegration/
│       ├── App.swift                      # @main SwiftUI entry point
│       └── ContentView.swift              # Root view
├── Tests/
│   └── IOSIntegrationTests/
│       └── IOSIntegrationTests.swift      # Unit tests
└── README.md                              # This file
```

## Requirements

| Tool | Minimum version |
|------|----------------|
| Xcode | 15+ |
| Swift | 5.9+ |
| iOS deployment target | 16.0+ |

## Getting Started

### Open in Xcode

```bash
cd ios-integration
open Package.swift
```

Xcode will resolve the package and you can run the app on a simulator or device immediately.

### Build from the command line (macOS only)

```bash
cd ios-integration
swift build
```

### Run tests

```bash
cd ios-integration
swift test
```

## Integration with the Orchestration Back-end

The iOS app communicates with the FastAPI server (`main.py`) over REST and WebSocket:

| Transport | Endpoint |
|-----------|----------|
| REST | `http://<host>:8000/api/v1/` |
| WebSocket | `ws://<host>:8000/ws/telemetry` |

Add `URLSession`-based service classes under `Sources/IOSIntegration/Services/` as the feature set grows.

## Future Expansion

Suggested next steps:

- `Services/OrchestratorService.swift` — REST client for the FastAPI back-end
- `Services/TelemetrySocket.swift` — real-time WebSocket stream
- `Views/DeviceListView.swift` — ESP32 device management
- `Views/FrequencyView.swift` — frequency scan and lock UI
- `Views/FirmwareView.swift` — OTA firmware build and flash
- `Models/` — Codable data models mirroring the API responses
