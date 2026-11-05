# Final QA Report

**Audit Role:** AGENT 10 — FINAL QA AUDITOR  
**Report Artifact Location:** `reports/FINAL_QA_REPORT.md`  
**Target Repository:** `c:\Users\gopes\Downloads\project`  
**Audit Completion Date:** October 2, 2026  
**Operating Mode:** Read-Only Audit & Multi-Agent Synthesis  
**Input Agent Reports Reconciled:**
1. `reports/CODE_REVIEW.md` (Agent 1 — Static Code Review & Code Quality)
2. `reports/FRONTEND_QA.md` (Agent 2 — Frontend Application & SCADA QA)
3. `reports/BACKEND_QA.md` (Agent 3 — Backend API & Event Loop QA)
4. `reports/DATABASE_QA.md` (Agent 4 — Database QA & Data Architecture)
5. `reports/IOT_MQTT_QA.md` (Agent 5 — IoT, Firmware & MQTT Pipeline QA)
6. `reports/ML_QA.md` (Agent 6 — Machine Learning & Pipeline Integrity QA)
7. `reports/SECURITY_QA.md` (Agent 7 — Defensive Security, RBAC & STRIDE QA)
8. `reports/PERFORMANCE_QA.md` (Agent 8 — Performance & Scalability QA)
9. `reports/INTEGRATION_QA.md` (Agent 9 — End-to-End System Integration QA)

---

## 1. System Tested

The target under test is the **Motor Health Monitoring & Predictive Maintenance System (Motor-Guard)**. The platform is designed for industrial condition monitoring of electric motors, combining edge sensing, TinyML neural network inference, cloud heuristics, real-time message brokering, time-series persistence, and a browser-based SCADA supervisory dashboard.

### 1.1 Hardware & Embedded Specifications
- **Target Microcontroller:** Espressif ESP32 (ESP32-WROOM-32 / NodeMCU dual-core Xtensa LX6 @ 240 MHz, 520 KB SRAM, 4 MB Flash).
- **Embedded Firmware Environment:** Arduino Core for ESP32 (`firmware/esp32_motor_node.ino` and `firmware/esp32_motor_node/esp32_motor_node.ino`).
- **Edge TinyML Model Engine:** Edge Impulse C++ SDK (TensorFlow Lite Micro with EON Compiler, int8 quantized neural network in `edge_impulse_model/Gopesh_rathinam-project-1_inferencing/`).
- **Sensor Suite:**
  - *Temperature:* Dallas Semiconductor DS18B20 1-Wire Digital Thermometer connected to GPIO 4 (utilizing non-blocking async conversion).
  - *Vibration / Acceleration:* Analog Devices ADXL345 3-Axis Digital Accelerometer on I2C address `0x53` (SDA: GPIO 21, SCL: GPIO 22). *Note: System documentation in `firmware/README.md` diverges, specifying MPU6050 at `0x68`.*
  - *Current:* Allegro ACS712-05B Hall-Effect Current Sensor connected to analog input GPIO 34 (ADC1_CH6). Powered by 5.0V VCC.
  - *Local Display:* SSD1306 128×64 I2C Monochrome OLED Display on I2C address `0x3C`.
  - *Actuator / Indicators:* Relay output on GPIO 15; Status LED on GPIO 2.

### 1.2 Gateway & Ingestion Specifications
- **Message Broker:** Eclipse Mosquitto MQTT 3.1.1 Broker listening on TCP port 1883 (`motors/MTR-001/data` and `motors/MTR-001/cmd`).
- **USB Serial Bridge:** Python 3.12 script (`backend_example/serial_bridge.py`) utilizing PySerial at 115,200 baud, converting serial lines to HTTP POST requests.
- **REST Telemetry Gateway:** FastAPI ingestion routes (`POST /api/telemetry` and `POST /api/test/sensor-data`).

### 1.3 Backend & Analytics Specifications
- **Application Server:** FastAPI (v0.110+) running under Uvicorn ASGI server on Python 3.12 (`backend_example/main.py`).
- **Concurrency Model:** Python asyncio event loop integrated with Paho-MQTT threaded network loop via `asyncio.run_coroutine_threadsafe`.
- **Database Engine:** MongoDB 7.0+ accessed via the Motor (`motor.motor_asyncio.AsyncIOMotorClient`) asynchronous driver in `backend_example/database.py`. Database name: `motor_health_db`.
- **Predictive Analytics Engine:** In-memory procedural heuristics (`calculate_rul_and_health` and `evaluate_alerts`) calculating health score, failure probability, and remaining useful life (RUL).

### 1.4 Frontend Supervisory Dashboard Specifications
- **Client Application:** React 19 Single Page Application (`motor-dashboard/`).
- **Build & Dev Tooling:** Vite 6 with `@vitejs/plugin-react` and `@tailwindcss/vite` 4.
- **3D Digital Twin Engine:** Three.js (`three: ^0.174.0`) WebGL canvas displaying a real-time rotating 3D motor with thermal beacon shaders.
- **Data Visualization:** Recharts (`recharts: ^2.15.1`) rendering SVG multi-sensor telemetry trend graphs.
- **Client-Side State:** React Context API (`AppContext.jsx`) with browser `localStorage` persistence and WebSocket subscription to `ws://localhost:8000/ws/live`.

---

## 2. Architecture

```
[ Physical Electric Motor & Sensors ]
   ├── DS18B20 Temperature (GPIO 4, 1-Wire)
   ├── ADXL345 Accelerometer (I2C 0x53)
   └── ACS712 Current Sensor (GPIO 34 ADC)
                    │
                    ▼
[ ESP32 Edge Computing Node ]
   ├── FreeRTOS Main Loop (100 Hz / 10ms sampling)
   ├── Edge Impulse TinyML Engine (TFLite Micro int8, 300-sample frame)
   ├── SSD1306 Local Display (I2C 0x3C)
   ├── Wi-Fi Station (802.11 b/g/n)
   └── PubSubClient MQTT Publisher
          │                           │
   (MQTT TCP 1883)             (USB UART 115200)
          │                           │
          ▼                           ▼
[ Mosquitto MQTT Broker ]      [ Python Serial Bridge ]
   `motors/MTR-001/data`          (`serial_bridge.py`)
          │                           │
          └───────────┬───────────────┘
                      ▼
[ FastAPI Ingestion Gateway (main.py) ]
   ├── Paho-MQTT Ingestion Thread ──► `asyncio.run_coroutine_threadsafe`
   ├── REST Ingestion Gateway (`POST /api/telemetry`)
   ├── Predictive Heuristic Engine (`calculate_rul_and_health`)
   ├── Rule-Based Alert Classifier (`evaluate_alerts`)
   └── In-Memory State Cache (`latest_readings`, `active_alerts`)
          │                                   │
          ▼                                   ▼
[ MongoDB Database (motor_health_db) ]    [ WebSocket Server (/ws/live) ]
   ├── `telemetry` Collection                │ (Raw JSON Broadcast)
   ├── `alerts` Collection                   ▼
   └── `users` Collection                 [ React 19 SCADA Dashboard ]
                                             ├── Three.js 3D Digital Twin
                                             ├── Live Telemetry Gauges & Charts
                                             └── LocalStorage Auth & Mock State
```

### 2.1 Communication & Data Flow Mechanics
1. **Edge Sampling & TinyML Inference:** The ESP32 collects temperature, vibration magnitude, and current at 100 Hz. Features are loaded into an array of size 300 ($100 \text{ cycles} \times 3 \text{ features}$). Upon reaching 300 samples, the Edge Impulse neural network executes, generating probability distributions across classes (`critical`, `fault`, `normal`).
2. **Telemetry Serialization & Uplink:** Telemetry is serialized using `snprintf` into a JSON document and published to MQTT topic `motors/MTR-001/data` every 250 ms (4 Hz) or pushed across USB UART.
3. **Backend Ingestion & Feature Calculation:** The FastAPI backend receives the payload either through the MQTT subscriber callback or via HTTP POST. It derives health scores, failure probabilities, and RUL estimations.
4. **Persistence & Broadcasting:** Telemetry and generated alert records are asynchronously inserted into MongoDB. The enriched JSON document is simultaneously broadcast to connected WebSocket clients at `/ws/live`.
5. **Supervisory Presentation:** The React frontend visualizes live sensor signals, updates 3D model status beacons, and plots historical trends.

