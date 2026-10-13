# MotorGuard — Implementation Roadmap & Acceptance Testing

## 1. Phase Milestones Overview

| Phase | Milestone Name | Objective | Status |
| :---: | :--- | :--- | :---: |
| **0** | **Architecture & Foundation** | Schemas, contracts, security, safety risks, setup docs, structure | **Complete** |
| **1** | **Backend & App Foundation** | FastAPI app, Pydantic settings, health check endpoint, test runner | **Complete** |
| **2** | **MQTT Ingestion & MongoDB** | Mosquitto broker, MQTT consumer, MongoDB storage, deduplication | **Current** |
| **3** | **Real-Time Dashboard** | React + Vite + TypeScript, WebSockets live gauges, motor list | *Pending* |
| **4** | **RBAC, Alerts & Maintenance** | Auth JWT, role-based views, alert acknowledgement, maintenance logs | *Pending* |
| **5** | **Physical ESP32 Telemetry** | ESP32 Wi-Fi, sensor calibration, matching telemetry schema | *Pending* |
| **6** | **Edge Impulse TinyML** | Model verification, inference timing, class probabilities | *Pending* |
| **7** | **Reliability & Failure Testing**| Wi-Fi loss, broker restart, invalid sensors, offline buffer recovery | *Pending* |
| **8** | **Gateway Release & VPN** | Docker stack, backup automation, secure remote access | *Pending* |

---

## 2. Phase-by-Phase Acceptance Criteria & Tests

### Phase 0: Architecture & Foundation (Current Phase)
- **Criteria**:
  1. Complete workspace directory structure exists.
  2. All architectural, data contract, MQTT, data model, security, and hardware documentation written.
  3. `.env.example`, `.gitignore`, `infrastructure/docker-compose.yml`, and `README.md` created.
  4. Existing firmware and datasets preserved and organized.
- **Verification Command**:
  ```powershell
  python -c "import os; docs=['architecture.md','telemetry-contract.md','mqtt-specification.md','data-model.md','environment-variables.md','security-checklist.md','hardware-tinyml-risks.md','local-setup-windows.md','deployment-strategy.md','roadmap-acceptance-tests.md']; assert all(os.path.exists(os.path.join('docs', f)) for f in docs); print('Phase 0 docs verified!')"
  ```

---

### Phase 1: Backend Foundation & Health Checks
- **Criteria**:
  1. FastAPI starts locally on Windows (`http://127.0.0.1:8000`).
  2. `GET /api/v1/health/live` returns HTTP 200 with JSON payload (`{"status": "ok", "version": "1.0.0"}`).
  3. `GET /api/v1/health/ready` returns HTTP 200/503 reflecting actual dependency readiness (unimplemented checks explicitly marked).
  4. Environment variables validate on boot via Pydantic; missing required variables abort startup cleanly.
  5. Pytest suite passes with 100% success on initial endpoints.
- **Verification Command**:
  ```powershell
  pytest tests/unit/test_health.py -v
  ```

---

### Phase 2: MQTT Broker Ingestion & MongoDB Persistence
- **Criteria**:
  1. Mosquitto accepts local MQTT client connections.
  2. FastAPI MQTT subscriber receives telemetry on `motorguard/v1/+/telemetry`.
  3. Valid payloads are inserted into MongoDB collection `telemetry`.
  4. Duplicate `event_id` transmissions are safely dropped without throwing errors.
  5. Invalid schemas (e.g. negative current or out-of-range temperature) are rejected and logged.
- **Verification Command**:
  ```powershell
  pytest tests/integration/test_mqtt_ingestion.py -v
  ```

---

### Phase 3: Real-Time Dashboard & Asset Views
- **Criteria**:
  1. React frontend builds cleanly with Vite and TypeScript (`npm run build`).
  2. Dashboard displays motor cards with real-time live readings updating via WebSockets.
  3. Device offline/stale status indicators change dynamically when heartbeats cease.
  4. Time-series sparklines display historical temperature, current, and vibration.
  5. Simulator data is visibly badged as `SIMULATOR`.

---

### Phase 4: Roles, Alerts & Maintenance Records
- **Criteria**:
  1. Users authenticate with username and password, receiving signed JWT tokens.
  2. Role hierarchy enforced on server: `Operator` cannot access user management or create maintenance records.
  3. Simulated threshold violation triggers an active alert record in MongoDB.
  4. Technician user can acknowledge and resolve alerts with technician notes.
- **Verification Command**:
  ```powershell
  pytest tests/integration/test_rbac_alerts.py -v
  ```

---

### Phase 5: Physical ESP32 Hardware Integration
- **Criteria**:
  1. ESP32 boots, calibrates ACS712 zero offset, and connects to local Wi-Fi.
  2. ESP32 publishes live sensor readings adhering strictly to `docs/telemetry-contract.md`.
  3. Readings are recorded in MongoDB and display on the React dashboard in real-time.
  4. Sensor disconnections (e.g. unplugging DHT11) report `sensor_status: DISCONNECTED` without faking `0.0`.

---

### Phase 6: Edge Impulse On-Device TinyML
- **Criteria**:
  1. Exported model `#1133176` executes on ESP32 in $< 10\text{ ms}$.
  2. Live inference outputs `healthy`, `warning`, or `critical` with real probabilities.
  3. Known validation test vectors produce identical outputs on PC and ESP32 hardware.

---

### Phase 7: Fault-Tolerance & Reliability Verification
- **Criteria**:
  1. Broker restart: ESP32 and backend reconnect automatically with exponential backoff.
  2. Gateway internet disconnected: Local dashboard and MongoDB ingestion continue functioning.
  3. Stale detection: Powering off ESP32 transitions status from `online` $\rightarrow$ `stale` (15s) $\rightarrow$ `offline` (35s via LWT/timeout).

---

### Phase 8: Production Release & Gateway Deployment
- **Criteria**:
  1. `docker compose -f infrastructure/docker-compose.yml up -d` starts full stack cleanly.
  2. Container health checks for MongoDB and Mosquitto report `healthy`.
  3. Remote access tested over authenticated VPN/reverse proxy without exposing raw ports.
  4. Backup snapshot script successfully dumps and restores database.
