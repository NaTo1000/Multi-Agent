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
| **Spectrum Analyzer** | FFT-based RF spectrum analysis, channel occupancy, waterfall heatmap |
| **Auto-Discovery** | Zero-config device discovery: mDNS, ARP subnet scan, BLE, YAML/CSV import |
| **LLM Integration** | Ollama / OpenAI / Anthropic / Groq — firmware generation, fault diagnosis |
| **Device Simulator** | Virtual ESP32 with full HTTP API — no hardware needed for development |
| **Predictive Maintenance** | EWMA anomaly scoring, failure prediction, auto-heal actions |
| **Firmware OTA** | On-the-fly C++ generation, arduino-cli build, HTTP OTA flash |
| **WiFi** | STA connection, network scanning, mDNS, HTTP API server on device |
| **BLE 5** | 2M PHY advertising, GATT command server, paired-app communication |
| **LoRa Mesh** | Self-healing multi-hop mesh (SX1276/RFM95), beacon discovery |
| **ESP-NOW Mesh** | Sub-1ms peer-to-peer mesh, auto peer discovery, reliable unicast |
| **GPS / GNSS** | NMEA 0183 parsing, async serial reading, GPS Mission Planner |
| **Cloud** | HTTP, AWS IoT Core, GCP Pub/Sub, Azure IoT Hub |
| **REST + WebSocket API** | FastAPI server for mobile apps and web dashboards |
| **Web Dashboard** | Plotly Dash: RSSI trends, spectrum waterfall, GPS map, fleet health gauge |
| **Real-time Logging** | Structured JSON logging, rotating files, threshold alerts |
| **Cross-platform App** | React Native (iOS + Android) — 7 screens including Mesh Manager + GPS |
| **Raspberry Pi** | Runs natively — no hardware-specific dependencies |

---

## Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│                     Orchestrator (Python)                          │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │Frequency │  │Modulation│  │Firmware  │  │SpectrumAnalyzer  │  │
│  │  Agent   │  │  Agent   │  │  Agent   │  │     Agent        │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  Comms   │  │    AI    │  │Discovery │  │  Predictive      │  │
│  │  Agent   │  │  Agent   │  │  Agent   │  │  Maintenance     │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘  │
│                                                                   │
│  REST API (FastAPI)  ●  WebSocket    ●  Plotly Dash Dashboard     │
│  Cloud Connectors    ●  LLM Client   ●  Device Simulator          │
└───────────────────────────────────────────────────────────────────┘
         │                         │
    WiFi / BLE / LoRa        Cloud (HTTP/AWS/GCP/Azure)
         │
┌────────┴────────────────────────┐
│  ESP32 Modules                  │
│  WiFi + BLE5 + GPS + LoRa Mesh  │
│  ESP-NOW Mesh firmware          │
└─────────────────────────────────┘
         │
┌────────┴────────┐
│  Mobile App     │  React Native — iOS + Android
│  7 Screens      │  Dashboard · Devices · RF · FW · Mesh · GPS · Settings
└─────────────────┘
```

---

## Quick Start

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure devices

Edit `config/devices.yaml` with your ESP32 IP addresses, or let the DiscoveryAgent
find them automatically:

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{"agent_id":"<discovery-agent-id>","task":"discover","params":{}}'
```

### 3. Run the orchestration server

```bash
python main.py --mode server --port 8000
```

Access:
- **REST API docs**: http://localhost:8000/docs
- **WebSocket**: `ws://localhost:8000/ws/telemetry`

### 4. Run the web dashboard

```bash
pip install dash plotly
python -m api.dashboard --port 8050
# Open http://localhost:8050/dashboard/
```

### 5. Run the demo (no hardware needed)

```bash
python main.py --mode demo
```

The demo automatically starts a `SimulatorFleet` with 4 virtual ESP32s.

### 6. Build ESP32 firmware

```bash
curl -X POST http://localhost:8000/api/v1/firmware/build \
  -H 'Content-Type: application/json' \
  -d '{"template":"base","features":["wifi","ble","gps","lora_mesh"],"version":"2.0.0"}'
```

---

## AI / LLM Integration

### Local (Ollama — free, runs on your machine)

```bash
# Install Ollama from https://ollama.ai
ollama pull llama3

# Firmware generation via REST
curl -X POST http://localhost:8000/api/v1/ai/research \
  -d '{"query":"Generate ESP32 firmware for a soil moisture sensor with LoRa"}'
```

### OpenAI / Anthropic / Groq

Edit `config/default.yaml`:

```yaml
ai_agent:
  llm:
    provider: "openai"   # ollama | openai | anthropic | groq | lmstudio
    model: "gpt-4o"
    api_key: "sk-..."
```

---

## ESP32 Firmware

Firmware templates are in `firmware/templates/`:

| File | Description |
|---|---|
| `base.cpp` | Core HTTP command server, OTA stub, frequency/modulation state |
| `wifi.cpp` | WiFi STA, mDNS, HTTP API, network scan, RSSI, OTA via HTTPUpdate |
| `ble.cpp` | BLE 5 2M PHY, GATT server, Nordic UART-compatible service |
| `gps.cpp` | TinyGPS++ NMEA parser, UART2 serial GPS |
| `lora_mesh.cpp` | Self-healing LoRa mesh, flooding routing, beacon discovery |
| `espnow.cpp` | ESP-NOW peer-to-peer mesh, auto-discovery, reliable unicast |

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
| POST | `/api/v1/ai/research` | LLM-powered research query |