---

## 3. Test Coverage

### 3.1 Existing Repository Test Inventory
A rigorous scan across the entire project repository (`c:\Users\gopes\Downloads\project`) identified **only a single automated test script**:
- **Script Location:** `backend_example/test_pipeline.py` (70 lines of Python code).
- **Scope of Existing Script:**
  - Starts FastAPI lifecycle (`startup_event`).
  - Executes `GET /` and `GET /api/system/status`.
  - Executes `POST /api/test/sensor-data` with nominal values (`vibration_mm_s: 3.2`, `temperature_c: 35.5`, `current_a: 0.42`, `anomaly_score: 0.12`).
  - Checks if a telemetry document was saved in MongoDB.
  - Executes `POST /api/test/sensor-data` with critical values (`vibration_mm_s: 7.8`, `temperature_c: 85.0`, `current_a: 15.2`, `anomaly_score: 0.75`).
  - Checks if an alert was saved in MongoDB.
  - Shuts down lifecycle and prints `=== ALL TESTS COMPLETED 100% CLEANLY ===`.

### 3.2 Empirical Test Coverage Metrics
| Subsystem / Tier | Automated Unit Tests | Automated Integration Tests | End-to-End Tests | Code / Path Coverage |
|---|---|---|---|---|
| **Embedded Firmware (`firmware/`)** | 0 | 0 | 0 | **0.0%** |
| **Edge ML (`edge_impulse_model/`)** | 0 | 0 | 0 | **0.0%** |
| **Backend API (`backend_example/main.py`)** | 0 | 1 (`test_pipeline.py` partial) | 0 | **~14.3%** (2 of 7 endpoints exercised) |
| **Database Layer (`database.py`)** | 0 | 1 (`test_pipeline.py` partial) | 0 | **25.0%** (2 of 8 query methods exercised) |
| **Frontend App (`motor-dashboard/src/`)** | 0 | 0 | 0 | **0.0%** (No Vitest/Jest/Playwright suites) |
| **Total System Test Coverage** | **0** | **1** | **0** | **< 3.0%** |

### 3.3 Critical Test Omissions & False Positives in Existing Pipeline
1. **Omission of Critical Endpoints:** `GET /api/users`, `GET /api/motors/{id}/history`, `GET /api/alerts`, `POST /api/motors/{id}/control`, and `/ws/live` are completely omitted from the test script.
2. **Zero Negative Input Validation Tests:** The test script provides zero validation for non-numeric data, missing fields, or empty JSON dictionaries.
3. **Fragility Under Offline MongoDB:** If MongoDB is offline, line 61 of `test_pipeline.py` (`latest_alert = await db["alerts"].find_one(...)`) raises an unhandled `TypeError: 'NoneType' object is not subscriptable`, causing the test suite to crash catastrophically.
4. **False Positive "100% Clean" Declaration:** Line 66 prints `=== ALL TESTS COMPLETED 100% CLEANLY ===`, creating false confidence while critical crash bugs in `GET /api/users` and motor control endpoints remain completely untested.

---

## 4. Critical Findings

The findings below represent severe defects that cause application crashes, data loss, complete security compromise, silent operational drops, or physical equipment hazards.

```
+----------------------------------------------------------------------------------------------------+
|                                    CRITICAL FINDINGS MATRIX                                        |
+---------+--------------------+------------------------------------+--------------------------------+
| ID      | Domain             | File & Line Reference              | Summary Defect                 |
+---------+--------------------+------------------------------------+--------------------------------+
| CRIT-01 | Security / RBAC    | backend_example/main.py:318-408    | Zero Authentication & RBAC     |
| CRIT-02 | Runtime Crash      | backend_example/main.py:389-400    | MongoDB BSON ObjectId Crash    |
| CRIT-03 | Frontend Crash     | motor-dashboard/Alerts.jsx:54      | Unchecked motor_name Property  |
| CRIT-04 | Network / IoT      | firmware/esp32_motor_node.ino:248  | PubSubClient Buffer Overflow   |
| CRIT-05 | Client Auth        | motor-dashboard/AppContext.jsx:21  | Admin Auto-Login Bypass        |
| CRIT-06 | Client Auth        | motor-dashboard/AppContext.jsx:32  | Broken Logout Persistence      |
| CRIT-07 | Integration        | motor-dashboard/src/pages/*        | Total Absence of Backend REST  |
| CRIT-08 | Performance        | backend_example/main.py:63-70      | Synchronous Serial WS Loop     |
| CRIT-09 | Resiliency         | backend_example/main.py:223-229    | Database Outage Freezes WS     |
| CRIT-10 | Input Validation   | backend_example/main.py:319, 336   | Untyped Dict Input HTTP 500    |
+---------+--------------------+------------------------------------+--------------------------------+
```

### CRIT-01: Zero Authentication & Server-Side Authorization Across All API Endpoints
- **Files:** `backend_example/main.py:318-408`, `backend_example/serial_bridge.py:1-164`.
- **Evidence:** The FastAPI backend does not configure any authentication dependencies (`HTTPBearer`, `OAuth2PasswordBearer`, or API keys). Every REST endpoint (`GET /api/users`, `POST /api/telemetry`, `POST /api/motors/{motor_id}/control`) and the WebSocket endpoint (`/ws/live`) can be accessed anonymously without credentials.
- **Impact:** An attacker on the network can issue arbitrary motor shutdown commands (`EMERGENCY_SHUTDOWN`), dump the complete employee directory, or inject false sensor data that blinds plant operators to catastrophic machine failure.

### CRIT-02: MongoDB BSON `ObjectId` Serialization Crash on `GET /api/users` (HTTP 500)
- **Files:** `backend_example/main.py:389-400`.
- **Evidence:** `cursor = db["users"].find({})` retrieves documents from MongoDB. Unlike the telemetry and alerts endpoints, `find({})` does not project out `_id` (`{"_id": 0}`). When documents contain standard MongoDB `ObjectId` types, FastAPI's default JSON response encoder raises:
  ```text
  TypeError: Object of type ObjectId is not JSON serializable
  ```
  resulting in an unhandled HTTP 500 Internal Server Error.
- **Impact:** The user administration endpoint completely crashes whenever user documents are created via standard database drivers or tools that assign native BSON ObjectIds.

### CRIT-03: Unchecked `motor_name` in Frontend Crashes Entire Alerts Page
- **Files:** `motor-dashboard/src/pages/Alerts.jsx:54`, `backend_example/main.py:126-150`.
- **Evidence:** `Alerts.jsx` line 54 executes:
  ```javascript
  const matchSearch = a.motor_name.toLowerCase().includes(search.toLowerCase())
  ```
  However, backend alerts generated in `main.py` only contain keys: `id`, `motor_id`, `severity`, `sensor`, `message`, `timestamp`, and `status`. The field `motor_name` is omitted entirely.
- **Impact:** When live backend alerts are displayed on the frontend, rendering `Alerts.jsx` throws an unhandled `TypeError: Cannot read properties of undefined (reading 'toLowerCase')`, causing the entire React component tree to crash to a white screen.

### CRIT-04: PubSubClient Buffer Overflow Silently Drops Telemetry Packets
- **Files:** `firmware/esp32_motor_node.ino:8, 248-266`.
- **Evidence:** The standard Nick O'Leary Arduino `PubSubClient` library defines `#define MQTT_MAX_PACKET_SIZE 128` (or 256 in newer versions). The firmware serializes a JSON payload averaging 165–185 bytes:
  ```cpp
  char payload[320];
  snprintf(payload, sizeof(payload), "{\"motor_id\":\"%s\",...}", ...);
  mqttClient.publish(MQTT_TOPIC, payload);
  ```
  With MQTT framing overhead, the packet size reaches 191–211 bytes. On any environment where `PubSubClient` defaults to 128 bytes, `publish()` returns `false` and transmits 0 bytes. The firmware ignores the boolean return value.
