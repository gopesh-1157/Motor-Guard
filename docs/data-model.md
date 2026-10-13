# MotorGuard — Persistent Data Model & MongoDB Schema

## 1. Overview & Identity Strategy

MotorGuard utilizes **MongoDB** on the local gateway for all persistent state. 

### Core Identity Rules
- **Motors**: Identified by an immutable, human-readable identifier `motor_id` (e.g., `MTR-775-001`).
- **Devices**: Identified by a unique hardware identifier `device_id` (e.g., `ESP32-NODE-001` or `SIM-NODE-002`).
- **Decoupling**: A physical ESP32 device can be reassigned to a different motor during maintenance without corrupting the historical telemetry of either motor.
- **No IP Identities**: Dynamic DHCP IP addresses are recorded strictly as temporal diagnostics and never as foreign keys.

---

## 2. Collections & Document Schemas

### 2.1 `users` Collection
Stores credentials, access roles, and site scopes.
```json
{
  "_id": "ObjectId('...')",
  "username": "tech_dave",
  "email": "dave@factory.local",
  "password_hash": "$2b$12$e8YQJ...",
  "role": "Technician",
  "assigned_sites": ["SITE-PLANT-A"],
  "assigned_motors": ["MTR-775-001", "MTR-775-002"],
  "is_active": true,
  "created_at": "2026-10-01T08:00:00.000Z",
  "last_login_at": "2026-10-09T09:15:00.000Z"
}
```
**Roles**:
- `Admin`: Full system configuration, user management, site/motor creation, device credential rotation.
- `Manager`: Fleet reports, operational summaries, alert audit review, maintenance scheduling.
- `Technician`: Live sensor investigation, alert acknowledgement/resolution, work-order logging, sensor zero-calibration.
- `Operator`: View-only live dashboard monitoring for assigned motors and alert reporting.

**Indexes**:
- `{"username": 1}` (Unique)
- `{"email": 1}` (Unique)

---

### 2.2 `sites` Collection
Physical plant or workshop locations.
```json
{
  "_id": "SITE-PLANT-A",
  "name": "Assembly Hall 1 - Line 3",
  "location": "Sector 4, Building B",
  "contact_person": "Dave Miller",
  "created_at": "2026-10-01T08:00:00.000Z"
}
```
**Indexes**:
- `{"_id": 1}` (Primary key)

---

### 2.3 `motors` Collection
Physical asset master records.
```json
{
  "_id": "MTR-775-001",
  "motor_id": "MTR-775-001",
  "site_id": "SITE-PLANT-A",
  "name": "Drill Feed Actuator Motor #1",
  "model": "RS-775 High-Torque DC Motor",
  "rated_voltage_v": 12.0,
  "rated_current_a": 2.5,
  "overcurrent_limit_a": 4.0,
  "max_temp_c": 50.0,
  "max_vibration_g": 0.200,
  "installation_date": "2026-09-15T00:00:00.000Z",
  "assigned_device_id": "esp32-node-001",
  "health_status": "healthy",
  "operational_state": "RUNNING",
  "total_runtime_hours": 142.5,
  "notes": "Installed with rubber anti-vibration damping mount."
}
```
**Indexes**:
- `{"motor_id": 1}` (Unique)
- `{"site_id": 1}`
- `{"assigned_device_id": 1}`

---

### 2.4 `devices` Collection
Edge microcontrollers and virtual transmitters.
```json
{
  "_id": "esp32-node-001",
  "device_id": "esp32-node-001",
  "assigned_motor_id": "MTR-775-001",
  "type": "hardware",
  "hardware_model": "ESP32-WROOM-32D",
  "mac_address": "C4:4F:33:18:9B:A2",
  "firmware_version": "1.0.1",
  "status": "online",
  "last_seen_at": "2026-10-09T13:15:30.124Z",
  "last_ip": "192.168.1.145",
  "last_wifi_rssi_dbm": -62,
  "registered_at": "2026-10-01T10:00:00.000Z"
}
```
**Indexes**:
- `{"device_id": 1}` (Unique)
- `{"status": 1}`
- `{"last_seen_at": 1}`

