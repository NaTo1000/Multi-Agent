# Multi-Agent ESP32 Orchestration System — V2.1 Quantum Edition

A production-grade multi-agent orchestration platform for managing fleets of ESP32 modules in real time — with full AI automation, frequency/modulation control, on-the-fly firmware creation, GPS/GNSS, cloud integration, a cross-platform mobile companion app, and a **supercharged quantum-computing layer** for optimal channel selection, secure key exchange, and fleet-wide synchronisation.

---

## What's New in V2.1

| Feature | Details |
|---|---|
| **QuantumAgent** | New agent providing QAOA, Grover, QRNG, BB84 QKD, QFT, and GHZ entanglement |
| **QAOA Optimisation** | Quantum Approximate Optimisation Algorithm for interference-free channel selection |
| **Grover Channel Search** | Quadratic-speedup search over frequency candidates |
| **BB84 QKD** | Full BB84 quantum key distribution simulation for secure device pairing |
| **QFT Spectrum Analysis** | Quantum Fourier Transform-based interference detection |
| **GHZ Fleet Entanglement** | Atomic fleet-wide frequency synchronisation via quantum consensus |
| **QRNG** | Quantum-inspired random number generation (Hadamard mixing + OS entropy) |
| **QuantumEngine** | Autonomous quantum-policy scheduler alongside the classical AutomationEngine |
| **QAM64/256/1024 + QISS** | Higher-order quantum-era modulation schemes for ultra-high-throughput links |
| **Quantum REST API** | `/api/v1/quantum/` route family for all quantum operations |

---

## Features

| Capability | Details |
|---|---|
| **Multi-Agent Orchestration** | Concurrent management of unlimited ESP32 modules |
| **AI Automation** | Adaptive frequency locking, interference detection, modulation selection |
| **Quantum Optimisation** | QAOA, Grover, QFT algorithms for superior channel/frequency decisions |
| **Quantum Cryptography** | BB84 QKD session-key exchange, QRNG entropy generation |
| **Frequency Control** | Scan, lock, fine-tune (PID), fleet-wide synchronisation |
| **Modulation** | AM / FM / FSK / GFSK / LoRa / QPSK / QAM16–1024 / QISS with adaptive selection |
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
┌─────────────────────────────────────────────────────────────────────┐
│                     Orchestrator (Python)                            │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐            │
│  │ Frequency   │  │  Modulation  │  │    Firmware     │            │
│  │   Agent     │  │    Agent     │  │     Agent       │            │
│  └─────────────┘  └──────────────┘  └─────────────────┘            │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐            │
│  │   Comms     │  │    AI        │  │    Quantum      │  V2.1 ★    │
│  │   Agent     │  │   Agent      │  │     Agent       │            │
│  └─────────────┘  └──────────────┘  └─────────────────┘            │
│                                                                     │
│  AutomationEngine (classical)  +  QuantumEngine (V2.1)             │
│  REST API (FastAPI)            ●   WebSocket (real-time)            │
│  Cloud Connectors              ●   Telemetry Monitor                │
└─────────────────────────────────────────────────────────────────────┘
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
| POST | `/api/v1/quantum/task` | Dispatch any task to the QuantumAgent |
| POST | `/api/v1/quantum/qaoa/{device_id}` | QAOA frequency optimisation |
| POST | `/api/v1/quantum/qkd/{device_id}` | BB84 QKD key exchange |
| POST | `/api/v1/quantum/grover` | Grover channel search |
| POST | `/api/v1/quantum/qft` | QFT interference spectrum analysis |
| POST | `/api/v1/quantum/qrng` | Generate quantum-random bytes |
| POST | `/api/v1/quantum/entangle` | GHZ fleet entanglement sync |

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
├── agents/             Specialised agents (frequency, modulation, firmware, comms, AI, quantum ★)
├── ai/                 AI automation engine, PID controller, and QuantumEngine ★
├── comms/              WiFi, BLE, GPS/GNSS host-side managers
├── firmware/           Firmware builder, OTA flasher, and ESP32 C++ templates
├── cloud/              Cloud connector (HTTP, AWS, GCP, Azure)
├── api/                FastAPI REST + WebSocket server (v2.1.0) ★
├── logging_system/     Structured logging and telemetry monitor
├── app/                React Native cross-platform mobile app
├── config/             YAML configuration files
├── tests/              pytest test suite (56 + quantum tests) ★
└── main.py             Entry point (server / demo / cli modes)
```