- **Impact:** Complete silent loss of telemetry over MQTT. The ESP32 serial monitor logs that data was published, but the broker receives nothing.

### CRIT-05: Frontend Authentication Bypass via Default User Fallback
- **Files:** `motor-dashboard/src/context/AppContext.jsx:21-25`.
- **Evidence:** The authentication context initializes state with:
  ```javascript
  useState(() => {
    const saved = localStorage.getItem('motor_health_user')
    return saved ? JSON.parse(saved) : users[0]
  })
  ```
  `users[0]` is hardcoded as Rajesh Kumar (Role: Administrator).
- **Impact:** Any unauthenticated user visiting the dashboard in a fresh browser session or incognito window is immediately granted Administrator privileges with full access to settings, motor controls, and operational overrides.

### CRIT-06: Broken Logout Session Persistence Across Page Reloads
- **Files:** `motor-dashboard/src/context/AppContext.jsx:32-35`.
- **Evidence:** The logout implementation in `AppContext.jsx`:
  ```javascript
  const logout = () => {
    setCurrentUser(null)
  }
  ```
  The function clears in-memory state but fails to execute `localStorage.removeItem('motor_health_user')`.
- **Impact:** When a user clicks "Logout", they are redirected to `/login`. However, reloading the page or navigating back causes `useState` to read the uncleared `localStorage` token, instantly restoring the logged-in session.

### CRIT-07: Total Absence of Backend REST Integration in Frontend UI
- **Files:** `motor-dashboard/src/pages/*`, `motor-dashboard/src/context/AppContext.jsx`.
- **Evidence:** A full codebase audit of `motor-dashboard/src/` revealed **zero** `fetch()` or `axios` HTTP calls to `http://localhost:8000/api/...`. The frontend relies 100% on static mock arrays from `src/data/mockData.js` for historical graphs, user accounts, maintenance records, and analytics. Only live telemetry overlay is ingested via WebSocket.
- **Impact:** Plant operators view synthetic, fabricated demo data. Changes in the backend database or real historical sensor degradation are never reflected in the dashboard.

### CRIT-08: Synchronous Serial WebSocket Broadcast Loop Freezing Backend
- **Files:** `backend_example/main.py:63-70`.
- **Evidence:** The WebSocket broadcast function:
  ```python
  async def broadcast_ws(payload: dict):
      for connection in list(active_connections):
          try:
              await connection.send_text(json.dumps(payload))
          except Exception as e:
              logger.warning(...)
  ```
  The loop serializes and awaits each client transmission sequentially. Empirical benchmarking shows that at 100 connected clients, this loop introduces 1,558 ms of event loop latency.
- **Impact:** Real-time MQTT telemetry ingestion and incoming HTTP REST requests are blocked for over 1.5 seconds per packet, triggering severe message queuing and eventual timeouts.

### CRIT-09: Database Outage Cascading Latency Trap Freezing Real-Time Streaming
- **Files:** `backend_example/main.py:223-229`, `backend_example/database.py:25, 51-71`.
- **Evidence:** `process_telemetry_payload` sequentially awaits `save_telemetry` and `save_alert` before calling `broadcast_ws`. When MongoDB is unreachable, PyMongo's `serverSelectionTimeoutMS = 5000` causes each call to block for 5.0 seconds. A telemetry packet with 2 alerts blocks the asyncio event loop for 15.0 seconds before broadcasting to WebSocket clients.
- **Impact:** A database network hiccup freezes the entire real-time SCADA monitoring stream, blinding operators during hardware faults.

### CRIT-10: Untyped Telemetry Payload with Zero Validation Causing HTTP 500 Crashes
- **Files:** `backend_example/main.py:319, 336`, `backend_example/main.py:172-190`.
- **Evidence:** `receive_telemetry(payload: Dict[str, Any])` accepts arbitrary dictionaries without Pydantic schema validation. In `process_telemetry_payload`, values are cast via `float(payload.get("vibration_mm_s", 0.0))`. If an incoming payload contains non-numeric values (e.g. `{"vibration_mm_s": "fault"}`), an unhandled `ValueError` crashes the request with HTTP 500. Empty payloads `{}` generate default health scores and insert corrupted records into MongoDB.
- **Impact:** Malformed edge packets crash backend worker processes and pollute database collections with invalid schema structures.

---

## 5. High-Severity Findings

Findings in this category represent serious functional failures, major architectural bugs, hardware electrical hazards, or performance cliffs.

### HIGH-01: Serial Bridge Total Parser Incompatibility
- **Files:** `backend_example/serial_bridge.py:95`, `firmware/esp32_motor_node.ino:270`.
- **Evidence:** `serial_bridge.py` verifies lines using:
  ```python
  if line.startswith("{") and line.endswith("}"):
  ```
  However, the ESP32 firmware prefixes every serial telemetry line:
  ```cpp
  Serial.printf("[MQTT Publish -> %s] %s\n", MQTT_TOPIC, payload);
  ```
- **Impact:** `line.startswith("{")` evaluates to `False` for every single transmitted line. The serial bridge rejects 100% of telemetry data coming across USB COM ports.

### HIGH-02: Missing Bi-Directional Motor Actuation Link in Firmware
- **Files:** `firmware/esp32_motor_node.ino:230-237`, `backend_example/main.py:403-408`.
- **Evidence:** The backend exposes `POST /api/motors/{motor_id}/control` which publishes commands to MQTT topic `motors/{motor_id}/cmd`. However, in `esp32_motor_node.ino`, the MQTT connection logic connects as a pure publisher. It **never calls `mqttClient.subscribe("motors/MTR-001/cmd")`** and registers no MQTT message callback.
- **Impact:** Emergency stop commands, shutdown overrides, and relay resets issued by operators are completely ignored by the physical hardware.

### HIGH-03: False Positive Confirmation on Motor Control Endpoint
- **Files:** `backend_example/main.py:403-408`.
- **Evidence:** In `send_motor_control`, the backend executes `mqtt_client.publish(topic, payload)` and immediately returns HTTP 200 `{"status": "command_published"}` without checking `mqtt_client.is_connected()`.
- **Impact:** If the MQTT broker is offline or disconnected, plant operators receive a successful confirmation that an emergency shutdown was executed, while the command was never sent.

### HIGH-04: REST Anti-Pattern in Motor Control Endpoint Signature
- **Files:** `backend_example/main.py:403-408`.
- **Evidence:** The endpoint signature is:
  ```python
  def send_motor_control(motor_id: str, command: str):
  ```
  In FastAPI, unannotated scalar parameters on POST endpoints are parsed as **URL Query Parameters** (`?command=EMERGENCY_SHUTDOWN`). A standard HTTP POST sending a JSON body `{"command": "EMERGENCY_SHUTDOWN"}` is rejected with `HTTP 422 Unprocessable Entity` ("Field required: query -> command").
- **Impact:** Standard industrial REST clients and API integrations fail when attempting to actuate motor relays.

### HIGH-05: Motor Current is Completely Dead Code in Health & Alert Calculations
- **Files:** `backend_example/main.py:86-93, 126-150`.
- **Evidence:** In `calculate_rul_and_health`:
  ```python
  def calculate_rul_and_health(vibration: float, temperature: float, current: float, anomaly_score: float):
      health = 100.0 - (vibration * 6.5) - (max(0, temperature - 50.0) * 1.2) - (anomaly_score * 30.0)
  ```
  The `current` parameter is accepted into the function but **never used in any calculation**. Furthermore, `evaluate_alerts()` contains zero threshold checks for current.
- **Impact:** A motor experiencing a locked rotor condition drawing 15.2 A (300% overcurrent) is reported as 92.2% healthy with 165 days of remaining life, generating zero electrical overcurrent alerts.

