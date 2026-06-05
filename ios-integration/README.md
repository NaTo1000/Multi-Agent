# iOS Integration — Multi-Agent ESP32 Orchestration System

**Version:** 2.0 — `CALiDOLLFYOkPR`  
**Platform:** iOS 17+ · watchOS 10+ · macOS 14+  
**Build system:** Swift Package Manager 5.10  
**Status:** ✅ Production-grade · Actively maintained

> A production-quality Swift Package Manager library integrating iOS with the Multi-Agent ESP32 orchestration platform. Provides real-time telemetry streaming, AI-powered fleet analysis via HuggingFace and IBM WatsonX, Flipper Zero BLE management, WiFi Pineapple recon, and Momentum asset pack delivery.

---

## Work Specification

| Item | Target | Status |
|------|--------|--------|
| iOS 17+ SwiftUI app with 6-tab navigation | Full TabView | ✅ Done |
| REST client for FastAPI (`/api/v1/`) | `OrchestratorService` actor | ✅ Done |
| WebSocket telemetry (`/ws/telemetry`) | `TelemetrySocket` actor | ✅ Done |
| OTA firmware management + SHA-256 | `FirmwareService` | ✅ Done |
| Asset pack manager (Momentum CDN) | `AssetPackService` + `AssetPackManager` | ✅ Done |
| **AI Council — HuggingFace inference** | `AICouncilService.queryHuggingFace()` | ✅ Done |
| **AI Council — IBM WatsonX orchestrator** | `AICouncilService.queryWatsonX()` | ✅ Done |
| **AI Council — local heuristic rules** | CPU/heap/offline/signal heuristics | ✅ Done |
| Flipper Zero BLE bridge | `FlipperBLEManager` + `FlipperBridge` module | ✅ Done |
| Flipper protobuf RPC codec | `FlipperProtobuf` | ✅ Done |
| Flipper SD card file ops | `FlipperFileManager` | ✅ Done |
| Flipper Nordic DFU flashing | `FlipperDFUManager` | ✅ Done |
| WiFi Pineapple API client | `PineappleAPIClient` actor | ✅ Done |
| Pineapple recon + CSV/JSON export | `PineappleRecon` | ✅ Done |
| DuckyScript payload management | `PineapplePayloads` | ✅ Done |
| Flipper-Pineapple MAC sync | `PineappleSync` | ✅ Done |
| Keychain credential storage | `KeychainHelper` (KeychainAccess) | ✅ Done |
| Network path monitoring | `NetworkMonitor` (NWPathMonitor) | ✅ Done |
| Flipper `.bm` bitmap decoder | `BMFrameDecoder` | ✅ Done |
| SHA-256 checksum validation | `SHA256Helper` (CryptoKit) | ✅ Done |
| Unified os.log wrapper | `AppLogger` | ✅ Done |
| All credentials via Keychain | No UserDefaults for secrets | ✅ Done |
| `@MainActor` ViewModels | All 6 ViewModels | ✅ Done |
| Swift strict concurrency | `StrictConcurrency` experiment flag | ✅ Done |
| Comprehensive test suite | 8 test files, 215+ assertions | ✅ Done |
| Latest dependency versions | SPM 5.10, deps updated | ✅ Done |

---

## TODO / Rectification Checklist

### High Priority
- [ ] Add `watchOS` companion target with simplified telemetry glance view
- [ ] Wire `AssetPackManager` disk registry to SwiftData for persistence
- [ ] Add background URLSession for large firmware downloads (> 50 MB)
- [ ] Implement push notification support for critical AI council alerts

### Medium Priority
- [ ] Add Charts-framework histogram for frequency scan signal distribution
- [ ] Add CoreML on-device fallback model for AI council (offline support)
- [ ] Expand Flipper protobuf to cover full RPC surface (GPIO, IR, NFC)
- [ ] Add `PineappleSync` deep-link integration with Pineapple web UI
- [ ] Write integration tests using a mock FastAPI server via `Process`

### Low Priority
- [ ] Add widget extension for fleet health summary on Home Screen
- [ ] Add Live Activity for active firmware flash progress
- [ ] Localization support (`.strings` / `String(localized:)`)
- [ ] Add ShareSheet export for recon CSV data from `PineappleRecon`
- [ ] Unit test `BMFrameDecoder` with real Flipper `.bm` fixture files

---

## Architecture

