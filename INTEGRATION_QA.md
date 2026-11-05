# End-to-End System Integration QA Report

**Auditor:** AGENT 9 — END-TO-END INTEGRATION AGENT  
**Report Artifact Location:** `reports/INTEGRATION_QA.md`  
**Execution Environment:** FastAPI + Starlette TestClient / HTTPX ASGI Transport + MongoDB + Mosquitto MQTT + WebSocket Engine  
**Project Workspace:** `c:\Users\gopes\Downloads\project`  
**Audit Date:** October 2, 2026  
**Status:** Completed in Read-Only Mode  

---

## Executive Summary

This report documents the end-to-end integration audit of the **Motor Health Monitoring & Predictive Maintenance System (Motor-Guard)** across all functional tiers:
```
ESP32 Sensor Telemetry 
  ↓ (MQTT / Serial Bridge)
FastAPI Ingestion Gateway (main.py)
  ↓ (Feature Extraction & Cloud ML Pipeline)
Alert Rule Engine & MongoDB Persistence (database.py)
  ↓ (WebSocket Broadcaster /ws/live)
React SCADA Workstation (motor-dashboard)
```

Ten targeted integration scenarios were executed and evaluated using both live runtime test executions and cross-tier architectural verification.

### Overall Scenario Results

| Scenario | Objective | Status | Key Integration Defect Identified |
|---|---|---|---|
| **Scenario 1** | Normal Telemetry Pipeline | **PASS** (Partial) | Ingestion and calculations succeed, but frontend relies exclusively on mock simulation; REST data is not synced. |
| **Scenario 2** | High Temperature (85°C & 70°C) | **FAIL** | 85°C triggers critical alert, but 70°C warning threshold is missing in backend. Alert payload lacks `motor_name`, crashing `Alerts.jsx`. |
| **Scenario 3** | High Vibration (7.8 & 5.5 mm/s) | **FAIL** | Vibration thresholds misaligned between backend (5.0 / 7.0 mm/s) and frontend UI (0.7 / 1.1 mm/s). |
| **Scenario 4** | High Current (15.2 A) | **FAIL** | Motor current is completely dead code in `calculate_rul_and_health` and alert evaluations; 15.2A produces 0 delta. |
| **Scenario 5** | Multiple Abnormal Values | **FAIL** | Artificial health floor (5.0%), failure probability cap (0.97), and RUL floor (1 day) prevent reporting zero life or 100% failure. |
| **Scenario 6** | MQTT Failure & Serial Bridge | **FAIL** | Serial bridge cannot parse firmware output due to `[MQTT Publish ->` prefix. Motor control returns false positive success when offline. |
| **Scenario 7** | Backend Restart Recovery | **FAIL** | In-memory cache (`latest_readings`) is wiped on restart; backend never queries MongoDB to reconstruct state on reboot. |
| **Scenario 8** | Database Outage & Latency | **FAIL** | Synchronously awaiting `save_telemetry` and `save_alert` with 5000ms timeout blocks WebSocket broadcasts by 5–10s during DB stalls. |
| **Scenario 9** | WebSocket Disconnect | **FAIL** | Client disconnection during `broadcast_ws` catches exceptions but fails to remove dead socket from `active_connections` (memory leak). |
| **Scenario 10** | Unauthorized Operation & RBAC | **FAIL** | Zero authentication or RBAC on backend API and WebSocket. Total unauthenticated access to control commands, telemetry, and user dumps. |

---

## Detailed Scenario Findings

### Scenario 1 — Normal Telemetry Pipeline Trace
- **Input Parameters:** `vibration_mm_s: 1.2`, `temperature_c: 35.0°C`, `current_a: 0.42A`, `anomaly_score: 0.05`.
- **Expected Behavior:** Ingestion via `POST /api/telemetry` calculates nominal health (>85%), failure probability (<0.15), RUL (>120 days), zero alerts, persists to MongoDB, and dispatches via WebSocket to update frontend motor status.
- **Empirical Execution:**
  - Health Calculated: `90.7%`
  - Failure Probability: `0.10`
  - RUL Days: `163 days`
  - Alerts Count: `0`
  - MongoDB Insertion: `True`
  - REST Status: `HTTP 200 OK`