### HIGH-06: 80-Day Cliff Discontinuity in Cloud RUL Prediction Heuristic
- **Files:** `backend_example/main.py:97-106`.
- **Evidence:** The RUL calculation uses a piecewise step function:
  ```python
  if health >= 80.0:
      rul_days = int(90 + (health - 80.0) * 4.5)
  elif health >= 50.0:
      rul_days = int(30 + (health - 50.0) * 1.2)
  ```
  At `health = 80.0`, RUL is calculated as `90 days`. At `health = 79.9`, RUL abruptly plunges to `65 days`.
- **Impact:** A minor 0.1% fluctuation in sensor noise causes an artificial 25-day plunge in equipment remaining life, triggering false maintenance dispatches.

### HIGH-07: Blocking 25ms I2C Display Updates & 6ms ADC Delays Stalling Sampling Loop
- **Files:** `firmware/esp32_motor_node.ino:45, 107-120, 374`.
- **Evidence:** The firmware targets a 100 Hz (10 ms) sampling loop for Edge Impulse. However, `readCurrent()` executes 30 analog reads with `delayMicroseconds(200)` (6.24 ms total). Additionally, `updateDisplay()` calls `display.display()` over 100 kHz I2C, blocking the CPU for 25–30 ms.
- **Impact:** Every 250 ms, the 10 ms sampling loop is stalled for over 30 ms, dropping 3 consecutive samples and distorting the FFT frequency bins required for machine learning vibration analysis.

### HIGH-08: ACS712 5V Analog Output Directly Connected to ESP32 3.3V GPIO
- **Files:** `firmware/esp32_motor_node.ino:54-56`.
- **Evidence:** The ACS712 current sensor is powered by 5.0V VCC and outputs an analog signal centered at 2.5V with a sensitivity of 185 mV/A. Under surge current or fault conditions, output voltage swings up to 4.5V–5.0V directly into GPIO 34. The absolute maximum input rating for ESP32 GPIOs is 3.6V.
- **Impact:** Electrical overstress (EOS) risking permanent destruction of the ESP32 internal ADC multiplexer or microcontroller latch-up.

### HIGH-09: Zero-Voltage Calibration Assumes Motor is OFF During Microcontroller Boot
- **Files:** `firmware/esp32_motor_node.ino:93-105`.
- **Evidence:** In `calibrateCurrentSensor()`, the firmware averages 100 analog readings during `setup()` and assigns `current_offset`.
- **Impact:** If the ESP32 reboots (due to a power dip, brownout, or watchdog reset) while the motor is running, the running current is calibrated as "zero". When the motor stops, current reads as negative; during operation, current reads near zero, corrupting power and energy calculations.

### HIGH-10: Dimensional Arithmetic Error: Converting Acceleration $g$ to $m/s^2$ but Tagging as $mm/s$
- **Files:** `firmware/esp32_motor_node.ino:257`.
- **Evidence:** Line 257 executes: `vibration * 9.81f`. Multiplying acceleration in $g$ by $9.81$ yields acceleration in $\text{m/s}^2$. However, the JSON payload labels the field `"vibration_mm_s"` (velocity in $\text{mm/s}$).
- **Impact:** ISO 10816 condition monitoring standards define vibration severity using RMS velocity ($\text{mm/s}$), not acceleration ($\text{m/s}^2$). Comparing raw $\text{m/s}^2$ against ISO velocity thresholds is physically invalid.

### HIGH-11: Three.js GPU Memory Leak & 60 FPS React `setState` Loop
- **Files:** `motor-dashboard/src/components/3d/IndustrialMotor3D.jsx:534-574`.
- **Evidence:** The 3D motor component executes React `setState` inside `requestAnimationFrame` at 60 FPS. Furthermore, on component unmount, Three.js geometries, textures, materials, and WebGL render targets are never disposed.
- **Impact:** CPU utilization spikes to 100% on a single core; opening and navigating away from the dashboard causes cumulative GPU VRAM leaks that eventually crash the browser tab.

### HIGH-12: Plaintext Passwords in `localStorage` and Hardcoded Secrets in Firmware
- **Files:** `motor-dashboard/src/pages/Users.jsx:37-76`, `firmware/esp32_motor_node.ino:16-20`.
- **Evidence:** User records stored in browser `localStorage` contain plaintext passwords (`"password123"`). Microcontroller firmware hardcodes Wi-Fi SSID, WPA2 passphrase, and MQTT server IP.
- **Impact:** Any client-side XSS vulnerability allows instant exfiltration of credentials; inspecting the compiled firmware binary reveals internal plant network credentials.

### HIGH-13: Compound Index Prefix Rule Violation on MongoDB `alerts` Collection
- **Files:** `backend_example/database.py:35`, `backend_example/main.py:376-388`.
- **Evidence:** `database.py` creates a compound index `[("motor_id", 1), ("timestamp", -1)]`. However, `main.py` queries `GET /api/alerts` using `find({}).sort("timestamp", -1)`.
- **Impact:** In MongoDB, a compound index cannot be used for sorting or filtering if the leading index prefix (`motor_id`) is omitted. MongoDB executes a full collection scan (`COLLSCAN`) and sorts in RAM, exhausting database memory as alert volume grows.

### HIGH-14: Cross-Tier Vibration & Temperature Threshold Contradictions
- **Files:** `backend_example/main.py:126-150`, `motor-dashboard/src/pages/LiveMonitoring.jsx:16-24`.
- **Evidence:** Backend `evaluate_alerts` defines vibration thresholds as Warning: `5.0 mm/s`, Critical: `7.0 mm/s`. Frontend `LiveMonitoring.jsx` defines thresholds as Warning: `0.70 mm/s`, Critical: `1.10 mm/s`.
- **Impact:** When the ESP32 publishes normal vibration of `1.2 mm/s`, the backend evaluates the motor as healthy, while the frontend dashboard renders a flashing red critical hazard alert.

---

## 6. Medium-Severity Findings

Findings in this category represent resource leaks, missing UI routes, state handling discrepancies, and edge case failures.

### MED-01: WebSocket Client Disconnection Memory Leak in `broadcast_ws`
- **Files:** `backend_example/main.py:63-70`.
- **Evidence:** When a WebSocket client disconnects abruptly, `await connection.send_text(...)` raises an exception. The exception handler logs a warning but never executes `active_connections.remove(connection)`.
- **Impact:** Dead client sockets remain in memory indefinitely, causing `active_connections` to grow monotonically and wasting CPU cycles iterating over dead sockets.

### MED-02: Unbounded In-Memory `active_alerts` Growth
- **Files:** `backend_example/main.py:51, 221`.
- **Evidence:** `active_alerts.append(alert)` appends every generated alert into a Python list in RAM without any maximum size limit, eviction policy, or time-to-live (TTL).
- **Impact:** In an industrial environment experiencing an alert storm (e.g. high vibration), the list consumes unbounded RAM, eventually causing the Python process to crash via OS OOM-killer.

### MED-03: Timestamps Stored as ISO Strings Instead of Native BSON Date
- **Files:** `backend_example/main.py:209`, `backend_example/database.py:34-35`.
- **Evidence:** Timestamps are stored as ISO 8601 strings (`datetime.now(timezone.utc).isoformat()`).
- **Impact:** String timestamps consume 35 bytes instead of 8 bytes (300% storage penalty), prevent MongoDB TTL expiry indexes, and risk lexicographical sort errors across timezones.

### MED-04: In-Memory Slicing Overhead `records[::-1]` on History Endpoints
- **Files:** `backend_example/main.py:370`.
- **Evidence:** `records = await cursor.to_list(length=limit)` retrieves records sorted descending, then duplicates the entire list in memory using `return records[::-1]`.
- **Impact:** Unnecessary CPU and memory overhead during high-frequency API polling.

### MED-05: Missing Routes in Sidebar Navigation (`/edge-impulse` and `/devices`)
- **Files:** `motor-dashboard/src/components/layout/Sidebar.jsx:22-35`, `motor-dashboard/src/App.jsx:32-33`.
- **Evidence:** React Router defines routes for `/edge-impulse` and `/devices`, but neither link is included in the sidebar navigation menu.
- **Impact:** Plant operators cannot access the Edge Impulse ML inspection page or the ESP32 device management console through standard UI navigation.

