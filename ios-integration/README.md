# iOS Integration — Multi-Agent ESP32 Orchestration System

A production-quality Swift Package Manager library providing an iOS (and macOS) client for the Multi-Agent ESP32 orchestration platform, with first-class support for **Flipper Zero** BLE management, **WiFi Pineapple** recon, and **Momentum / iNFINITE_FLIPZ_ASSET_PACKZ** over-the-air asset delivery.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        iOS Application                          │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌─────────────┐   │
│  │Dashboard │  │ Devices  │  │  Flipper  │  │  Pineapple  │   │
│  │   View   │  │   View   │  │   View    │  │    View     │   │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘  └──────┬──────┘   │
│       │              │              │                │          │
│  ┌────▼─────┐  ┌────▼─────┐  ┌─────▼─────┐  ┌──────▼──────┐   │
│  │Dashboard │  │ Device   │  │  Flipper  │  │  Pineapple  │   │
│  │ViewModel │  │  List VM │  │ ViewModel │  │  ViewModel  │   │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘  └──────┬──────┘   │
└───────┼──────────────┼──────────────┼────────────────┼──────────┘
        │              │              │                │
        ▼              ▼              │                │
┌────────────────────────────────┐   │                │
│   FastAPI Backend (port 8000)  │   │                │
│                                │   │                │
│  REST   /api/v1/               │   │                │
│  ├── /status                   │   │                │
│  ├── /devices  (CRUD)          │   │                │
│  ├── /agents                   │   │                │
│  ├── /tasks                    │   │                │
│  ├── /firmware/builds          │   │                │
│  └── /firmware/flash           │   │                │
│                                │   │                │
│  WS   /ws/telemetry  ◄─────────┘   │                │
└────────────┬───────────────────┘   │                │
             │                       │                │
             ▼                       ▼                ▼
┌─────────────────────┐  ┌──────────────────┐  ┌──────────────┐
│   ESP32 Agent Fleet │  │  Flipper Zero    │  │ WiFi         │
│                     │  │  (BLE, RPC,      │  │ Pineapple    │
│  ● Node Alpha       │  │   DFU, Files)    │  │ (REST API,   │
│  ● Node Beta        │  │                  │  │  Recon,      │
│  ● Node Gamma       │  │  FlipperBridge   │  │  Modules)    │
│  ● …                │  │  module          │  │  PineappleKit│
└─────────────────────┘  └──────────────────┘  └──────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │  Momentum CDN           │
                    │  up.momentum-fw.dev     │
                    │  iNFINITE_FLIPZ_ASSET   │
                    │  _PACKZ                 │
                    │                         │
                    │  AssetPackManager       │
                    │  module                 │
                    └─────────────────────────┘
```

---

## Swift Package Modules

| Module | Description |
|--------|-------------|
| **IOSIntegration** | Main app module — SwiftUI views, view-models, REST/WebSocket services, models |
| **FlipperBridge** | CoreBluetooth manager for Flipper Zero; RPC/protobuf codec; file operations; DFU flash |
| **PineappleKit** | WiFi Pineapple REST client, recon parsing, DuckyScript payloads, Flipper↔Pineapple sync |
| **AssetPackManager** | Momentum CDN client, `meta.json` parser, pack install/registry |

---

## API Endpoint Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/status` | System health check |
| GET | `/api/v1/devices` | List all ESP32 devices |
| POST | `/api/v1/devices` | Register a new device |
| GET | `/api/v1/devices/{id}` | Get device details |
| PUT | `/api/v1/devices/{id}` | Update device metadata |
| DELETE | `/api/v1/devices/{id}` | Deregister a device |
| GET | `/api/v1/devices/{id}/telemetry` | Historical telemetry |
| GET | `/api/v1/agents` | List orchestrator agents |
| GET | `/api/v1/tasks` | List tasks |
| POST | `/api/v1/tasks` | Dispatch a task |
| GET | `/api/v1/tasks/{id}` | Poll task status |
| DELETE | `/api/v1/tasks/{id}` | Cancel a task |
| GET | `/api/v1/firmware/builds` | List OTA firmware builds |
| POST | `/api/v1/firmware/flash` | Trigger OTA flash |
| **WS** | `/ws/telemetry` | Live telemetry stream (JSON frames) |

