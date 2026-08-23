# Multi-Agent ESP32 Orchestration System

A production-grade multi-agent orchestration platform for managing fleets of ESP32 modules in real time — with full AI automation, frequency/modulation control, on-the-fly firmware creation, GPS/GNSS, cloud integration, and a cross-platform mobile companion app.

---

## Features

| Capability | Details |
|---|---|
| **Multi-Agent Orchestration** | Concurrent management of unlimited ESP32 modules |
| **AI Automation** | Adaptive frequency locking, interference detection, modulation selection |
| **Frequency Control** | Scan, lock, fine-tune (PID), fleet-wide synchronisation |
| **Modulation** | AM / FM / FSK / GFSK / LoRa / QPSK / QAM16 with adaptive selection |
| **Firmware OTA** | On-the-fly C++ generation, arduino-cli build, HTTP OTA flash |
| **WiFi** | STA connection, network scanning, mDNS, HTTP API server on device |
| **BLE 5** | 2M PHY advertising, GATT command server, paired-app communication |
| **GPS / GNSS** | NMEA 0183 parsing, async serial reading, fix streaming |
| **Cloud** | Configurable webhook (HTTP / own VPS / local), AWS IoT Core, GCP Pub/Sub, Azure IoT Hub |
| **Compute** | Pluggable offload — local VPS (default), AWS Lambda, GCP Cloud Functions |
| **REST + WebSocket API** | FastAPI server for mobile apps and web dashboards |
| **Real-time Logging** | Structured JSON logging, rotating files, threshold alerts |
| **Cross-platform App** | React Native (iOS + Android) companion app |
| **Raspberry Pi** | Runs natively — no hardware-specific dependencies |

---

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│                   Orchestrator (Python)                    │
│                                                           │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Frequency   │  │  Modulation  │  │    Firmware     │  │
│  │   Agent     │  │    Agent     │  │     Agent       │  │
│  └─────────────┘  └──────────────┘  └─────────────────┘  │
│  ┌─────────────┐  ┌──────────────┐                        │
│  │   Comms     │  │    AI        │  TaskScheduler          │
│  │   Agent     │  │   Agent      │  EventBus              │
│  └─────────────┘  └──────────────┘                        │
│                                                           │
│  REST API (FastAPI)  ●  WebSocket (real-time)             │
│  Cloud Connectors    ●  Telemetry Monitor                 │
└───────────────────────────────────────────────────────────┘
         │                         │
    WiFi / BLE               Cloud (HTTP/AWS/GCP/Azure)
         │
┌────────┴────────┐
│  ESP32 Modules  │  (WiFi + BLE 5 + GPS/GNSS)
│  Base Firmware  │
└─────────────────┘
         │
┌────────┴────────┐
│  Mobile App     │  (React Native — iOS + Android)
│  Dashboard      │
└─────────────────┘
```

---

## Quick Start

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure devices

Edit `config/devices.yaml` with your ESP32 IP addresses, or register them
dynamically via the REST API.

### 3. Run the orchestration server

```bash
python main.py --mode server --port 8000
```

Access:
- **REST API docs**: http://localhost:8000/docs
- **WebSocket**: `ws://localhost:8000/ws/telemetry`

### 4. Run the demo (no hardware needed)

```bash
python main.py --mode demo
```

### 5. Build ESP32 firmware

```bash
curl -X POST http://localhost:8000/api/v1/firmware/build \
  -H 'Content-Type: application/json' \
  -d '{"template":"base","features":["wifi","ble","gps"],"version":"1.0.0"}'
```

---

## ESP32 Firmware

Firmware templates are in `firmware/templates/`:

| File | Description |
|---|---|
| `base.cpp` | Core HTTP command server, OTA stub, frequency/modulation state |
| `wifi.cpp` | WiFi STA, HTTP server, network scan, RSSI, OTA via HTTPUpdate |
| `ble.cpp` | BLE 5 advertising, GATT server, Nordic UART-compatible service |
| `gps.cpp` | NMEA parsing via TinyGPS++, UART2 GPS module support |

The `FirmwareAgent` assembles these at runtime and optionally compiles
with `arduino-cli` (FQBN: `esp32:esp32:esp32`).

---