### MED-06: Inoperative UI Actions in Reports and Maintenance Pages
- **Files:** `motor-dashboard/src/pages/Reports.jsx:92-120`, `motor-dashboard/src/pages/Maintenance.jsx:45-80`.
- **Evidence:** "Download PDF" and "Generate New Report" buttons in `Reports.jsx` lack `onClick` handlers or trigger mock timeouts without generating files. Maintenance work order submission does not persist.
- **Impact:** Operators cannot export compliance audit documentation or assign work orders.

### MED-07: Inconsistent Class Label Casing Causing `NaN` in Inference Charts
- **Files:** `motor-dashboard/src/data/mockData.js:650, 668`, `motor-dashboard/src/pages/EdgeImpulse.jsx:120`.
- **Evidence:** Mock data mixes uppercase `"NORMAL"`, `"BEARING_FAULT"` with lowercase `"normal"`, `"bearing_fault"`.
- **Impact:** Object key lookups fail in charting components, rendering `NaN` or blank intervals in AI classification distributions.

### MED-08: Zombie WebSocket Reconnect Timer Spawning Connections on Unmount
- **Files:** `motor-dashboard/src/context/AppContext.jsx:269-275`.
- **Evidence:** In `AppContext.jsx`, the WebSocket reconnect `setTimeout` identifier is not cleared in the `useEffect` cleanup return function.
- **Impact:** Rapid component unmounting/remounting creates duplicate zombie WebSocket connections that flood the backend.

### MED-09: Unhandled Exceptions in `asyncio.run_coroutine_threadsafe` Future
- **Files:** `backend_example/main.py:246`.
- **Evidence:** In `on_mqtt_message`, the Future returned by `asyncio.run_coroutine_threadsafe` is not stored, awaited, or bound to a completion callback.
- **Impact:** Any uncaught exception inside `process_telemetry_payload` is silently swallowed, leaving no log trail.

### MED-10: Missing Pagination Validation on History and Alerts Endpoints
- **Files:** `backend_example/main.py:360, 376`.
- **Evidence:** `limit: int = 100` lacks upper-bound validation (`Query(default=100, ge=1, le=1000)`).
- **Impact:** An attacker can request `limit=10000000`, causing the database and API to attempt loading millions of documents into RAM.

---

## 7. Low-Severity Findings

Findings in this category represent dead code, documentation mismatches, minor style bugs, or code duplication.

- **LOW-01: Identical Duplicate Firmware Sketch Files:** `firmware/esp32_motor_node.ino` and `firmware/esp32_motor_node/esp32_motor_node.ino` are 100% byte-for-byte identical duplicates, risking divergent edits.
- **LOW-02: Orphaned Pydantic Model `SensorDataTestPayload`:** Defined in `backend_example/main.py:55-60` but never referenced in any route or function signature.
- **LOW-03: Missing Runtime Dependencies in `backend_example/requirements.txt`:** `httpx` (required by `test_pipeline.py`) and `pyserial` (required by `serial_bridge.py`) are absent from `requirements.txt`.
- **LOW-04: Hardcoded MongoDB Connection String in Seed Script:** `backend_example/seed_users.py:69` hardcodes `mongodb://localhost:27017`, ignoring the `MONGO_URI` environment variable.
- **LOW-05: Missing Non-Existent Motor 404 Response:** `GET /api/motors/{motor_id}/live` returns HTTP 200 with an informational JSON string instead of a standard HTTP 404 `Not Found`.
- **LOW-06: React 19 StrictMode Impure Render Warnings:** Date formatting inside JSX render passes triggers minor console warnings under React StrictMode.
- **LOW-07: Incomplete Mobile Responsive Navigation:** The sidebar lacks an off-canvas drawer toggle for viewport widths below 640px.

### Informational Findings (INFO)
- **INFO-01: Monolithic 1.51 MB Frontend JavaScript Bundle:** `dist/assets/index.js` is bundled into a single file without dynamic route code splitting.
- **INFO-02: Hardware Wiring Documentation Mismatch:** `firmware/README.md` documents MPU6050, `SIMULATION_MODE`, and AC RMS; code implements ADXL345, DC averaging, and hardware-only sampling.
- **INFO-03: Hardcoded Critical Hazard Banner in Overview UI:** `Overview.jsx` hardcodes a critical hazard alert banner that renders regardless of live motor state.

---

## 8. Security Findings

Synthesized from `reports/SECURITY_QA.md`, `reports/BACKEND_QA.md`, and `reports/FRONTEND_QA.md`.

### 8.1 Threat Model & STRIDE Analysis Matrix
| STRIDE Category | Threat Description | Vulnerable Component | Severity | Reconciled Status |
|---|---|---|---|---|
| **Spoofing** | Forging telemetry packets without credentials | REST (`/api/telemetry`), MQTT | **HIGH** | Confirmed unauthenticated ingestion |
| **Tampering** | Overriding motor control commands (Emergency stop) | REST (`/api/motors/{id}/control`) | **CRITICAL** | Confirmed arbitrary actuation |
| **Repudiation** | Modifying user accounts or triggering resets with zero audit log | REST (`/api/users`), LocalStorage | **MEDIUM** | Confirmed zero authentication logging |
| **Information Disclosure** | Dumping all user names, roles, departments via unauthenticated GET | REST (`/api/users`), Firmware code | **HIGH** | Confirmed unauthenticated user dump |
| **Denial of Service** | Exhausting event loop or memory via unindexed queries & WS leaks | Backend API, WS broadcaster | **HIGH** | Confirmed event loop blocking & leaks |
| **Elevation of Privilege** | Modifying `localStorage` role string to escalate to Administrator | Frontend `ProtectedRoute.jsx` | **CRITICAL** | Confirmed client-side RBAC bypass |

### 8.2 Insecure CORS Configuration Analysis
`backend_example/main.py:34-40` configures CORS middleware as:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
- **Vulnerability Breakdown:** The combination of `allow_origins=["*"]` and `allow_credentials=True` is prohibited by W3C CORS specifications. Modern browsers reject preflight responses that combine wildcards with credentials. Furthermore, Starlette reflects the incoming `Origin` header dynamically, effectively allowing any malicious origin to make credentialed cross-origin requests.

### 8.3 Unauthenticated Actuation Risk
Industrial control systems require strict separation of telemetry ingestion and actuation. In Motor-Guard, the actuation endpoint (`/api/motors/{motor_id}/control`) resides on the same unauthenticated REST interface as public health checks. Anyone on the local network or intranet can trip the motor relay or halt production lines without providing an identity or audit trail.

---

## 9. Integration Findings

Synthesized from `reports/INTEGRATION_QA.md` and cross-tier analysis.

### 9.1 The 10 End-to-End Scenario Evaluations
```
+----------------------------------------------------------------------------------------------------+
|                                 INTEGRATION SCENARIOS EVALUATION                                   |
+----------+------------------------------------+--------+-------------------------------------------+
| Scenario | Description                        | Status | Key Integration Defect                    |
+----------+------------------------------------+--------+-------------------------------------------+
| SC-01    | Normal Telemetry Pipeline Trace    | PARTIAL| Backend computes health; UI uses mock data|
| SC-02    | High Temperature (85°C & 70°C)     | FAIL   | 70°C warning missing; motor_name crashes UI|
| SC-03    | High Vibration (7.8 vs 5.5 mm/s)   | FAIL   | 5.0/7.0 vs 0.7/1.1 mm/s threshold clash   |
| SC-04    | High Current (15.2 A)              | FAIL   | Current is dead code in health formula    |
| SC-05    | Catastrophic Multiple Failures     | FAIL   | Clamped to artificial 5% health & 1d RUL  |
| SC-06    | MQTT Failure & Serial Bridge Break | FAIL   | Serial bridge regex prefix mismatch       |
| SC-07    | Backend Restart & State Loss       | FAIL   | Memory cache lost; DB not queried on boot |
| SC-08    | Database Outage Latency Trap       | FAIL   | Awaiting DB stalls WS broadcast by 5-15s  |
| SC-09    | WebSocket Disconnection Leak       | FAIL   | Closed socket not removed from active list|
| SC-10    | Unauthorized RBAC Bypass           | FAIL   | Zero auth on backend; localStorage bypass |
+----------+------------------------------------+--------+-------------------------------------------+
```