---

## Mobile App

The React Native companion app (`app/`) provides 7 screens:

| Screen | Description |
|---|---|
| **Dashboard** | Live WebSocket status — device cards, agent activity |
| **Devices** | Register, ping, AI-optimise ESP32 modules |
| **Frequency** | Band scan, presets, lock, fine-tune, fleet sync |
| **Firmware** | On-the-fly build with feature flags |
| **Mesh** | ESP-NOW / LoRa mesh topology graph, node commands, mesh OTA |
| **GPS** | Real-time device positions, waypoint planning, mission upload |
| **Settings** | Orchestrator host, cloud endpoint, LLM config |

### Run the app

```bash
cd app
npm install
npm run android   # or: npm run ios
```

---

## Predictive Maintenance

The `PredictiveMaintenanceAgent` monitors every device continuously and:
- Scores health 0–100 using RSSI, heap, uptime, error rate
- Predicts time-to-failure by linear extrapolation of the health trend
- Auto-heals: triggers OTA if health < 30, frequency re-scan if health < 60
- Generates prioritised fleet maintenance schedules

---

## Spectrum Analysis

The `SpectrumAnalyzerAgent` provides:
- Per-band channel sweep with RSSI sampling
- FFT-based power spectral density computation
- Rolling waterfall buffer (60 frames)
- Channel occupancy tracking with busy%
- Best-channel recommendation (lowest interference)
- Dominant interferer detection

---

## Raspberry Pi Support

The orchestration backend runs natively on Raspberry Pi:

```bash
pip install RPi.GPIO pyserial-asyncio
python main.py --mode server
```

Attach a GPS module to `/dev/ttyUSB0`, a LoRa module via SPI,
and the platform becomes a full gateway node.

---

## Cloud Integration

Configure in `config/default.yaml`:

```yaml
comms_agent:
  cloud_connector: "aws"    # http | aws | gcp | azure
  cloud_endpoint: "https://your-endpoint.amazonaws.com"
```

---

## Development

```bash
# Run all 124 tests
python -m pytest tests/ -v

# Run server in development mode
python main.py --mode server --log-level DEBUG

# Launch interactive demo with 4 simulated ESP32s
python main.py --mode demo

# Start the web dashboard
python -m api.dashboard --debug
```

---

## Directory Structure

```
├── orchestrator/           Core engine + Device Simulator
├── agents/                 8 specialised agents
│   ├── frequency_agent.py  Scan / lock / PID fine-tune
│   ├── modulation_agent.py Adaptive modulation
│   ├── firmware_agent.py   On-the-fly build + OTA
│   ├── comms_agent.py      WiFi / BLE / GPS / cloud
│   ├── ai_agent.py         Optimise / research / anomaly
│   ├── spectrum_agent.py   FFT spectrum analysis
│   ├── discovery_agent.py  Zero-config auto-discovery
│   └── predictive_agent.py Predictive maintenance
├── ai/
│   ├── automation.py       Policy-driven background loop
│   ├── frequency_lock.py   PID closed-loop controller
│   └── llm_client.py       Ollama / OpenAI / Anthropic / Groq
├── comms/                  WiFi / BLE / GPS host managers
├── firmware/
│   ├── builder.py          On-the-fly C++ assembler
│   ├── flasher.py          HTTP OTA flasher
│   └── templates/
│       ├── base.cpp        HTTP command server
│       ├── wifi.cpp        WiFi STA + OTA
│       ├── ble.cpp         BLE 5 GATT server
│       ├── gps.cpp         TinyGPS++ NMEA parser
│       ├── lora_mesh.cpp   Self-healing LoRa mesh
│       └── espnow.cpp      ESP-NOW P2P mesh
├── cloud/                  HTTP / AWS / GCP / Azure connectors
├── api/
│   ├── server.py           FastAPI app
│   ├── routes.py           REST endpoints
│   ├── websocket.py        WebSocket telemetry
│   └── dashboard.py        Plotly Dash web dashboard
├── logging_system/         Structured JSON logging + alerting
├── app/                    React Native (7 screens)
│   └── src/screens/
│       ├── DashboardScreen.js
│       ├── DevicesScreen.js
│       ├── FrequencyScreen.js
│       ├── FirmwareScreen.js
│       ├── MeshManagerScreen.js
│       ├── GPSMissionScreen.js
│       └── SettingsScreen.js
├── config/                 YAML configuration
├── tests/                  pytest — 124 tests
└── main.py                 Entry point (server / demo / cli)
```


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
| **Cloud** | HTTP, AWS IoT Core, GCP Pub/Sub, Azure IoT Hub |
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

Configure the cloud connector in `config/default.yaml`:

```yaml
comms_agent:
  cloud_connector: "aws"    # http | aws | gcp | azure
  cloud_endpoint: "https://your-endpoint.amazonaws.com"
```

Or override per-request via the `/api/v1/tasks` endpoint:
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
├── cloud/              Cloud connector (HTTP, AWS, GCP, Azure)
├── api/                FastAPI REST + WebSocket server
├── logging_system/     Structured logging and telemetry monitor
├── app/                React Native cross-platform mobile app
├── config/             YAML configuration files
├── tests/              pytest test suite (56 tests)
└── main.py             Entry point (server / demo / cli modes)
```
