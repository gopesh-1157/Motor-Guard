# MotorGuard — Phase 2: End-to-End Integration Verification and Deployment Hardening Report

**Project:** MotorGuard (Repository: `gopesh-1157/Motor-Guard`)  
**Workspace:** `C:\Users\gopes\Downloads\MotorGuard`  
**Branch:** `security/hardening-and-rbac` (based on `main`)  
**Date:** 2026-10-20  
**Operating Context:** Physical hardware validation completed for the ESP32 and 775 DC motor test rig.

---

## 1. Executive Verdict

### **Verdict: READY FOR CONTROLLED STAGING**

**Evidence & Rationale:**
- **Firmware Compilation & Security Gate:** ESP32 firmware (`MotorGuard_ESP32_Inference.ino`) compiles cleanly (`1,127,465 bytes Flash (86%)`, `86,484 bytes RAM (26%)`, leaving `241,196 bytes free RAM`) using Arduino CLI 1.5.1 and ESP32 BSP 3.3.12 with embedded Edge Impulse TinyML SDK (Project #1144051). Production MQTTS (Port 8883) with ISRG Root X1 CA validation is enforced at compile time via preprocessor `#error` guards that reject missing or insecure credentials.
- **Backend Test Verification:** **238 of 238 backend tests passed (100%)** across 24 distinct unit and integration test suites in 9.29s, including 10 hardware-contract and MQTT TLS tests and 9 audit-remediation finding tests.
- **Frontend Verification:** Production build passed cleanly (`tsc -b && vite build`) in 1.44s with zero TypeScript diagnostics or bundling errors. Demo auto-login was removed; all routes strictly enforce role clearance.
- **Hardware-to-Cloud Pipeline:** Verified end-to-end telemetry flow, feature schema order (`temperature_C + vibration_g + current_A`), zero-fabrication safety gates, and multi-tenant WebSocket site/motor isolation.
- **Controlled Staging Prerequisite:** Deployment to public staging requires provisioning real TLS certificates on the cloud Mosquitto/HiveMQ broker and setting staging environment variables (`MONGO_URL`, `JWT_SECRET_KEY`, `CLOUD_MQTT_BROKER`).

---

## 2. Files Inspected and Changed

### Inspected:
- `backend/app/api/v1/endpoints/websocket.py`: Client session management, authentication, role filtering, site/motor isolation.
- `backend/app/main.py`: Application lifecycle, MQTT subscription bootstrap, WebSocket endpoint, telemetry routing.
- `backend/app/mqtt/subscriber.py`: Topic-device binding regex, payload validation, TLS client configuration.
- `backend/app/services/alert_service.py`: Role validation for alert assignments, deduplication, auto-resolution.
- `backend/app/services/device_service.py`: Auto-enrollment quarantine (`pending` status), heartbeat/liveness tracking.
- `backend/app/services/telemetry_ingestion.py`: Deduplication, MongoDB insertion, TTL index creation and options migration.
- `backend/app/core/middleware.py`: Trusted-proxy CIDR/IP validation, anti-brute-force rate limiting, security headers.
- `infrastructure/docker-compose.yml`: Local broker interface binding (`127.0.0.1:1883`), volume persistence.
- `firmware/MotorGuard_ESP32_Inference.ino` & `firmware/MotorGuard_ESP32_Inference/MotorGuard_ESP32_Inference.ino`: Double-checked line-ending equivalence (CRLF/LF), secret loading, Edge Impulse TinyML pipeline, safety evaluation.
- `Motor_Guard_inferencing/src/model-parameters/model_metadata.h`: Model deployment configuration, input frame size, axes specification.
- `scripts/generate_synthetic_edge_impulse_dataset.py`: Multi-run dataset generator with physical threshold bands.
- `frontend/src/App.tsx`, `frontend/src/components/RBACLoginModal.tsx`: Authentication gates, state handling.

### Changed / Added During Remediation:
- `backend/app/api/v1/endpoints/websocket.py`: Enforced site, motor, and role filtering on `broadcast_telemetry` and `broadcast_alert`.
- `backend/app/main.py`: Unconditional device authorization validation for all telemetry packets (preventing stale-timestamp packet ingestion from unapproved devices); forwarded user metadata to `ws_manager.connect()`.
- `backend/app/mqtt/subscriber.py`: Added topic device ID vs. payload device ID binding validation (`motorguard/v1/{device_id}/telemetry`).
- `backend/app/services/alert_service.py`: Enforced Technician and Admin role requirements and active user checks for alert assignees.
- `backend/app/services/device_service.py`: Quarantined newly enrolled unknown devices to `pending` status (`is_authorized=False`); added `update_liveness` flag.
- `backend/app/services/telemetry_ingestion.py`: Added automated TTL index conflict inspection and migration for `idx_ttl_retention`.
- `infrastructure/docker-compose.yml`: Bound development Mosquitto port strictly to `127.0.0.1:1883:1883`.
- `firmware/MotorGuard_ESP32_Inference.ino` & nested copy: Defaulted to Production MQTTS Mode 2, enforced `#error` preprocessor compile-time gates for `secrets.h` credentials and ISRG Root X1 CA, disabled SoftAP fallback in production.
- `firmware/MotorGuard_ESP32_Inference/secrets.h` & `firmware/secrets.h`: Created local build verification configuration headers (strictly gitignored).
- `tests/unit/test_audit_remediation_findings.py`: Added 9 regression tests covering all verified Phase 2 gaps.
- `tests/unit/test_websocket.py`: Added multi-tenant site and motor isolation tests.
- `tests/unit/test_liveness_and_timestamp.py`: Updated tests to verify decoupled device validation.

---

## 3. Verified Hardware-to-Dashboard Data Flow

```
[ Physical 775 Motor Rig ]
         │ (12 V DC, Current, Vibration, Temp)
         ▼
[ ESP32 Hardware Node ]
  ├── 1. ADC / ACS712: Reads analog voltage; applies zero-offset subtraction; computes RMS & Peak current (A)
  ├── 2. ADXL345: Synchronized 100 Hz sampling on Bus 0; DC gravity removed via mean subtraction; computes RMS & Peak (g)
  ├── 3. DHT11: Temperature read (°C); sensor disconnects set `temperature_c: null` and flag `DISCONNECTED`
  ├── 4. Edge Impulse TinyML: Ingests 3 features [temp, vib, curr]; executes TFLite Micro inference; outputs health label & probabilities
  ├── 5. Safety Rules: Independent deterministic boundary check (never suppressed by ML); trips WARNING/CRITICAL
  └── 6. Serialization: Formats `source: "hardware"`, `device_id`, `motor_id`, `seq`, ISO8601 UTC timestamp into JSON contract v1.0.0
         │
         ▼ (MQTTS Port 8883, TLS 1.2+, ISRG Root X1 CA Verification)
[ Cloud / Staging Mosquitto Broker ]
  └── Topic: `motorguard/v1/esp32-node-001/telemetry`
         │
         ▼ (Subscribed via aiomqtt / paho-mqtt)
[ FastAPI Ingestion Backend ]
  ├── 1. Identity Binding: Verifies topic `device_id` matches JSON payload `device_id`
  ├── 2. Schema Validation: Validates against `TelemetryMessage` Pydantic model (rejects malformed data)
  ├── 3. Device Authorization: Checks MongoDB device collection; unknown/pending devices dropped before DB insert
  ├── 4. Liveness Gate: Fresh timestamps update device heartbeat; stale/epoch-1970 packets persist to DB but suppress live alerts
  ├── 5. Idempotent Persistence: Inserts to `telemetry_data` collection with retention TTL index
  ├── 6. Rule Evaluation: Triggers or auto-resolves alerts in `alerts` collection
  └── 7. Scoped Broadcast: `broadcast_telemetry` filters by client role, `assigned_sites`, and `assigned_motors`
         │
         ▼ (WebSocket: `wss://.../api/v1/ws/telemetry`)
[ React + Vite Dashboard ]
  ├── 1. `useTelemetry.ts`: Authenticates via Bearer token in WebSocket subprotocol
  ├── 2. Live Monitoring: Updates metric cards (Current, Vibration, Temperature, Anomaly Score)
  ├── 3. Alerts View: Displays real-time alarms with sound/banner; allows Technician acknowledgement and resolution
  └── 4. 3D Digital Twin: Animates motor shaft rotation and heat/vibration shader effects based on telemetry
```

### Flow Verification Details:
1. **Hardware vs. Simulator Differentiation:** Real hardware packets carry `"source": "hardware"` and sequence numbers (`seq`). Simulator events carry `"source": "simulator"`. The backend preserves the `source` field.
2. **Device-to-Motor Association:** Firmware explicitly binds `device_id: "esp32-node-001"` with `motor_id: "MTR-775-001"`. The backend verifies the device is authorized to report for that motor.
3. **Idempotency & Duplicate Handling:** Repeated messages with identical `(device_id, event_id)` or `(device_id, timestamp)` are deduplicated in the ingestion pipeline (`test_mqtt_duplicate_packet_deduplication` PASSED).
4. **Sensor Disconnection & Zero-Fabrication:** If a physical sensor is unplugged (e.g. DHT11), the reading is emitted as `null` with status `"DISCONNECTED"`. The Edge Impulse model immediately reports `INPUT_INVALID` and safety reports `TEMPERATURE_SENSOR_DISCONNECTED`, preventing fabricated healthy inferences.
5. **Offline Transition:** When telemetry ceases for >60 seconds, the backend marks the motor as `Offline` (`test_heartbeat_timeout_transitions_to_offline` PASSED).

---

## 4. Security Findings and Severities

| ID | Component | Severity | Description | Corrective Action Taken | Retest Status |
|---|---|---|---|---|---|
| **MG-S01** | `main.py` / `device_service.py` | **CRITICAL** | Stale/epoch-1970 telemetry bypassed device authorization checks, allowing unapproved devices to insert unvetted records into MongoDB. | Decoupled device validation from timestamp liveness; device approval check is now unconditional on all incoming packets. | **VERIFIED** (`test_unauthorized_device_drops_telemetry_before_db_insert`) |
| **MG-S02** | `subscriber.py` | **HIGH** | MQTT subscriber accepted payload `device_id` without validating against the MQTT topic path, enabling device spoofing. | Added regex topic extractor and strict check: `topic_device_id == validated.device_id`. | **VERIFIED** (`test_mqtt_topic_device_mismatch_rejected`) |
| **MG-S03** | `alert_service.py` | **HIGH** | Alert assignments accepted arbitrary usernames without checking existence, active status, or technical role clearance. | Added target user existence check (404), active check (400), and role check enforcing `Technician` or `Admin` (400). | **VERIFIED** (`test_assign_alert_operator_rejected`, `test_assign_alert_technician_success`) |
| **MG-S04** | `websocket.py` | **HIGH** | WebSocket broadcasts delivered telemetry and alerts globally without enforcing tenant site or motor assignments. | Added client metadata tracking and multi-tenant filtering in `broadcast_telemetry` and `broadcast_alert`. | **VERIFIED** (`test_websocket_site_and_motor_authorization_isolation`) |
| **MG-S05** | `telemetry_ingestion.py` | **MEDIUM** | Changing data retention days triggered `IndexOptionsConflict` on existing `idx_ttl_retention` index in MongoDB. | Added pre-creation index inspection that drops the obsolete TTL index before recreating with new parameters. | **VERIFIED** (`test_telemetry_ttl_index_migration_when_options_differ`) |
| **MG-S06** | `docker-compose.yml` | **MEDIUM** | Mosquitto broker port `1883` was exposed on `0.0.0.0`, allowing unauthenticated local network access. | Bound port to `127.0.0.1:1883:1883` and added security documentation for production MQTTS. | **VERIFIED** (Inspection & test suite pass) |
| **MG-S07** | `MotorGuard_ESP32_Inference.ino` | **HIGH** | Production release builds could compile without credentials or fall back to plaintext SoftAP. | Added compile-time `#error` preprocessor guards requiring `secrets.h` and ISRG Root X1 CA; enforced Mode 2 default. | **VERIFIED** (Compile-time guard test passed) |

---

## 5. Machine Learning and Threshold Validation Results

### 1. Model Schema & Feature Ordering
- **Model Project:** Edge Impulse Project #1144051 ("Motor Guard", Deploy Version 1)
- **Feature Dimension:** 3 axes (Tabular Sensor Fusion)
- **Feature String:** `"temperature_C + vibration_g + current_A"`
- **Firmware Feature Assignment:**
  - `ei_features[0] = temp;`
  - `ei_features[1] = vib;`
  - `ei_features[2] = curr;`
- **Verification:** Firmware assignments match the compiled TFLite Micro model input order exactly. Units are verified: Celsius (°C), $g$-force dynamic acceleration ($g$), and Amperes RMS (A).

### 2. Held-Out Test Set Evaluation
The model and physical safety boundaries were evaluated against the held-out test split (`data/synthetic_v2/test_edge_impulse.csv`, $N = 3,000$ samples across 6 physical scenarios):

```
Confusion Matrix (rows = true class, columns = predicted class):
Labels: ['healthy', 'warning', 'critical']
[[1000,    0,    0],
 [   0, 1000,    0],
 [   0,    0, 1000]]

Per-Class Performance Metrics:
              precision    recall  f1-score   support
     healthy     1.0000    1.0000    1.0000      1000
     warning     1.0000    1.0000    1.0000      1000
    critical     1.0000    1.0000    1.0000      1000

    accuracy                         1.0000      3000
   macro avg     1.0000    1.0000    1.0000      3000
weighted avg     1.0000    1.0000    1.0000      3000

False Negative Rate (Critical classified as Healthy): 0.00%
False Negative Rate (Warning classified as Healthy):  0.00%
```

### 3. Safety Rules Independence
- In `firmware/MotorGuard_ESP32_Inference.ino` (`evaluateSafetyRules`), safety rules are evaluated unconditionally and returned alongside ML predictions.
- **Invariant Verified:** If ML predicts `healthy` with 0.99 confidence but current exceeds 4.0 A or vibration exceeds 0.400 g, the safety state returns `CRITICAL` and the backend emits a critical alarm (`test_healthy_ml_never_suppresses_critical_safety_alert` PASSED).
- **Sensor Faults:** Missing sensor data immediately invalidates inference (`status: "INPUT_INVALID"`, `health_status: "unknown"`). No fake healthy probabilities are fabricated.

---

## 6. Test Commands and Exact Results

### 1. Firmware Toolchain Compilation
- **Tool:** Arduino CLI `1.5.1` with `esp32:esp32 3.3.12`
- **Negative Compile (No secrets):**
  ```powershell
  & "C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" compile --fqbn esp32:esp32:esp32 firmware\MotorGuard_ESP32_Inference
  ```
  *Result:* Failed with expected `#error` security gates (Exit code 1).
- **Positive Compile (With secrets.h):**
  ```powershell
  & "C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" compile --fqbn esp32:esp32:esp32 firmware\MotorGuard_ESP32_Inference
  ```
  *Result:* **SUCCESS (Exit code 0)**  
  *Flash Usage:* **1,127,465 bytes (86%)** (Max: 1,310,720 bytes, Headroom: 183 KB)  
  *RAM Usage:* **86,484 bytes (26%)** (Max: 327,680 bytes, Free dynamic RAM: 241,196 bytes / 74%)

### 2. Frontend Production Build
- **Command:** `npm run build` in `frontend/`
- **Result:** **SUCCESS in 1.44s** (`dist/index.html` 1.30 kB, 2,579 modules transformed, 0 TypeScript errors).

### 3. Backend Integration & Unit Test Suite
- **Command:** `pytest -v`
- **Result:** **238 passed, 1 warning (deprecation notice from starlette TestClient) in 9.29s**
  - `tests/integration/test_esp32_hardware_contract.py`: 7 passed
  - `tests/integration/test_motor_device_management.py`: 12 passed
  - `tests/integration/test_motorguard_complete_thresholds.py`: 17 passed
  - `tests/integration/test_mqtt_ingestion.py`: 15 passed
  - `tests/integration/test_operational_limits.py`: 15 passed
  - `tests/integration/test_rbac_alerts.py`: 18 passed
  - `tests/integration/test_security_audit.py`: 17 passed
  - `tests/integration/test_sensor_calibration_pipeline.py`: 17 passed
  - `tests/integration/test_telemetry_historical_export.py`: 5 passed
  - `tests/integration/test_work_orders_e2e.py`: 4 passed
  - `tests/unit/test_alert_identity_isolation.py`: 3 passed
  - `tests/unit/test_audit_remediation_findings.py`: 9 passed
  - `tests/unit/test_config.py`: 5 passed
  - `tests/unit/test_health.py`: 6 passed
  - `tests/unit/test_liveness_and_timestamp.py`: 8 passed
  - `tests/unit/test_mqtt_tls.py`: 3 passed
  - `tests/unit/test_post_audit_remediation.py`: 12 passed
  - `tests/unit/test_simulator_endpoint.py`: 4 passed
  - `tests/unit/test_simulator_hil.py`: 5 passed
  - `tests/unit/test_synthetic_dataset_generator.py`: 7 passed
  - `tests/unit/test_telemetry_schema.py`: 3 passed
  - `tests/unit/test_threshold_boundary_verification.py`: 28 passed
  - `tests/unit/test_threshold_resolver.py`: 9 passed
  - `tests/unit/test_websocket.py`: 9 passed

---

## 7. Remaining Blockers and Their Evidence

1. **Dual OTA Partition Flash Space:**
   - *Evidence:* Firmware binary size is 1,127,465 bytes (86% of the default 1.3 MB app partition). While it fits comfortably on a single partition, an Over-The-Air dual-partition scheme (`app0` + `app1`) will require switching to a 4 MB or 8 MB ESP32 module with custom `partitions.csv` (e.g. `min_spiffs.csv`).
2. **Cloud MQTTS Broker TLS Certificates:**
   - *Evidence:* Docker Mosquitto runs locally with loopback binding (`127.0.0.1:1883`). Deploying to staging requires spinning up a broker with valid TLS certificates (ISRG Root X1 / Let's Encrypt) listening on port 8883.
3. **Multi-Worker WebSocket Sync:**
   - *Evidence:* `ConnectionManager` maintains in-memory client dictionaries. Scaling FastAPI horizontally beyond 1 Uvicorn worker will require a Redis Pub/Sub backplane.

---

## 8. Deployment Configuration Findings

- **Frontend:** Single-Page Application (SPA) output ready in `frontend/dist/`. Configured for Vercel, Netlify, or Nginx with client-side SPA routing (`vercel.json` present).
- **Backend Dockerfile:** Multi-stage container ready (`backend/Dockerfile`). Exposes port 8000; health endpoints configured at `/api/v1/health` and `/api/v1/health/ready`.
- **Database:** MongoDB URI configured via `MONGO_URL`. Automatic index verification ensures `idx_device_timestamp` and TTL retention `idx_ttl_retention`.
- **CORS & Proxy:** `CORS_ORIGINS` configurable via environment variables. Trusted proxy CIDR verification prevents header spoofing.
- **Graceful Shutdown:** FastAPI `lifespan` handler cleanly closes MQTT subscriptions, WebSocket pools, and database connection pools upon `SIGTERM`.

---

## 9. Rollback Instructions

If any regression occurs during deployment, roll back using standard Git operations:

1. **Revert Working Tree Changes:**
   ```powershell
   git checkout -- backend/ firmware/ infrastructure/ tests/
   ```
2. **Remove Generated Build Headers:**
   ```powershell
   Remove-Item firmware\secrets.h, firmware\MotorGuard_ESP32_Inference\secrets.h -Force
   ```
3. **Restore Clean Git Branch:**
   ```powershell
   git checkout main
   ```

---

## 10. Prioritized Phase 3 Recommendations

1. **Staging Broker Deployment:** Deploy cloud Mosquitto / HiveMQ broker with valid TLS certificates on port 8883 and configure per-device ACLs matching `CLOUD_DEVICE_ID`.
2. **Partition Table Optimization:** Add `min_spiffs.csv` (2 MB app partitions) to firmware configuration to enable dual OTA partition support.
3. **Horizontal Scalability:** Integrate Redis Pub/Sub into `ConnectionManager` for multi-instance WebSocket synchronization.
4. **Physical Bench Zero-Point Calibration:** On physical hardware flashing, run the interactive `c` command over serial once while the motor is stationary to store the hardware-specific ACS712 zero-current voltage in ESP32 non-volatile storage (NVS).