### 9.2 Critical Cross-Tier Disconnects
1. **The Telemetry Isolation Disconnect:** The backend successfully ingests telemetry, runs ML heuristics, records to MongoDB, and broadcasts to WebSocket. However, the React application's historical analysis, motor tables, and user management pages communicate with zero backend REST endpoints.
2. **Schema Incompatibility Crash Vector:** The backend `evaluate_alerts()` function generates alert objects with fields: `['id', 'motor_id', 'severity', 'sensor', 'message', 'timestamp', 'status']`. The frontend `Alerts.jsx` component expects `motor_name`. Receiving a live backend alert triggers a fatal JavaScript crash.
3. **Threshold Contradiction Matrix:**
   - *Vibration Warning:* Backend = `5.0 mm/s`, Frontend = `0.70 mm/s` (**7.1x discrepancy**).
   - *Vibration Critical:* Backend = `7.0 mm/s`, Frontend = `1.10 mm/s` (**6.3x discrepancy**).
   - *Temperature Warning:* Backend = None (missing), Frontend = `65.0°C`.
   - *Temperature Critical:* Backend = `80.0°C`, Frontend = `80.0°C` (Matches).

---

## 10. Performance Findings

Synthesized from `reports/PERFORMANCE_QA.md`.

### 10.1 Frontend Performance Deficiencies
- **Bundle Weight:** Production build generates a monolithic `index.js` of 1,514.88 kB (433.91 kB gzip), exceeding Vite's 500 kB chunk threshold by 300%.
- **Render Thrashing:** `IndustrialMotor3D.jsx` executes React `setState` inside `requestAnimationFrame`, causing 60 re-renders per second of the 3D canvas container.
- **Context Cascades:** `AppContext.jsx` distributes unmemoized values, causing all 15 routed dashboard components to re-render whenever a live WebSocket packet arrives at 4 Hz.
- **SVG Recharts Redraw Overhead:** 4 SVG charts in `LiveMonitoring.jsx` completely destroy and recreate their SVG DOM trees on every live tick.

### 10.2 Backend API & Concurrency Benchmarks
- **WebSocket Broadcast Latency:**
  - 1 Client: 0.12 ms
  - 10 Clients: 1.84 ms
  - 50 Clients: 92.40 ms
  - 100 Clients: 1,558.20 ms (**Catastrophic serialization delay**)
- **Explain Plan Verification on MongoDB `alerts` Query:**
  - Query: `db.alerts.find({}).sort({timestamp: -1})`
  - Winning Plan: `COLLSCAN` (Collection Scan) + `SORT` (In-Memory Sort).
  - Total Docs Examined: $N$ (Scans entire collection due to compound index prefix mismatch).

### 10.3 Embedded Firmware Timing Budget Analysis
- **Target Sampling Period:** 10,000 µs (10.0 ms = 100 Hz).
- **Current Read Delay:** 30 samples $\times$ 200 µs delay = 6,240 µs (62.4% of budget).
- **OLED Display Update:** 25,000 µs over 100 kHz I2C (250% of budget).
- **Result:** Every 250 ms, the main loop overruns by 21.2 ms, dropping samples and introducing 300% timing jitter into vibration frequency analysis.

---

## 11. ML Findings

Synthesized from `reports/ML_QA.md`.

### 11.1 Cloud ML Reality vs. Heuristic Implementation
The project documentation advertises a "Cloud AI Predictive Analytics Engine". Code inspection of `backend_example/main.py` confirms that **no trained machine learning model exists in the cloud backend**. The RUL and health scores are procedural linear heuristics:
$$\text{Health} = 100.0 - (\text{vibration} \times 6.5) - (\max(0, \text{temp} - 50.0) \times 1.2) - (\text{anomaly} \times 30.0)$$
- **Defect:** Motor current is omitted entirely from the equation.
- **Defect:** Anomaly score derivation in `process_telemetry_payload` assigns an artificial floor of 0.65 whenever an AI fault is predicted, conflating supervised classification confidence with novelty detection.

### 11.2 Edge Impulse TinyML Architecture & DSP Flaws
- **Model Architecture:** 1D Convolutional Neural Network (Input shape: 300 features, 3 classes: `critical`, `fault`, `normal`).
- **Critical DSP Anti-Pattern:** The Edge Impulse model applies a high-frequency **Spectral Analysis (FFT) DSP block** across a 3-feature stream consisting of:
  1. Temperature (°C) from DS18B20 (updated at 1 Hz, held constant across 100 consecutive frames).
  2. Vibration magnitude (g) from ADXL345.
  3. Current average (A) from ACS712.
  Feeding constant DC signals (temperature and current) into an FFT spectral block is mathematically invalid and corrupts the frequency-domain feature space.

### 11.3 Phantom Anomaly Detector & Class Space Contradictions
- **The Phantom Anomaly Detector:** Edge Impulse model metadata header `model_metadata.h` explicitly sets:
  ```cpp
  #define EI_CLASSIFIER_HAS_ANOMALY EI_ANOMALY_TYPE_UNKNOWN
  ```
  The deployed model has **zero anomaly detection capabilities**. The backend and frontend invent an artificial anomaly score by remapping classification probabilities.
- **Class Space Mismatch:**
  - *Edge Impulse Model Classes:* 3 classes (`critical`, `fault`, `normal`).
  - *Frontend Confusion Matrix:* 4 classes (`normal`, `bearing_fault`, `rotor_imbalance`, `overheating`).
  - The frontend fabricates specific mechanical failure classifications that the deployed edge model cannot predict.

---

## 12. Conflicting Agent Findings

This section reconciles contradictory findings, inconsistent severity classifications, and false positives detected across the 9 agent reports.

### 12.1 Contradiction 1: Feature Buffer Boundary Check (Permanent Freeze vs. Latent Defect)
- **Agent 1 (`CODE_REVIEW.md`):** Identified CQ-001 as **CRITICAL: Permanent Inference Freeze**, stating that the condition `if (feature_index + 2 < EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE)` prevents the buffer from ever reaching full capacity, completely halting inference.
- **Agent 6 (`ML_QA.md`):** Mathematically proved that with `FRAME_SIZE = 300`, on sample 100 `feature_index` equals 297 (`297 + 2 = 299 < 300` is True). Features are written to slots 297, 298, 299, incrementing `feature_index` to 300, which evaluates `feature_index >= 300` as True, resets the index, and invokes inference.
- **Reconciliation & Final Verdict:** Agent 1's claim of an immediate permanent freeze under the default 300-sample configuration is a **False Positive**. However, Agent 6 correctly identified that the condition creates a **Latent High-Severity Vulnerability**: if any model re-deployment produces a frame size not divisible by 3, or if an index offset occurs, the buffer enters an unrecoverable permanent deadlock. Reclassified from Critical freeze to **High Latent Defect**.

### 12.2 Contradiction 2: PubSubClient Packet Overflow Omission
- **Agent 5 (`IOT_MQTT_QA.md`):** Identified default `MQTT_MAX_PACKET_SIZE = 128` as a **Critical Defect** causing silent packet drop for 165–185 byte payloads.
- **Agent 1 (`CODE_REVIEW.md`):** Audited the firmware code thoroughly but completely missed the PubSubClient packet size buffer limit.
- **Reconciliation & Final Verdict:** Verified directly against the official Arduino `PubSubClient.h` source code. In version 2.7 and earlier (and standard PlatformIO / Arduino library manager distributions), `MQTT_MAX_PACKET_SIZE` defaults to 128. Because `snprintf` creates payloads up to 185 bytes (packet size ~211 bytes), `mqttClient.publish()` fails and returns false. Agent 5's finding is **CONFIRMED CRITICAL**.

