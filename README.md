# MotorGuard — Industrial Multi-Motor Monitoring & Maintenance Platform

[![Phase](https://img.shields.io/badge/Phase-0%3A%20Architecture%20%26%20Foundation-blue.svg)](#roadmap)
[![Architecture](https://img.shields.io/badge/Topology-Local--First%20Gateway-green.svg)](#architecture)
[![License](https://img.shields.io/badge/License-Proprietary-orange.svg)](#)

**MotorGuard** is an industrial condition-monitoring and predictive maintenance platform designed for multi-motor DC fleets (e.g. RS-775 motors). MotorGuard utilizes a **local-first edge gateway topology**: physical ESP32 nodes acquire vibration, temperature, and current readings, execute on-device TinyML inference, and publish telemetry over MQTT to a local on-premise gateway.

The local gateway operates autonomously without requiring an active internet connection, ensuring continuous monitoring, logging, and threshold alerting even during wide-area network outages. When wide-area connectivity is available, authorized users access the system remotely through an authenticated gateway or secure VPN.

---

## Architecture Overview

```
                              [ Physical Motor Fleet ]
       +--------------------+  +--------------------+  +--------------------+
       | Motor 001 + ESP32  |  | Motor 002 + ESP32  |  | Motor N + ESP32    |
       |  DHT11, ADXL345,   |  |  DHT11, ADXL345,   |  |  DHT11, ADXL345,   |
       |  ACS712, TinyML    |  |  ACS712, TinyML    |  |  ACS712, TinyML    |
       +---------+----------+  +---------+----------+  +---------+----------+
                 |                       |                       |
                 +-----------------------+-----------------------+
                                         |
                        Local Wi-Fi / Ethernet LAN (MQTT)
                                         |
                                         v
                      +-------------------------------------+
                      |    Local MotorGuard Edge Gateway    |
                      |   (Always-on PC / Industrial NUC)   |
                      |                                     |
                      |  +-------------------------------+  |
                      |  | Eclipse Mosquitto MQTT Broker |  |
                      |  +---------------+---------------+  |
                      |                  |                  |
                      |                  v                  |
                      |  +-------------------------------+  |
                      |  | FastAPI Ingestion & Rules     |  |
                      |  +-------+---------------+-------+  |
                      |          |               |          |
                      |          v               v          |
                      |     +---------+     +---------+     |
                      |     | MongoDB |     | Web-    |     |
                      |     | Storage |     | Sockets |     |
                      |     +---------+     +----+----+     |
                      +--------------------------|----------+
                                                 |
                       +-------------------------+-------------------------+
                       |                                                   |
                       v                                                   v
          [ Local Network Users ]                             [ Remote Secure Access ]
          Browser on Factory LAN                              Authenticated Reverse Proxy
          (http://gateway.local:5173)                         / WireGuard VPN
```

---

## Technology Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend** | React 18 + Vite + TypeScript | Industrial web dashboard, live gauges, historical charts |
| **Backend API** | Python 3.11+ + FastAPI | High-performance asynchronous API, WebSockets hub, rules engine |
| **Messaging** | Eclipse Mosquitto (MQTT 3.1.1/5.0) | Central local edge message bus with QoS 1 & LWT |
| **Database** | MongoDB 7.0 | Document store for motors, devices, telemetry, alerts, maintenance |
| **Edge Hardware** | ESP32 DevKit + C++ (Arduino) | Embedded microcontroller acquiring physical sensor telemetry |
| **Sensors** | DHT11 + ADXL345 + ACS712-20A | Temperature, 3-axis dynamic vibration RMS ($g$), current ($A$) |
| **TinyML** | Edge Impulse (TFLite Micro EON) | On-device 3-axis motor health classifier (healthy, warning, critical)|
| **Simulator** | Python + paho-mqtt | Secondary virtual motor diagnostic tool for testing degradation |
| **Infrastructure**| Docker Compose | Reproducible local gateway deployment with container health checks |

---

## Repository Structure

```
MotorGuard/
├── .env.example                       # Complete environment variable specification template
├── .gitignore                          # Multi-runtime ignore (Python, Node, C++, Docker, OS, secrets)
├── requirements.txt                    # Root Python dependencies for all platform services
├── TEAM_SETUP.md                       # Comprehensive team onboarding & quick-start setup guide
├── README.md                           # Master project documentation
├── docs/
│   ├── architecture.md                 # System components, topology, and data flow diagrams
│   ├── telemetry-contract.md           # Versioned telemetry JSON schema, validation rules, payload examples
│   ├── mqtt-specification.md           # Topic namespace, QoS, LWT, deduplication, and reconnection logic
│   ├── data-model.md                   # MongoDB collections, schemas, indexes, and relationships
│   ├── environment-variables.md        # Detailed env-var documentation for dev & prod
│   ├── security-checklist.md           # Auth, transport security, port exposure, secrets, Wi-Fi provisioning
│   ├── hardware-tinyml-risks.md        # ACS712 electrical safety, voltage dividers, ADXL345 RMS, TinyML bounds
│   ├── local-setup-windows.md          # Step-by-step PowerShell setup instructions for Windows
│   ├── deployment-strategy.md          # Local -> Docker -> Staging -> Production migration blueprint
│   └── roadmap-acceptance-tests.md     # Phase-specific milestones and exact acceptance tests
├── infrastructure/
│   ├── docker-compose.yml              # Scaffolding Compose file with health checks & placeholders marked
│   └── mosquitto/
│       └── mosquitto.conf              # Mosquitto broker configuration for development
├── backend/                            # FastAPI backend service (Phase 1)
├── frontend/                           # React + Vite + TypeScript dashboard (Phase 3)
├── simulator/                          # Virtual motor simulator (Phase 2)
├── firmware/                           # ESP32 sketches & Edge Impulse library (Phase 5 & 6)
├── data/                               # Preserved datasets for model validation
└── tests/                              # Integration & unit test suites
```

---

## Phased Implementation Roadmap

- [x] **Phase 0: Architecture, Workspace Setup & Foundation** *(Complete)*
- [x] **Phase 1: Application Foundation & Health Checks** *(Complete)*
- [x] **Phase 2: MQTT Broker & MongoDB Ingestion** *(Complete)*
- [x] **Phase 3: Real-Time Dashboard & Asset Views** *(Complete)*
- [x] **Phase 4: RBAC, Alerts & Maintenance Records** *(Complete)*
- [x] **Phase 5: Physical ESP32 Hardware Integration** *(Complete)*
- [ ] **Phase 6: Edge Impulse On-Device TinyML**
- [ ] **Phase 7: Reliability & Failure Testing**
- [ ] **Phase 8: Production Gateway Release & Remote Access**

---

## Documentation Index

- [Team Quick-Start & Onboarding Guide](TEAM_SETUP.md)
- [Architecture Specification](docs/architecture.md)
- [Telemetry Contract (v1.0.0)](docs/telemetry-contract.md)
- [MQTT Topic & Messaging Specification](docs/mqtt-specification.md)
- [Persistent Data Model & MongoDB Schemas](docs/data-model.md)
- [Environment Variables Inventory](docs/environment-variables.md)
- [Security Threat Checklist](docs/security-checklist.md)
- [Hardware Safety & TinyML Validation](docs/hardware-tinyml-risks.md)
- [Windows Local Setup Guide](docs/local-setup-windows.md)
- [Production Deployment Strategy](docs/deployment-strategy.md)
- [Implementation Roadmap & Acceptance Criteria](docs/roadmap-acceptance-tests.md)

---

## Quick Start & Local Setup

### Prerequisites
- **Python**: 3.11+ (with `pip` and `venv`)
- **Node.js**: 20 LTS or 18+ (with `npm`)
- **MongoDB**: 7.0+ (Local community server or Docker container)
- **MQTT Broker**: Eclipse Mosquitto or bundled Python broker (`infrastructure/local_broker.py`)

### 1. Environment Configuration
Copy the template file to `.env`:
```powershell
Copy-Item .env.example .env
```
*(Default settings connect to `localhost:8000`, `127.0.0.1:1883`, and `127.0.0.1:27017` out of the box).*

### 2. Backend & Dependencies Setup
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Frontend Installation & Build
```powershell
cd frontend
npm install
npm run build
cd ..
```

### 4. Running the Complete Stack
You can launch the full development suite with the one-click PowerShell launcher:
```powershell
.\run_dev.ps1
```
Or start each service individually:
- **Broker**: `python infrastructure/local_broker.py`
- **FastAPI Backend**: `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload`
- **React Dashboard**: `cd frontend && npm run dev`
- **Virtual Simulator**: `python simulator/simulator.py`

Access points:
- **Web Dashboard**: [http://localhost:5173](http://localhost:5173) (Default Admin: `admin` / `adminpassword123`)
- **API Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc API Reference**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## ESP32 Hardware & Sensor Connections

The edge firmware (`firmware/MotorGuard_ESP32_Inference.ino`) samples physical sensor data from DC motor test benches:

| Component | Interface / Pins | Details & Calibration |
| :--- | :--- | :--- |
| **ESP32 DevKit** | Wi-Fi SoftAP / Serial | Default AP: `MotorGuard-ESP32-AP` (Password: `MotorGuard123`), IP: `192.168.4.1` |
| **ADXL345** | I2C0: SDA `GPIO 21`, SCL `GPIO 22` | 3-axis vibration sampling at 100 Hz, RMS calculation ($g$) |
| **DHT11** | 1-Wire: `GPIO 4` | Ambient motor casing temperature (°C) & relative humidity (%) |
| **ACS712-20A** | Analog: `GPIO 34` (ADC1) | Current sensing via 10k/20k resistor voltage divider (ratio 0.667 to protect 3.3V ADC) |
| **SH1106 OLED** | I2C1: SDA `GPIO 32`, SCL `GPIO 33` | 128x64 local edge telemetry display |
| **Buzzer / Alarm** | Digital: `GPIO 25` | Hardware audible alert trigger on critical overcurrent/thermal faults |

---

## Machine Learning & Edge Impulse TinyML

- **On-Device Inference**: Firmware includes headers from Edge Impulse (`MotoGuard_Motor_Health_inferencing.h`), calculating spectral vibration features and spectral power to classify motor health into `Healthy`, `Warning`, or `Critical`.
- **Pre-trained Impulse**: Pre-packaged library archive available in `firmware/ei-motoguard-motor-health-arduino-1.0.1-impulse-#1.zip`.
- **Training Datasets**: Synthetic and test-bench run datasets are archived in `data/` for feature extraction and retraining.

---

## Verification & Automated Testing

Run the full automated test suite (63 integration & unit tests):
```powershell
pytest -v
```

Run frontend verification and production compilation:
```powershell
npm --prefix frontend run build
```

---

## Docker Deployment

To deploy the infrastructure components using Docker Compose:
```bash
docker compose -f infrastructure/docker-compose.yml up -d
```
Includes:
- **MongoDB 7.0** with persistent storage volume (`mongodb_data`)
- **Eclipse Mosquitto 2.0** with custom configuration (`infrastructure/mosquitto/mosquitto.conf`)

---

## Current Status & Known Limitations

- **Completed & Verified**:
  - Full FastAPI gateway with async telemetry ingestion, rule evaluations, and WebSockets.
  - Role-Based Access Control (RBAC) with JWT auth (`admin`, `manager`, `technician`, `viewer`).
  - Alert Operations Center with timeline, severity badges, and acknowledgment/resolution workflows.
  - Real-time React 18 dashboard with 3D cyber twin viewer, live gauges, and historical analytics.
  - ESP32 hardware firmware with SoftAP server and serial bridge ingestion script (`infrastructure/serial_bridge.py`).
  - 100% automated test suite passing (63 unit & integration tests).
- **Simulated & In-Progress**:
  - Motor degradation scenarios in `simulator/simulator.py` simulate bearing wear and overcurrent faults for testing without damaging physical motors.
  - Edge Impulse on-device model runs embedded on ESP32; hardware multi-load endurance benchmark calibration is actively running in laboratory test benches.
