# NAi\_iNFINITEAi — Multi-Agent ESP32 Orchestration with Cognitive AI Core

> **NAi\_iNFINITEAi** is a production-grade, self-learning, multi-agent orchestration platform for managing fleets of ESP32 modules in real time, augmented by a full-stack cognitive AI layer — the **Technical Learning Cortex (TLC)**, **HiAi**, **CHAiMERA3sp**, **TWINBRAiN**, and **VoiceAnalysisEngine** — that can run on top of any existing LLM or independently without any external model dependency.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [AI Cognitive Stack](#ai-cognitive-stack)
   - [HiAi — Human Intelligence Augmented AI](#hiai)
   - [CHAiMERA3sp — Multi-Engine Router + Tracery](#chaimera3sp)
   - [TLC — Technical Learning Cortex](#tlc)
   - [VoiceAnalysisEngine + Cortex Council](#voiceanalysisengine)
   - [TWINBRAiN — Compassion Response Engine](#twinbrain)
4. [Hardware Layer](#hardware-layer)
5. [Quick Start](#quick-start)
6. [Configuration](#configuration)
7. [REST & WebSocket API](#rest--websocket-api)
8. [ESP32 Firmware](#esp32-firmware)
9. [Mobile App](#mobile-app)
10. [Cloud Integration](#cloud-integration)
11. [Testing](#testing)
12. [Directory Structure](#directory-structure)
13. [Development](#development)

---

## Overview

| Capability | Details |
|---|---|
| **Multi-Agent Orchestration** | Concurrent management of unlimited ESP32 modules |
| **Cognitive AI Core (TLC)** | Self-testing dream-state engine, predictive reasoning, autonomous decisions |
| **HiAi Pre-processing** | VAD emotional inference, user profiling, ambiguity resolution |
| **CHAiMERA3sp Routing** | 4-provider AI router with tracery knowledge scraping and fake-info dispelling |
| **Voice Analysis** | Real-time pitch/speed classification → emotional state → Cortex Council synthesis |
| **TWINBRAiN** | Millisecond-evolving compassion response inventory |
| **Frequency Control** | Scan, lock, fine-tune (PID), fleet-wide synchronisation |
| **Modulation** | AM / FM / FSK / GFSK / LoRa / QPSK / QAM16 with adaptive selection |
| **Firmware OTA** | On-the-fly C++ generation, arduino-cli build, HTTP OTA flash |
| **WiFi / BLE 5** | STA connection, GATT command server, paired-app communication |
| **GPS / GNSS** | NMEA 0183 parsing, async serial reading |
| **Cloud** | HTTP, AWS IoT Core, GCP Pub/Sub, Azure IoT Hub |
| **REST + WebSocket** | FastAPI server for mobile apps and web dashboards |
| **Cross-platform App** | React Native (iOS + Android) companion app |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    NAi_iNFINITEAi Platform                           │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                  Cognitive AI Core                              │ │
│  │                                                                 │ │
│  │  ┌──────────┐  ┌────────────────┐  ┌───────────────────────┐  │ │
│  │  │  HiAi    │  │  CHAiMERA3sp   │  │   TLC (Dream Engine)  │  │ │
│  │  │ VAD+NRC  │  │ 4-Engine Router│  │ Waking│Dream│Predict  │  │ │
│  │  │ Profiler │  │ Tracery/Lockout│  └───────────────────────┘  │ │
│  │  │ Ambiguity│  └────────────────┘                             │ │
│  │  └──────────┘  ┌────────────────┐  ┌───────────────────────┐  │ │
│  │                │ VoiceAnalysis  │  │     TWINBRAiN         │  │ │
│  │                │ Pitch│Speed    │  │  Compassion Inventory │  │ │
│  │                │ CortexCouncil  │  │  Real-time Evolution  │  │ │
│  │                └────────────────┘  └───────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────────┐ │
│  │  Frequency  │  │  Modulation  │  │         Firmware            │ │
│  │    Agent    │  │    Agent     │  │          Agent              │ │
│  └─────────────┘  └──────────────┘  └─────────────────────────────┘ │
│  ┌─────────────┐  ┌──────────────┐  TaskScheduler  EventBus        │ │
│  │   Comms     │  │    AI        │                                  │ │
│  │   Agent     │  │   Agent      │  REST API (FastAPI)              │ │
│  └─────────────┘  └──────────────┘  WebSocket (real-time)          │ │
└──────────────────────────────────────────────────────────────────────┘
        │                              │
    WiFi / BLE 5                   Cloud (HTTP/AWS/GCP/Azure)
        │
┌────────┴────────┐
│  ESP32 Fleet    │   WiFi + BLE 5 + GPS/GNSS
│  OTA Firmware   │
└─────────────────┘
        │
┌────────┴────────┐
│  Mobile App     │   React Native — iOS + Android
└─────────────────┘
```

---

## AI Cognitive Stack

### HiAi

**Human Intelligence Augmented AI** — runs before every provider query.

| Sub-system | Science | Function |
|---|---|---|
| `EmotionalStateModel` | VAD (Russell 1980) + NRC EmoLex (Mohammad & Turney 2013) | Infers Valence/Arousal/Dominance from prompt text |
| `UserProfileStore` | Descriptive statistics over rolling window | Per-user tone, verbosity, ambiguity rate profile |
| `AmbiguityResolver` | Grice (1975) Cooperative Principle | Detects lexical / referential / scope / ellipsis ambiguity; disambiguates prompt |

**Output** → `HiAiResult` with `resolved_prompt`, `emotional_snapshot`, `rapport_note`, `rapport_context`

---

### CHAiMERA3sp

**Composite Hybrid AI Multi-Engine Routing Architecture** — routes queries to 4 AI providers with post-response knowledge integrity enforcement.

**Providers:** `watsonx` · `kimi` · `kai9000` · `manus`

**Strategies:** `first` · `fallback` · `broadcast`

**Tracery Subsystem** (post-response pipeline):

| Component | Function |
|---|---|
| `KnowledgeScraper` | Extracts `TraceryNode` factual claims from response text |
| `AccuracyScrutineer` | Detects contradictions → **dispels fake info** → logs at WARNING |
| `SeriesDecipher` | Groups claims by topic series; computes coherence scores |
| `InferenceStreamMonitor` | **Percentage-based lockouts**: accuracy < 40% after ≥5 claims → provider locked |
| `get_research_report()` | Full `DataResearchReport` with series, dispelled nodes, accuracy per provider |

---

### TLC

**Technical Learning Cortex** — the brain of the system. Three operating modes:

#### Waking Mode
Records `TechnicalObservation` objects → `PatternRecognizer` derives `KnowledgeEntry` insights with evidence-weighted confidence.

#### Dream-State Mode
Periodic self-test cycle:
1. Deep-copies live knowledge store as sandbox
2. Applies 5 guardrailed corruption types (`negate_success`, `nullify_param`, `inject_band_noise`, `deflate_confidence`, `domain_swap`)
3. Measures system reaction (`resilient` / `degraded` / `failed`)
4. Researches reactions → activates 5 Algorithmic Protocols (Alpha–Epsilon)
5. Produces `DreamEvaluation` with recommendations
6. Derives `MindStatus` (`healthy` / `learning` / `stressed` / `degraded`)

#### Predictive Mode
`OutcomeInventory` (recency-weighted, oldest=1.0×, newest=2.0×) → `PredictiveReasoner` → `AutonomousDecision` (4-way: `proceed` / `caution` / `abort` / `defer`).  Fluid anomaly detection quarantines outlier observations without removing them.

---

### VoiceAnalysisEngine

Real-time pitch and speech-speed analysis pipeline feeding the **Cortex Council**.

```
VoiceFrame (pitch Hz, speed WPM, amplitude dB, text)
    → PitchContour (mean, variance, delta Hz/s, inflections, trend)
    → SentencePattern (declarative / interrogative / exclamatory / trailing)
    → EmotionalState (calm / excited / distressed / uncertain / assertive)
    → CortexCouncilRecommendation (neuromodulator + synthesis_intensity)
```

**Cortex Council synthesis commands:**

| Emotion | Neuromodulator | Command |
|---|---|---|
| calm | serotonin_stabilise | `MAINTAIN_BASELINE` |
| excited | dopamine_temper | `TEMPER_AROUSAL` |
| distressed | cortisol_reduce | `REDUCE_STRESS_SIGNAL` |
| uncertain | acetylcholine_boost | `BOOST_CLARITY` |
| assertive | norepinephrine_calibrate | `CALIBRATE_DRIVE` |

---

### TWINBRAiN

Real-time **compassion response generator** — evolves by the millisecond in differential combinational time spaces.

- `CompassionInventory` stores all prior response patterns indexed by emotional trigger + situational tags (Jaccard similarity lookup)
- `generate_responses()` returns inventory matches supplemented by template-derived responses with personalised context injection
- `record_outcome()` closes the feedback loop: effective responses score +0.10, ineffective −0.10
- Inventory grows indefinitely; older patterns remain auditable

---

## Hardware Layer

| Component | Details |
|---|---|
| **ESP32** | WiFi + BLE 5 + UART GPS — managed via HTTP API and OTA |
| **Raspberry Pi** | Host orchestrator — runs natively, no hardware deps |
| **GPS Module** | NMEA 0183 on UART2 — TinyGPS++ parser |
| **Frequency Range** | 2.4 GHz / 5 GHz / 868 MHz / 915 MHz / LoRa |

---

## Quick Start

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure

```bash
cp config/secrets.yaml.example config/secrets.yaml
# Edit config/secrets.yaml with your API keys
# Edit config/devices.yaml with your ESP32 IP addresses
```

### 3. Run the server

```bash
python main.py --mode server --port 8000
```

- REST API docs: http://localhost:8000/docs
- WebSocket: `ws://localhost:8000/ws/telemetry`

### 4. Run the demo (no hardware needed)

```bash
python main.py --mode demo
```

### 5. Interactive CLI

```bash
python main.py --mode cli
```

---

## Configuration

`config/default.yaml` — all settings with annotated defaults:

```yaml
# CHAiMERA3sp routing
ai_agent:
  chaimera3sp:
    strategy: first          # first | fallback | broadcast
    priority: [watsonx, kimi, kai9000, manus]
    providers:
     watsonx:
       endpoint: ""         # IBM watsonx.ai generation URL
       project_id: ""       # set via WATSONX_PROJECT_ID env var
       model_id: "ibm/granite-13b-instruct-v2"
     kimi:
       endpoint: "https://api.moonshot.cn/v1"
       model: "kimi-2.6"
     kai9000:
       endpoint: ""         # self-hosted inference URL
     manus:
       endpoint: ""         # Manus AI API base
```

Secret keys (api_key, project_id, connection strings) go in `config/secrets.yaml` — never committed.

---

## REST & WebSocket API

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/status` | Orchestrator status |
| GET | `/api/v1/devices` | List all devices |
| POST | `/api/v1/devices` | Register a device |
| DELETE | `/api/v1/devices/{id}` | Remove a device |
| POST | `/api/v1/devices/{id}/ping` | Ping a device |
| GET | `/api/v1/agents` | List agents and metrics |
| POST | `/api/v1/tasks` | Dispatch task to an agent |
| POST | `/api/v1/tasks/broadcast` | Broadcast to all agents of a type |
| GET | `/api/v1/tasks/{id}` | Get task result |
| POST | `/api/v1/firmware/build` | Build firmware on-the-fly |
| POST | `/api/v1/firmware/flash/{device_id}` | OTA flash a device |
| POST | `/api/v1/ai/optimise/{device_id}` | AI-driven optimisation |
| POST | `/api/v1/ai/research` | AI research query via CHAiMERA3sp |

**WebSocket** `ws://host/ws/telemetry` — streams device telemetry and agent events in real time.

---

## ESP32 Firmware

Templates in `firmware/templates/`:

| File | Description |
|---|---|
| `base.cpp` | Core HTTP command server, OTA stub, frequency/modulation state |
| `wifi.cpp` | WiFi STA, HTTP server, network scan, RSSI, OTA via HTTPUpdate |
| `ble.cpp` | BLE 5 advertising, GATT server, Nordic UART-compatible service |
| `gps.cpp` | NMEA parsing via TinyGPS++, UART2 GPS support |

Build on-the-fly:
```bash
curl -X POST http://localhost:8000/api/v1/firmware/build \
  -H 'Content-Type: application/json' \
  -d '{"template":"base","features":["wifi","ble","gps"],"version":"1.0.0"}'
```

---

## Mobile App

React Native companion app (`app/`):

- **Dashboard** — live WebSocket status of all devices and agents
- **Devices** — register, ping, and manage ESP32 modules
- **Frequency** — band scan, lock, fine-tune, fleet sync
- **Firmware** — build and flash firmware on-the-fly
- **Settings** — orchestrator host, cloud endpoint, preferences

```bash
cd app && npm install
npm run android   # or: npm run ios
```

---

## Cloud Integration

```yaml
# config/default.yaml
comms_agent:
  cloud_connector: "aws"    # http | aws | gcp | azure
  cloud_endpoint: "https://your-endpoint.amazonaws.com"
```

---

## Testing

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -q
# 478 tests — all passing
```

Test files:

| File | Coverage |
|---|---|
| `test_tlc.py` | TLC waking, dream-state, predictive, voice, TWINBRAiN |
| `test_chaimera3sp.py` | Providers, routing strategies, tracery subsystem |
| `test_hiai.py` | VAD model, profiler, ambiguity resolver |
| `test_agents.py` | All 5 agents |
| `test_orchestrator.py` | Orchestrator core, scheduler, device management |
| `test_firmware.py` | Builder and flasher |
| `test_cloud.py` | Cloud connectors |
| `test_vault.py` | Secret vault |

---

## Directory Structure

```
├── orchestrator/        Core orchestrator engine
├── agents/              Frequency, Modulation, Firmware, Comms, AI agents
├── ai/
│   ├── tlc.py           Technical Learning Cortex (TLC)
│   ├── hiai.py          HiAi — VAD + profiler + ambiguity resolver
│   ├── chaimera3sp.py   CHAiMERA3sp router + tracery subsystem
│   ├── emotional_state.py  NRC EmoLex + VAD model
│   ├── user_profile.py  Rolling behavioural profile store
│   ├── ambiguity.py     Gricean ambiguity detector + resolver
│   ├── frequency_lock.py  PID frequency lock controller
│   └── automation.py    Automation engine
├── comms/               WiFi, BLE, GPS/GNSS managers
├── firmware/            Builder, OTA flasher, ESP32 C++ templates
├── cloud/               HTTP, AWS, GCP, Azure connectors
├── api/                 FastAPI REST + WebSocket server
├── logging_system/      Structured logging + telemetry monitor
├── lib/                 Secrets vault
├── app/                 React Native mobile app
├── config/              YAML configuration files
├── tests/               pytest test suite (478 tests)
├── MARKDOWN.md          Model insertion algorithm
├── MODEL_CARD.md        Hugging Face model card
└── main.py              Entry point (server / demo / cli)
```

---

## Development

```bash
# Run all tests
python -m pytest tests/ -v

# Run server in debug mode
python main.py --mode server --log-level DEBUG

# Interactive CLI
python main.py --mode cli
```

---

*NAi\_iNFINITEAi — where hardware orchestration meets fluid cognitive intelligence.*