## REST API Reference

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/status` | Orchestrator status |
| GET | `/api/v1/devices` | List all devices |
| POST | `/api/v1/devices` | Register a new device |
| DELETE | `/api/v1/devices/{id}` | Remove a device |
| POST | `/api/v1/devices/{id}/ping` | Ping a device |
| GET | `/api/v1/agents` | List agents and metrics |
| POST | `/api/v1/tasks` | Dispatch a task to an agent |
| POST | `/api/v1/tasks/broadcast` | Broadcast task to all agents of a type |
| GET | `/api/v1/tasks/{id}` | Get task result |
| POST | `/api/v1/firmware/build` | Build firmware on-the-fly |
| POST | `/api/v1/firmware/flash/{device_id}` | OTA flash a device |
| POST | `/api/v1/ai/optimise/{device_id}` | AI-driven device optimisation |
| POST | `/api/v1/ai/research` | AI research query |

Cloud webhook (`cloud_push`) and compute offload (`compute_offload`) are
dispatched through `/api/v1/tasks` to the comms agent — see
[Cloud Integration](#cloud-integration) and [Compute Backends](#compute-backends).

---

## Mobile App

The React Native companion app (`app/`) provides:

- **Dashboard** — live WebSocket status of all devices and agents
- **Devices** — register, ping, and manage ESP32 modules
- **Frequency** — band scan, lock, fine-tune, fleet sync
- **Firmware** — build and deploy firmware on-the-fly
- **Settings** — configure orchestrator host, cloud endpoint, preferences

### Run the app

```bash
cd app
npm install
npm run android   # or: npm run ios
```

---

## Raspberry Pi Support

The orchestration backend runs natively on Raspberry Pi:

```bash
# RPi-specific optional dependencies
pip install RPi.GPIO pyserial-asyncio

# Run with GPS module on /dev/ttyUSB0
python main.py --mode server
```

The `GPSManager` reads NMEA sentences directly from a serial GPS dongle,
and `WiFiManager` uses `nmcli` (available by default on RPi OS).

---

## Cloud Integration

The telemetry webhook is fully configurable — send it to AWS, Google Cloud,
Azure, or your own VPS / local server.

Configure the connector in `config/default.yaml`:

```yaml
comms_agent:
  cloud_connector: "aws"    # http | vps | local | aws | gcp | azure
  cloud_endpoint: "https://your-endpoint.amazonaws.com"
```

Or use the nested style:

```yaml
comms_agent:
  cloud_connector:
    backend: "gcp"
    endpoint: "projects/my-project/topics/esp32-telemetry"
```

### Self-hosted (VPS / local server)

Point the webhook at your own server — no cloud account needed:

```yaml
comms_agent:
  cloud_connector: "vps"
  cloud_endpoint: "https://my-vps.example.com"
  path_prefix: "/telemetry"
  api_key: "your-shared-secret"
```

### Per-request override

Override the connector per call via the `/api/v1/tasks` endpoint:

```json
{
  "agent_id": "<comms-agent-id>",
  "task": "cloud_push",
  "params": {
    "connector": "aws",
    "endpoint": "https://..."
  }
}
```

---

## Compute Backends

Heavy jobs (firmware builds, AI batch work, ...) can run on the local host,
your own VPS, AWS Lambda, or GCP Cloud Functions:

```yaml
compute:
  backend: "local"      # local | vps | aws | gcp
  endpoint: ""          # local/vps worker URL, or GCP function URL
  function: ""          # AWS Lambda function name
  aws_region: "us-east-1"
```

Offload a job via the `compute_offload` task:

```json
{
  "agent_id": "<comms-agent-id>",
  "task": "compute_offload",
  "params": {
    "backend": "aws",
    "function": "firmware-builder",
    "job": "firmware_build",
    "payload": {"features": ["wifi", "ble"]}
  }
}
```

- `local` (default) — runs in-process; set `endpoint` to POST the job to your own worker instead.
- `aws` — invokes the configured Lambda function (requires `boto3`).
- `gcp` — POSTs the job to the configured Cloud Function / Cloud Run URL.

---

## Development

```bash
# Run all tests
python -m pytest tests/ -v

# Run server in development mode
python main.py --mode server --log-level DEBUG

# Interactive CLI
python main.py --mode cli
```

---

## Directory Structure

```
├── orchestrator/       Core orchestrator engine
├── agents/             Specialised agents (frequency, modulation, firmware, comms, AI)
├── ai/                 AI automation engine and PID frequency lock controller
├── comms/              WiFi, BLE, GPS/GNSS host-side managers
├── firmware/           Firmware builder, OTA flasher, and ESP32 C++ templates
├── cloud/              Cloud connectors (HTTP/VPS/local, AWS, GCP, Azure) and compute backends
├── api/                FastAPI REST + WebSocket server
├── logging_system/     Structured logging and telemetry monitor
├── app/                React Native cross-platform mobile app
├── config/             YAML configuration files
├── tests/              pytest test suite (56 tests)
└── main.py             Entry point (server / demo / cli modes)
```