```
+-------------------------------------------------------------------------+
|                          iOS Application                                |
|                                                                         |
|  Tab 1        Tab 2       Tab 3          Tab 4     Tab 5    Tab 6       |
|  Dashboard  --Devices -- AI Council -- Flipper -- Pineapple - Settings  |
|     |           |            |             |          |                 |
|  DashboardVM DeviceListVM AICouncilVM FlipperVM PineappleVM             |
+------+-----------+------------+------------+----------+-----------------+
       |          |            |            |          |
       v          v            v            |          |
+-------------------------------------+    |          |
|   FastAPI Backend  (port 8000)      |    |          |
|                                     |    |          |
|  REST /api/v1/                      |    |          |
|  +-- /status                        |    |          |
|  +-- /devices  (CRUD)               |    |          |
|  +-- /agents   (list/get)           |    |          |
|  +-- /tasks    (dispatch/poll)      |    |          |
|  +-- /firmware/builds               |    |          |
|  +-- /firmware/flash                |    |          |
|  +-- /assets   (list/sync)          |    |          |
|  +-- /ai/analyse  (proxy)           |    |          |
|                                     |    |          |
|  WS /ws/telemetry <-----------------+    |          |
+------------------+------------------+    |          |
                   |                       |          |
                   v                       v          v
       +------------------+  +------------------+  +--------------+
       |  ESP32 Fleet     |  |  Flipper Zero    |  | WiFi         |
       |                  |  |  BLE (RPC / DFU) |  | Pineapple    |
       |  * Node Alpha    |  |                  |  | (REST API)   |
       |  * Node Beta     |  |  FlipperBridge   |  |              |
       |  * Node Gamma    |  |  module          |  | PineappleKit |
       +------------------+  +------------------+  +--------------+
                                      |
                                      v
                         +-------------------------+
                         |   AI Council            |
                         |                         |
                         |  HuggingFace            |
                         |  Inference API          |
                         |  (mistralai/Mistral-7B) |
                         |                         |
                         |  IBM WatsonX.ai         |
                         |  granite-13b-instruct   |
                         |  (metric analysis)      |
                         |                         |
                         |  On-Device Heuristics   |
                         |  (CPU/heap/RSSI/offline)|
                         +----------+--------------+
                                    |
                         +----------v--------------+
                         |   Momentum / Asset CDN  |
                         |   up.momentum-fw.dev    |
                         |   iNFINITE_FLIPZ_ASSET  |
                         |   _PACKZ                |
                         |   AssetPackManager      |
                         +-------------------------+
```

---

## Swift Package Modules

| Module | Sources | Description |
|--------|---------|-------------|
| **IOSIntegration** | `Sources/IOSIntegration/` | Main app: SwiftUI views, @MainActor ViewModels, REST/WS services, models, utilities, config |
| **FlipperBridge** | `Sources/FlipperBridge/` | CoreBluetooth BLE for Flipper Zero, protobuf RPC codec, SD card file ops, Nordic DFU |
| **PineappleKit** | `Sources/PineappleKit/` | WiFi Pineapple REST client, recon/CSV export, DuckyScript payloads, Flipper-Pineapple sync |
| **AssetPackManager** | `Sources/AssetPackManager/` | Momentum CDN client, meta.json parser, disk-persisted install registry |

---

## API Endpoint Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/status` | System health check |
| GET | `/api/v1/devices` | List all ESP32 devices |
| POST | `/api/v1/devices` | Register a new device |
| GET | `/api/v1/devices/{id}` | Get device by ID |
| PUT | `/api/v1/devices/{id}` | Update device metadata |
| DELETE | `/api/v1/devices/{id}` | Deregister a device |
| GET | `/api/v1/devices/{id}/telemetry` | Historical telemetry |
| GET | `/api/v1/agents` | List orchestrator agents |
| GET | `/api/v1/tasks` | List tasks |
| POST | `/api/v1/tasks` | Dispatch task to agent |
| GET | `/api/v1/tasks/{id}` | Poll task status |
| DELETE | `/api/v1/tasks/{id}` | Cancel task |
| GET | `/api/v1/firmware/builds` | List firmware builds |
| POST | `/api/v1/firmware/flash` | Flash OTA firmware |
| GET | `/api/v1/assets` | List cached asset packs |
| POST | `/api/v1/assets/sync` | Sync with Momentum CDN |
| POST | `/api/v1/ai/analyse` | AI council analysis proxy |
| WS | `/ws/telemetry` | Real-time telemetry stream |

---

## AI Council

The AI Council analyses live fleet telemetry using two cloud AI models **and** fast local heuristics. All three sources run concurrently; results are merged into a single `AICouncilAnalysis`.

### HuggingFace Inference API

Connects to `https://api-inference.huggingface.co/models/<model-id>` using a bearer token.

**Default model:** `mistralai/Mistral-7B-Instruct-v0.3`

```swift
let council = AICouncilService()
let text = try await council.queryHuggingFace(prompt: "Analyse these metrics...")
```

### IBM WatsonX Orchestrator

Connects to `https://us-south.ml.cloud.ibm.com/ml/v1/text/generation` using an IBM Cloud IAM API key. IAM bearer tokens are automatically fetched and refreshed.

**Default model:** `ibm/granite-13b-instruct-v2`

```swift
let text = try await council.queryWatsonX(prompt: "What is wrong with the fleet?")
```

### Metric Analysis Flow

```
TelemetrySocket --> telemetryBuffer (100 frames)
                          |
                          v
             AICouncilService.analyse()
                    +-----+-----+
                    v     v     v
              HF model  WX model  Local rules
                    +-----+-----+
                          v
                   AICouncilAnalysis
                   +-- criticalCount
                   +-- warningCount
                   +-- infoCount
                   +-- sortedRecommendations
                   +-- metricsSnapshot
```

### Recommendation Severity Levels