---

## Flipper Zero BLE Protocol

| UUID | Role |
|------|------|
| `19ED82AE-ED21-4C9D-4145-228E62FE0000` | Primary RPC Service |
| `19ED82AE-ED21-4C9D-4145-228E62FE0001` | TX Characteristic (phone → Flipper) |
| `19ED82AE-ED21-4C9D-4145-228E62FE0002` | RX Characteristic (Flipper → phone, notify) |
| `19ED82AE-ED21-4C9D-4145-228E62FE0003` | Flow Control |
| `180F` | Battery Service (standard BLE) |
| `2A19` | Battery Level |

### RPC Frame Format

```
[4 bytes LE length] [4 bytes LE command_id] [1 byte flags] [1 byte command_type] [payload]
```

- `flags`: bit 0 = `has_next` (multi-chunk frame)
- `command_type`: see `FlipperCommandType` enum

### DFU (Nordic Legacy DFU)

Service: `00001530-1212-EFDE-1523-785FEABCD123`

1. Send `StartDFU` (0x01) with image type
2. Send firmware size packet (4+4+4 bytes: SD+BL+APP)
3. Request packet receipt notifications every 10 packets
4. Send `ReceiveFirmware` (0x03)
5. Stream binary in 20-byte chunks
6. Send `ValidateFirmware` (0x04)
7. Send `ActivateAndReset` (0x05)

---

## Asset Packs (iNFINITE_FLIPZ_ASSET_PACKZ / Momentum)

Pack index: `https://up.momentum-fw.dev/asset-packs/index.json`

Each pack contains a `meta.json`:

```json
{
  "name": "PackName",
  "author": "author_handle",
  "meta_version": 2,
  "animations": [
    {
      "name": "AnimName",
      "width": 128,
      "height": 64,
      "frame_count": 30,
      "frame_rate": 15,
      "passive_frames": [0, 1, 2],
      "active_frames": [3, 4, 5]
    }
  ]
}
```

Frames are stored as `.bm` files — 1-bit-per-pixel bitmaps, MSB first, rows padded to full bytes.  
`BMFrameDecoder` converts them to `UIImage` for preview in `AssetPackBrowserView`.

---

## Build & Test

### Requirements

- Xcode 15+ / Swift 5.9+
- iOS 17 SDK (or macOS 14 for macOS targets)
- A running Multi-Agent FastAPI backend (default: `http://localhost:8000`)

### Build

```bash
cd ios-integration
swift build
```

### Test

```bash
swift test
```

### Run specific test suite

```bash
swift test --filter FlipperBridgeTests
swift test --filter PineappleKitTests
swift test --filter IOSIntegrationTests
```

---

## Environment Variable Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MULTI_AGENT_BASE_URL` | `http://localhost:8000` | FastAPI backend base URL |
| `MULTI_AGENT_WS_URL` | `ws://localhost:8000/ws/telemetry` | WebSocket telemetry URL |
| `PINEAPPLE_HOST` | `172.16.42.1` | WiFi Pineapple IP or hostname |
| `REQUEST_TIMEOUT` | `30` | URLSession timeout in seconds |
| `RETRY_MAX_ATTEMPTS` | `3` | Max retries for failed API requests |
| `RETRY_BASE_DELAY` | `1.0` | Base delay (seconds) for exponential backoff |

Override at launch in Xcode via **Product → Scheme → Edit Scheme → Arguments → Environment Variables**, or in CI via shell environment before running tests.

---

## In-App Settings

All configuration values can also be overridden at runtime via the **Settings** tab, which persists values to `UserDefaults` and sensitive credentials (API token, Pineapple API key) to the iOS **Keychain**.

---

## Security Notes

- API tokens are stored in the Keychain with `.afterFirstUnlock` accessibility — they survive device restarts but not device data erasure.
- The Pineapple API key is stored with the same policy.
- All backend communication uses Bearer token authentication; set your token in Settings before first use.
- SHA-256 checksums are validated on all firmware downloads before flashing.