### 12.3 Contradiction 3: Severity of Permissive CORS Policy
- **Agent 1 (`CODE_REVIEW.md`) & Agent 3 (`BACKEND_QA.md`):** Classified `allow_origins=["*"]` with `allow_credentials=True` as **CRITICAL**.
- **Agent 7 (`SECURITY_QA.md`):** Classified the CORS configuration as **MEDIUM (CVSS 6.5)**.
- **Reconciliation & Final Verdict:** While combining wildcards with credentials violates W3C standards and is rejected by browsers, the backend currently possesses no cookies, session tokens, or browser-credentialed auth mechanisms. An attacker cannot exfiltrate authenticated sessions that do not exist. Therefore, CVSS 9+ (Critical) is an overstatement. The reconciled severity is **MEDIUM** (escalating to High upon implementation of JWT/cookie authentication).

### 12.4 Contradiction 4: Hardware Sensor Documentation Disparity Severity
- **Agent 1 (`CODE_REVIEW.md`):** Classified the MPU6050 vs. ADXL345 documentation mismatch as **INFORMATIONAL (`CQ-031`)**.
- **Agent 5 (`IOT_MQTT_QA.md`):** Classified the sensor mismatch as **HIGH / Divergent Defect**.
- **Reconciliation & Final Verdict:** In industrial firmware engineering, wiring an MPU6050 (I2C address `0x68`) according to `README.md` diagrams while the compiled firmware queries an ADXL345 (I2C address `0x53`) causes total I2C bus initialization failure and firmware panics. Treating hardware pinout contradictions as Informational is a dangerous under-classification. Reconciled severity is **HIGH**.

### 12.5 Contradiction 5: Pipeline Test Script Coverage Integrity
- **Test Script Artifact (`test_pipeline.py`):** Declares `=== ALL TESTS COMPLETED 100% CLEANLY ===`.
- **Agents 3, 4, and 9 (`BACKEND_QA.md`, `DATABASE_QA.md`, `INTEGRATION_QA.md`):** Demonstrated that 8 out of 10 end-to-end integration scenarios fail, `GET /api/users` crashes on ObjectId, `POST /api/motors/.../control` rejects JSON bodies, and `test_pipeline.py` itself crashes if MongoDB is down.
- **Reconciliation & Final Verdict:** The test script's claim of "100% cleanly" is a dangerous **false-positive artifact** resulting from shallow happy-path testing.

---

## 13. Failed Tests

Comprehensive compilation of all empirical test failures documented across all auditing agents.

```
+----------------------------------------------------------------------------------------------------+
|                                      FAILED TESTS MATRIX                                           |
+----+--------------------------+-----------------------+---------------------+----------------------+
| #  | Source Report            | Identifier / Scenario | Endpoint / Function | Failure Mode         |
+----+--------------------------+-----------------------+---------------------+----------------------+
| 1  | BACKEND_QA.md            | Test 4                | POST /api/telemetry | Accepts empty JSON   |
| 2  | BACKEND_QA.md            | Test 5                | POST /api/telemetry | HTTP 500 on bad type |
| 3  | BACKEND_QA.md            | Test 7                | POST /api/test/...  | HTTP 500 on bad type |
| 4  | BACKEND_QA.md            | Test 9                | GET /api/motors/live| Returns 200 not 404  |
| 5  | BACKEND_QA.md            | Test 13               | GET /api/users      | HTTP 500 ObjectId    |
| 6  | BACKEND_QA.md            | Test 14               | POST /control       | HTTP 422 JSON Body   |
| 7  | BACKEND_QA.md            | Test 15               | POST /control       | False 200 MQTT down  |
| 8  | BACKEND_QA.md            | Test 17               | OPTIONS CORS        | Wildcard+Credentials |
| 9  | FRONTEND_QA.md           | TC-AUTH-01            | AppContext.jsx      | Admin auto-login     |
| 10 | FRONTEND_QA.md           | TC-AUTH-02            | AppContext.jsx      | Logout not persisted |
| 11 | FRONTEND_QA.md           | TC-NAV-01             | Sidebar.jsx         | Missing routes       |
| 12 | FRONTEND_QA.md           | TC-VIEW-03            | Pages REST Sync     | Zero REST calls      |
| 13 | FRONTEND_QA.md           | TC-VIEW-07            | Reports.jsx         | Inoperative buttons  |
| 14 | FRONTEND_QA.md           | TC-VIEW-08            | Dashboard Themes    | White theme clash    |
| 15 | INTEGRATION_QA.md        | Scenario 2            | Alerts.jsx          | Missing motor_name   |
| 16 | INTEGRATION_QA.md        | Scenario 3            | LiveMonitoring.jsx  | Threshold clash      |
| 17 | INTEGRATION_QA.md        | Scenario 4            | calculate_rul...    | Current is dead code |
| 18 | INTEGRATION_QA.md        | Scenario 5            | calculate_rul...    | Artificial 5% floor  |
| 19 | INTEGRATION_QA.md        | Scenario 6            | serial_bridge.py    | Regex prefix break   |
| 20 | INTEGRATION_QA.md        | Scenario 7            | GET /api/motors/live| Restart cache loss   |
| 21 | INTEGRATION_QA.md        | Scenario 8            | broadcast_ws        | DB offline stalls WS |
| 22 | INTEGRATION_QA.md        | Scenario 9            | broadcast_ws        | Closed socket leak   |
| 23 | INTEGRATION_QA.md        | Scenario 10           | System-wide         | Total RBAC bypass    |
+----+--------------------------+-----------------------+---------------------+----------------------+
```

---

## 14. Recommended Fix Order

To ensure safe and structured remediation without introducing regressions, fixes must be executed across four strictly sequenced phases.

```
[ Phase 0: Emergency Safety & Crash Fixes ]
  ├── 1. Protect ESP32 GPIO 34 from 5V Overvoltage (Resistor Voltage Divider)
  ├── 2. Patch Alerts.jsx: Add optional chaining (a.motor_name?.toLowerCase())
  ├── 3. Fix GET /api/users: Project {"_id": 0} or convert ObjectId to string
  └── 4. Enforce MQTT_MAX_PACKET_SIZE 512 in firmware PubSubClient
                   │
                   ▼
[ Phase 1: Authentication, Authorization & Actuation Integrity ]
  ├── 5. Implement JWT Authentication on FastAPI with Role-Based Access Control
  ├── 6. Fix AppContext.jsx: Remove default admin fallback & clear localStorage on logout
  ├── 7. Fix POST /api/motors/{id}/control: Accept Pydantic JSON Body & check MQTT state
  ├── 8. Wire Firmware MQTT Subscription: Subscribe to motors/{id}/cmd & handle relays
  └── 9. Restrict CORS Policy: Replace wildcard origins with explicit domain whitelist
                   │
                   ▼
[ Phase 2: Pipeline Synchronization & Integration Repair ]
  ├── 10. Fix serial_bridge.py: Strip [MQTT Publish -> ...] prefix before JSON parsing
  ├── 11. Connect Frontend to Real REST API: Replace mockData.js with real fetch/axios
  ├── 12. Harmonize Thresholds: Align vibration (5.0/7.0) and temperature across tiers
  ├── 13. Incorporate Motor Current into calculate_rul_and_health and alert rules
  └── 14. Reconstruct Cache on Startup: Query MongoDB to warm latest_readings on reboot
                   │
                   ▼
[ Phase 3: Performance, Scalability & DSP Hardening ]
  ├── 15. Fix Three.js Memory Leak: Dispose geometries/materials and throttle setState
  ├── 16. Optimize WS Broadcast: asyncio.gather with Dead Connection Eviction
  ├── 17. Asynchronous DB Writes: Decouple save_telemetry from live WS broadcast loop
  ├── 18. Fix MongoDB Compound Index: Create index on {"timestamp": -1} for alerts
  ├── 19. Embedded RTOS Separation: Move I2C OLED display updates to FreeRTOS Task on Core 0
  └── 20. Edge Impulse DSP Realignment: Remove DC signals (Temp/Current) from 100 Hz FFT
```