| Severity | Condition examples |
|----------|--------------------|
| `critical` | CPU > 95%, heap < 8 KB, 3+ offline devices |
| `warning`  | CPU 85-95%, heap 8-20 KB, RSSI < -80 dBm, 1-2 offline |
| `info`     | General tips, non-urgent observations |

---

## Flipper Zero BLE Protocol

### Known Service UUIDs

| Service | UUID |
|---------|------|
| Flipper Serial | `8fe5b3d5-2e7f-4a98-2a48-7acc60fe0000` |
| Nordic DFU | `0000fe59-0000-1000-8000-00805f9b34fb` |

### RPC Frame Format

```
+----------+----------------------+
| 2 bytes  | N bytes              |
|  Length  |  Protobuf payload    |
+----------+----------------------+
```

Commands: `storage_list`, `storage_read`, `storage_write`, `storage_delete`, `app_start`

### SD Card Paths

| Purpose | Path |
|---------|------|
| Dolphin animations | `/ext/dolphin/` |
| .fap plugins | `/ext/apps/` |
| Assets | `/ext/apps_assets/` |

---

## Environment Variable Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MULTI_AGENT_BASE_URL` | `http://localhost:8000` | FastAPI REST base URL |
| `MULTI_AGENT_WS_URL` | `ws://localhost:8000/ws/telemetry` | WebSocket URL |
| `PINEAPPLE_HOST` | `172.16.42.1` | WiFi Pineapple IP |
| `REQUEST_TIMEOUT` | `30` | URLSession timeout (seconds) |
| `RETRY_MAX_ATTEMPTS` | `3` | Max retry attempts |
| `RETRY_BASE_DELAY` | `1.0` | Exponential backoff base (seconds) |
| `HF_API_TOKEN` | *(Keychain)* | HuggingFace Inference API bearer token |
| `HF_MODEL_ID` | `mistralai/Mistral-7B-Instruct-v0.3` | HuggingFace model to use |
| `HF_INFERENCE_BASE_URL` | `https://api-inference.huggingface.co` | HF endpoint override |
| `WATSONX_API_KEY` | *(Keychain)* | IBM Cloud IAM API key |
| `WATSONX_PROJECT_ID` | *(Keychain)* | WatsonX project ID |
| `WATSONX_BASE_URL` | `https://us-south.ml.cloud.ibm.com` | WatsonX regional endpoint |
| `WATSONX_MODEL_ID` | `ibm/granite-13b-instruct-v2` | WatsonX model ID |
| `AI_MAX_TOKENS` | `512` | Max generated tokens |
| `AI_TEMPERATURE` | `0.3` | Sampling temperature (0-2) |

---

## Build & Test

### Prerequisites

- Xcode 16+ (Swift 5.10)
- iOS 17 Simulator or device
- macOS 14+ for local test runs

### Build

```bash
cd ios-integration
swift build
```

### Test

```bash
swift test
```

### Test Coverage

| Target | Files | Assertions |
|--------|-------|------------|
| `IOSIntegrationTests` | 6 | ~185 |
| `FlipperBridgeTests` | 1 | ~25 |
| `PineappleKitTests` | 1 | ~30 |
| **Total** | **8** | **~240** |

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| [Starscream](https://github.com/daltoniam/Starscream) | `>= 4.0.6` | WebSocket client |
| [KeychainAccess](https://github.com/kishikawakatsumi/KeychainAccess) | `>= 4.2.2` | iOS Keychain wrapper |
| [swift-protobuf](https://github.com/apple/swift-protobuf) | `>= 1.29.0` | Flipper RPC protobuf runtime |
| [swift-algorithms](https://github.com/apple/swift-algorithms) | `>= 1.2.0` | Advanced collection algorithms |

System frameworks: **Foundation**, **SwiftUI**, **CoreBluetooth**, **Network**, **CryptoKit**, **Charts**, **OSLog**, **Security**.

---

## Integration with iNFINITE_FLIPZ_ASSET_PACKZ

Set `MULTI_AGENT_BASE_URL` to your backend, then navigate to the **Asset Pack Browser** tab.

To use assets from `iNFINITE_FLIPZ_ASSET_PACKZ`:
1. Host `meta.json` at a publicly accessible URL
2. Set `ASSET_PACK_CDN_URL` in scheme environment (optional override)
3. Asset packs appear automatically in the Asset Pack Browser tab

---

## Contributing

1. Fork the repo and create a branch from `NiA_FBT26`
2. All new code must use `async/await` — no completion handlers
3. New services must conform to a `Protocol` for testability
4. All new `ViewModel` types must be `@MainActor`
5. Run `swift test` and ensure all tests pass before opening a PR
6. Credentials must go through `KeychainHelper` — never `UserDefaults`

---

## Security Notes

- All API tokens stored in iOS Keychain with `.afterFirstUnlock` accessibility
- SHA-256 checksums validated on every OTA firmware download before flashing
- IBM Cloud IAM tokens cached in memory only — never persisted to disk
- WatsonX + HuggingFace keys stored via Security framework (not UserDefaults)
- No secrets are committed to source control