---

### 2.5 `telemetry` Collection
High-volume time-series sensor events and Edge Impulse predictions.
```json
{
  "_id": "ObjectId('...')",
  "event_id": "8d3e9112-9c17-483d-9d41-e946a0c5b5f2",
  "device_id": "esp32-node-001",
  "motor_id": "MTR-775-001",
  "source": "hardware",
  "seq": 1042,
  "timestamp": "2026-10-09T13:15:30.124Z",
  "server_received_at": "2026-10-09T13:15:30.145Z",
  "sensors": {
    "temperature_c": 34.2,
    "current_a": 1.15,
    "vibration_g_rms": 0.082
  },
  "sensor_status": {
    "temperature": "OK",
    "current": "OK",
    "vibration": "OK"
  },
  "inference": {
    "status": "PREDICTED",
    "health_status": "healthy",
    "confidence": 0.985,
    "probabilities": {
      "healthy": 0.985,
      "warning": 0.015,
      "critical": 0.000
    },
    "model_version": "ei-motoguard-v1.0.1",
    "inference_time_ms": 3
  },
  "diagnostics": {
    "wifi_rssi_dbm": -62,
    "free_heap_bytes": 184512,
    "uptime_seconds": 1042
  }
}
```
**Compound Indexes**:
- `{"device_id": 1, "event_id": 1}` (Unique, for deduplication)
- `{"motor_id": 1, "timestamp": -1}` (Optimizes time-range and historical chart queries)
- `{"timestamp": 1}` (TTL index support for telemetry retention, e.g., 90 days)

---

### 2.6 `alerts` Collection
Safety threshold violations and condition warnings.
```json
{
  "_id": "ObjectId('...')",
  "alert_id": "ALT-20261009-001",
  "motor_id": "MTR-775-001",
  "device_id": "esp32-node-001",
  "severity": "CRITICAL",
  "trigger_type": "THRESHOLD_OVERCURRENT",
  "trigger_value": 4.15,
  "threshold_limit": 4.0,
  "unit": "A",
  "message": "Overcurrent trip limit exceeded: measured 4.15 A (limit 4.0 A)",
  "state": "ACTIVE",
  "triggered_at": "2026-10-09T13:14:02.000Z",
  "acknowledged_at": null,
  "acknowledged_by": null,
  "resolved_at": null,
  "resolution_notes": null
}
```
**Indexes**:
- `{"motor_id": 1, "state": 1}`
- `{"severity": 1, "state": 1}`
- `{"triggered_at": -1}`

---

### 2.7 `maintenance_records` Collection
Service interventions, bearing lubrications, and replacements.
```json
{
  "_id": "ObjectId('...')",
  "record_id": "MAINT-202610-001",
  "motor_id": "MTR-775-001",
  "service_type": "INSPECTION",
  "technician_id": "tech_dave",
  "technician_name": "Dave Miller",
  "summary": "Investigated elevated vibration reading (0.165 g)",
  "details": "Re-tightened motor mounting bracket bolts; cleaned shaft collar. Post-maintenance vibration normalized to 0.075 g.",
  "parts_replaced": ["M4 mounting screws (4x)"],
  "downtime_minutes": 25,
  "timestamp": "2026-10-09T14:00:00.000Z"
}
```
**Indexes**:
- `{"motor_id": 1, "timestamp": -1}`
- `{"technician_id": 1}`

---

### 2.8 `audit_events` Collection
Administrative, security, and configuration change records.
```json
{
  "_id": "ObjectId('...')",
  "event_type": "DEVICE_REASSOCIATION",
  "performed_by": "admin_user",
  "ip_address": "192.168.1.10",
  "target_entity": "devices",
  "target_id": "esp32-node-001",
  "changes": {
    "assigned_motor_id": {"old": "MTR-775-001", "new": "MTR-775-002"}
  },
  "timestamp": "2026-10-09T15:00:00.000Z"
}
```
**Indexes**:
- `{"timestamp": -1}`
- `{"performed_by": 1}`