### Phase 0: Emergency Safety & Crash Fixes (P0 — Immediate)
1. **Hardware Voltage Divider on ACS712:** Install a 2:1 resistive divider (e.g. 10kΩ / 20kΩ) between ACS712 OUT and ESP32 GPIO 34 to step 5.0V down to 3.3V safe levels.
2. **Frontend Crash Guard:** In `Alerts.jsx:54`, replace `a.motor_name.toLowerCase()` with `(a.motor_name || a.motor_id || 'Unknown Motor').toLowerCase()`.
3. **Backend BSON Serialization Fix:** In `backend_example/main.py:395`, update cursor to `db["users"].find({}, {"_id": 0})` or map documents with `doc["_id"] = str(doc["_id"])`.
4. **Firmware Buffer Configuration:** Add `#define MQTT_MAX_PACKET_SIZE 512` at the very top of `firmware/esp32_motor_node.ino` before `#include <PubSubClient.h>`.

### Phase 1: Authentication, Authorization & Actuation Integrity (P1 — Next Sprint)
5. **FastAPI Security Architecture:** Add standard OAuth2 / JWT bearer authentication middleware to FastAPI; enforce `@require_role(["admin"])` on actuation endpoints.
6. **Frontend Auth Hardening:** In `AppContext.jsx`, initialize `currentUser` to `null` instead of `users[0]`; call `localStorage.removeItem('motor_health_user')` inside `logout()`.
7. **Motor Control Endpoint Signature:** Replace scalar parameter with `class MotorControlRequest(BaseModel): command: str`; verify `mqtt_client.is_connected()` and return HTTP 503 if offline.
8. **Firmware Command Ingestion:** In `firmware/esp32_motor_node.ino`, add `mqttClient.subscribe("motors/MTR-001/cmd")` and register a callback to toggle GPIO 15 relay.
9. **CORS Hardening:** Replace `allow_origins=["*"]` with explicit frontend origins (e.g. `["http://localhost:5173"]`).

### Phase 2: Pipeline Synchronization & Integration Repair (P2)
10. **Serial Bridge Parser Patch:** In `backend_example/serial_bridge.py:95`, extract substring between first `{` and last `}` using regex `re.search(r'\{.*\}', line)`.
11. **Frontend REST Integration:** Implement React Query or Axios services to populate `Overview.jsx`, `Alerts.jsx`, `Users.jsx`, and `Analytics.jsx` from backend endpoints.
12. **Threshold Alignment:** Unify vibration thresholds to Warning: `5.0 mm/s` (or Class II ISO `2.8 mm/s`), Critical: `7.0 mm/s` across both `main.py` and `LiveMonitoring.jsx`.
13. **Current Ingestion in ML:** Incorporate `current` into `calculate_rul_and_health`: deduct health when current exceeds rated operating amperage (e.g. `max(0, current - 5.0) * 8.0`); add overcurrent alert rule in `evaluate_alerts`.
14. **Backend State Warm-Up:** In `startup_event()`, query MongoDB `telemetry` collection for the latest record of each motor and warm `latest_readings`.

### Phase 3: Performance, Scalability & DSP Hardening (P3)
15. **Three.js WebGL Lifecycle Cleanup:** In `IndustrialMotor3D.jsx`, call `renderer.dispose()`, `geometry.dispose()`, `material.dispose()`, and remove `setState` from `requestAnimationFrame`.
16. **Concurrent WebSocket Broadcasting:** Replace serial `for` loop in `broadcast_ws` with `asyncio.gather(*[client.send_text(data) for client in active_connections], return_exceptions=True)`; immediately remove clients that raise exceptions.
17. **Decoupled Database Persistence:** Offload `save_telemetry` and `save_alert` to background tasks via `asyncio.create_task()` so database latency never stalls WebSocket broadcasting.
18. **Index Optimization:** In `database.py`, create an index on `alerts` for `[("timestamp", -1)]` to support global alert queries without `motor_id`.
19. **Dual-Core FreeRTOS Partitioning:** Move I2C OLED display updates and Wi-Fi transmission to FreeRTOS Core 0; dedicate Core 1 entirely to 100 Hz sensor sampling and TinyML inference.
20. **Edge Impulse DSP Realignment:** Retrain the Edge Impulse impulse using 3-axis raw accelerometer inputs ($X, Y, Z$) for Spectral Analysis; process temperature and current through a separate static threshold or anomaly engine.

---

## 15. Regression Test Requirements

Following the implementation of recommended fixes, the following verification suite must be executed to ensure complete system stability and prevent regression.

### 15.1 Embedded Firmware & IoT Regression Suite
- **REG-FW-01 (Buffer Capacity):** Verify MQTT packets up to 300 bytes are published without truncation; verify `mqttClient.publish()` returns `true`.
- **REG-FW-02 (Command Actuation):** Publish `{"command": "EMERGENCY_SHUTDOWN"}` to `motors/MTR-001/cmd`; verify ESP32 GPIO 15 relay toggles within 50 ms.
- **REG-FW-03 (Reboot Under Load):** Boot ESP32 while a 3.0A load is active; verify `current_offset` defaults to calibrated factory baseline and does not zero out active load.
- **REG-FW-04 (Isochronous Sampling):** Profile GPIO toggle on oscilloscope during loop; verify 100 Hz sampling period remains within $10.0 \pm 0.5 \text{ ms}$ regardless of I2C display updates.

### 15.2 Backend API & Database Regression Suite
- **REG-API-01 (BSON Serialization):** Populate MongoDB `users` collection with native `ObjectId` records; execute `GET /api/users`; verify HTTP 200 with serialized `id` strings.
- **REG-API-02 (Input Schema Validation):** Submit invalid payloads (`{}`, `{"vibration_mm_s": "invalid"}`, non-JSON); verify FastAPI returns HTTP 422 with structured field error locations.
- **REG-API-03 (Actuation Signature & Validation):** Submit `POST /api/motors/MTR-001/control` with JSON body `{"command": "RESET_RELAY"}`; verify HTTP 200; submit when broker offline; verify HTTP 503.
- **REG-API-04 (Offline DB Resiliency):** Stop MongoDB container; execute `POST /api/telemetry`; verify WebSocket broadcast completes in $< 20 \text{ ms}$ without being blocked by MongoDB connection timeouts.
- **REG-API-05 (Index Explain Plan):** Execute MongoDB explain plan on `GET /api/alerts`; verify query execution plan uses `IXSCAN` on `timestamp` and examines zero surplus documents.

### 15.3 Machine Learning & Integration Regression Suite
- **REG-ML-01 (Overcurrent Degradation):** Submit `current_a: 15.0A` to `POST /api/telemetry`; verify health score drops below 50% and an electrical overcurrent alert is generated.
- **REG-ML-02 (RUL Continuity):** Sweep health score from 100% down to 0% in 0.5% increments; verify RUL curve is strictly monotonic with zero discontinuous drops exceeding 5 days.
- **REG-ML-03 (Serial Bridge Forwarding):** Stream raw firmware serial output through `serial_bridge.py`; verify 100% of telemetry packets are parsed and successfully forwarded to backend.
- **REG-ML-04 (WebSocket Dead Socket Eviction):** Open 50 WebSocket connections, abruptly terminate 25 connections; trigger `broadcast_ws`; verify `active_connections` drops to exactly 25 with zero memory leak.

### 15.4 Frontend SCADA & Security Regression Suite
- **REG-FE-01 (Unauthenticated Access):** Open incognito browser to `/`; verify immediate redirection to `/login` without Administrator role assignment.
- **REG-FE-02 (Session Termination):** Click "Logout"; refresh browser page; verify user remains on `/login` and cannot access `/overview`.
- **REG-FE-03 (Alert Payload Safety):** Broadcast a live alert omitting `motor_name`; verify `Alerts.jsx` renders `motor_id` fallback without throwing a JavaScript error.
- **REG-FE-04 (Three.js Memory Lifecycle):** Mount and unmount `IndustrialMotor3D` component 50 times in a loop; verify WebGL memory and JS heap footprint return to baseline.
- **REG-FE-05 (CORS Rejection):** Issue cross-origin request from unlisted domain with credentials; verify browser blocks response with CORS policy error.