- **Integration Disconnect:** Although the backend processes and broadcasts the enriched telemetry over `/ws/live`, the React frontend's REST layer contains **zero** fetch calls to populate historical graphs, telemetry logs, or maintenance records. The UI remains decoupled from backend REST state.

---

### Scenario 2 — High Temperature Telemetry (85°C & 70°C)
- **Input Parameters:** `temperature_c: 85.0°C` (Overheating) and `temperature_c: 70.0°C` (Warning).
- **Expected Behavior:** Backend generates Warning alert at 70°C and Critical alert at 85°C. Alert payload contains fields compatible with frontend `Alerts.jsx`.
- **Empirical Execution:**
  - At 85.0°C: Critical alert generated (`ALT-TEMP-...`: "Overheating detected: 85.0°C (limit: 80°C)").
  - At 70.0°C: **Zero alerts generated**. The backend `evaluate_alerts()` implementation has no warning threshold for temperature (only `if temp > 80.0:`).
  - Alert Payload Schema: Keys returned are `['id', 'motor_id', 'severity', 'sensor', 'message', 'timestamp', 'status']`.
- **Integration Breakdown (Crash Vector):**
  - In `motor-dashboard/src/pages/Alerts.jsx:54`:
    ```javascript
    const matchSearch = a.motor_name.toLowerCase().includes(search.toLowerCase())
    ```
  - Because backend alerts omit `motor_name`, evaluating live backend alerts in the frontend causes an unhandled `TypeError: Cannot read properties of undefined (reading 'toLowerCase')`, crashing the entire Alerts page!

---

### Scenario 3 — High Vibration Telemetry (7.8 mm/s vs 5.5 mm/s)
- **Input Parameters:** `vibration_mm_s: 7.8` (Critical) and `vibration_mm_s: 5.5` (Warning).
- **Expected Behavior:** Warning alert triggered at 5.5 mm/s, Critical alert triggered at 7.8 mm/s. Thresholds in backend match dashboard visual threshold indicators.
- **Empirical Execution:**
  - At 7.8 mm/s: Critical alert generated (`ALT-...`: "Critical vibration: 7.8 mm/s (limit: 7.0 mm/s)"). Health: `49.3%`, RUL: `9 days`.
  - At 5.5 mm/s: Warning alert generated (`ALT-...`: "Warning vibration: 5.5 mm/s (limit: 5.0 mm/s)"). Health: `64.2%`, RUL: `51 days`.
- **Cross-Tier Threshold Fracture:**
  - Backend `evaluate_alerts()` thresholds: Warning = `5.0 mm/s`, Critical = `7.0 mm/s`.
  - Frontend `LiveMonitoring.jsx:16` thresholds:
    ```javascript
    const THRESHOLDS = {
      vibration_mm_s: { warning: 0.70, critical: 1.10 },
      ...
    };
    ```
  - When the ESP32 publishes normal vibration of 1.2 mm/s, the backend considers it completely healthy, but the frontend LiveMonitoring UI renders a bright red critical hazard alert!

---

### Scenario 4 — High Current (15.2 A - Dead Code Evaluation)
- **Input Parameters:** Normal `current_a: 0.42A` vs Overcurrent `current_a: 15.2A` (nominal 5A motor rating).
- **Expected Behavior:** Severe motor overcurrent significantly reduces health score, spikes failure probability, and generates an electrical overcurrent alert.
- **Empirical Execution:**
  - Baseline (0.42 A): Health = `92.2%`, FailProb = `0.09`, RUL = `165 days`, Alerts = `0`.
  - Overcurrent (15.2 A): Health = `92.2%`, FailProb = `0.09`, RUL = `165 days`, Alerts = `0`.
  - Delta: `Health = 0.0`, `FailProb = 0.0`, `RUL = 0 days`, `Alerts = 0`.
- **Root Cause:**
  - In `backend_example/main.py:86-93`:
    ```python
    def calculate_rul_and_health(vibration: float, temperature: float, current: float, anomaly_score: float):
        health = 100.0 - (vibration * 6.5) - (max(0, temperature - 50.0) * 1.2) - (anomaly_score * 30.0)
    ```
  - The `current` argument is accepted into `calculate_rul_and_health` but **never used in any mathematical equation**. Furthermore, `evaluate_alerts()` contains zero checks for current. A motor drawing 500% rated current under locked rotor is reported as 92.2% healthy with 165 days of remaining life.

---

### Scenario 5 — Multiple Abnormal Values (Catastrophic Failure Clamping)
- **Input Parameters:** `vibration_mm_s: 7.8`, `temperature_c: 85.0°C`, `current_a: 15.2A`, `anomaly_score: 0.75`.
- **Expected Behavior:** Severe simultaneous failure triggers multiple alerts, drops health to 0%, spikes failure probability to 1.0 (100%), and sets RUL to 0 days.
- **Empirical Execution:**
  - Raw Equation Output: `100 - 50.7 - 42.0 - 22.5 = -15.20%`.
  - Clamped Health Output: `5.0%` (Artificial floor).
  - Failure Probability: `0.97` (Artificial cap; `0.70 + (50 - 5)*0.006 = 0.97`).
  - Remaining Useful Life: `1 day` (Artificial floor; `max(1, int(5 * 0.2)) = 1`).
  - Alerts: 3 alerts generated (Vibration critical, Temperature critical, Edge Impulse warning).
- **Architectural Impact:**
  - The model can never output 0% health or 0 days RUL. Even under total destructive failure (50 mm/s vibration, 200°C temperature), the system continuously reports that the motor has 1 day of life remaining.

---

### Scenario 6 — MQTT Failure & Serial Bridge Parsing Break
- **Execution Method:** Evaluated backend standalone behavior without MQTT broker, and simulated firmware serial telemetry ingestion in `backend_example/serial_bridge.py`.
- **Empirical Execution:**
  - Backend starts cleanly in standalone mode and reports `mqtt: "offline"` in `/api/system/status`.
  - Executing `POST /api/motors/MTR-001/control?command=EMERGENCY_SHUTDOWN` while MQTT is offline returns `HTTP 200 OK` with `{"status": "command_published"}`. The backend reports false positive actuation to operators when the broker is down.
  - Calling control with standard JSON payload `{"command": "EMERGENCY_SHUTDOWN"}` fails with `HTTP 422 Unprocessable Entity` ("Field required: query -> command").
- **Serial Bridge Disconnect:**
  - In `firmware/esp32_motor_node.ino:270`:
    ```cpp
    Serial.printf("[MQTT Publish -> %s] %s\n", MQTT_TOPIC, payload);
    ```
  - In `backend_example/serial_bridge.py:95`:
    ```python
    if line.startswith("{") and line.endswith("}"):
    ```
  - Because firmware prefixes every JSON line with `[MQTT Publish -> motors/MTR-001/data] `, `line.startswith("{")` evaluates to `False`. The serial bridge rejects every single line from the ESP32 USB COM port.

---

### Scenario 7 — Backend Restart & In-Memory State Loss
- **Execution Method:** Seeded `latest_readings` and `active_alerts`, restarted backend process, and immediately queried `GET /api/motors/MTR-001/live`.
- **Empirical Execution:**
  - Before Restart: In-memory cache held 1 motor and 1 active alert.
  - After Restart: `latest_readings` and `active_alerts` are empty.
  - Query: `GET /api/motors/MTR-001/live` returns:
    ```json
    {"message": "No live reading received yet from ESP32", "motor_id": "MTR-001"}
    ```
- **Architectural Impact:**
  - `main.py` never queries the MongoDB `telemetry` collection on startup to warm the `latest_readings` cache. Every server restart or container redeployment wipes motor telemetry until the hardware transmits its next packet.

---

### Scenario 8 — Database Outage & Latency Propagation
- **Code Analysis & Execution:**
  - In `backend_example/main.py:223-229`:
    ```python
    # 4. Asynchronously persist to MongoDB
    await save_telemetry(enriched)
    for a in new_alerts:
        await save_alert(a)

    # 5. Broadcast to connected WebSocket frontend clients
    await broadcast_ws(enriched)
    ```
- **Empirical Impact:**
  - `save_telemetry` and `save_alert` are executed sequentially before `broadcast_ws`.
  - When MongoDB is unresponsive or experiencing network partitions, PyMongo's `serverSelectionTimeoutMS = 5000` causes `await save_telemetry` to block for 5.0 seconds, and each alert to block for another 5.0 seconds (total 10–15 seconds).
  - During this period, the coroutine is suspended, starving WebSocket clients of live telemetry and freezing the dashboard SCADA stream.

---

### Scenario 9 — WebSocket Disconnection & Client Socket Leak
- **Execution Method:** Connected a client to `/ws/live`, simulated an abrupt socket drop (broken pipe), and triggered `broadcast_ws`.
- **Empirical Execution:**
  - Initial `active_connections`: `0`
  - Injected broken socket into `active_connections`: count = `1`
  - Ran `await broadcast_ws(...)`: Warning logged (`Error sending to WebSocket client: Connection closed abruptly`).
  - Post-broadcast `active_connections`: count = `1` (`True`).
- **Defect:**
  - In `backend_example/main.py:63-70`:
    ```python
    async def broadcast_ws(payload: dict):
        for connection in list(active_connections):
            try:
                await connection.send_text(json.dumps(payload))
            except Exception as e:
                logger.warning(f"Error sending to WebSocket client: {e}")
    ```
  - The exception handler logs a warning but **never removes** the dead socket from `active_connections`. Over days of operation, disconnected browser tabs accumulate indefinitely in RAM, creating a memory and CPU leak on every broadcast loop.

---

### Scenario 10 — Unauthorized Operation & RBAC Bypass
- **Execution Method:** Attempted administrative actions via unauthenticated HTTP requests.
- **Empirical Execution:**
  - `GET /api/users`: `HTTP 200 OK` (Disclosed all 6 user records including roles and departments with zero credentials).
  - `POST /api/motors/MTR-001/control?command=EMERGENCY_SHUTDOWN`: `HTTP 200 OK` (Command dispatched to MQTT with zero authentication).
  - `POST /api/telemetry` (Injecting bogus motor `MTR-999` with 99.9 mm/s vibration): `HTTP 200 OK` (Telemetry accepted and persisted into MongoDB with zero authentication).
- **Frontend RBAC Bypass:**
  - `AppContext.jsx` initializes `currentUser` to `users[0]` (Admin) when localStorage is empty.
  - Any user can bypass frontend `ProtectedRoute` checks by executing `localStorage.setItem('motor_health_user', JSON.stringify({role: 'admin'}))` in DevTools.
  - Because backend endpoints have zero token or role verification, frontend RBAC provides zero actual security.

---

## Conclusion & Integration Readiness
The core mathematical formulas and basic async ingestion pipeline function under happy-path conditions. However, the system currently exhibits **severe cross-tier fractures**:
1. Frontend alerts page crashes when ingesting backend alerts (missing `motor_name`).
2. Live monitoring renders false critical alarms due to 5x threshold mismatch between UI and backend.
3. Serial bridge cannot ingest firmware telemetry due to log prefix string mismatch.
4. Database latency directly blocks real-time WebSocket broadcasting.
5. Unbounded socket leaks and unauthenticated actuator controls present critical operational hazards.

All integration defects must be formally consolidated and prioritized before any source code fixes are applied.
