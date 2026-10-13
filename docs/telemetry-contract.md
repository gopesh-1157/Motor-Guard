# MotorGuard — Telemetry Contract Specification (v1.0.0)

## 1. Scope & Design Philosophy

This document defines the strict, versioned JSON telemetry payload contract shared by **all** data producers in the MotorGuard ecosystem:
- Physical ESP32 microcontrollers
- The secondary virtual motor simulator

### Zero vs. Unavailable Principle
A missing or failing sensor reading **must never** be converted silently to `0.0`.
- An idle, de-energized motor drawing zero current produces `current_a = 0.00` with `sensor_status.current = "OK"`.
- A disconnected ACS712 sensor produces `current_a = null` with `sensor_status.current = "DISCONNECTED"`.
- Downstream logic and statistical aggregations treat `null` as missing data, avoiding artificial distortion of fleet performance averages.

---

## 2. Telemetry Schema Definition (`v1.0.0`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "MotorGuardTelemetryPayload",
  "type": "object",
  "required": [
    "schema_version",
    "event_id",
    "device_id",
    "motor_id",
    "source",
    "seq",
    "timestamp",
    "sensors",
    "sensor_status",
    "inference"
  ],
  "properties": {
    "schema_version": {
      "type": "string",
      "enum": ["1.0.0"],
      "description": "Semantic schema version for wire compatibility"
    },
    "event_id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique UUIDv4 generated at source for idempotent deduplication"
    },
    "device_id": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9_-]{3,32}$",
      "description": "Unique identifier of the physical or virtual transmitter"
    },
    "motor_id": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9_-]{3,32}$",
      "description": "Stable identifier of the monitored motor"
    },
    "source": {
      "type": "string",
      "enum": ["hardware", "simulator"],
      "description": "Origin of the telemetry stream"
    },
    "seq": {
      "type": "integer",
      "minimum": 0,
      "description": "Monotonically increasing sequence number per transmitter"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "Source sample time in ISO-8601 UTC format (must end with Z)"
    },
    "sensors": {
      "type": "object",
      "required": ["temperature_c", "current_a", "vibration_g_rms"],
      "properties": {
        "temperature_c": {
          "type": ["number", "null"],
          "minimum": -20.0,
          "maximum": 120.0,
          "description": "Chassis temperature in Celsius"
        },
        "current_a": {
          "type": ["number", "null"],
          "minimum": 0.0,
          "maximum": 30.0,
          "description": "Total DC armature current in Amperes"
        },
        "vibration_g_rms": {
          "type": ["number", "null"],
          "minimum": 0.0,
          "maximum": 16.0,
          "description": "Dynamic acceleration RMS across 3 axes in standard Earth gravity (g)"
        }
      }
    },
    "sensor_status": {
      "type": "object",
      "required": ["temperature", "current", "vibration"],
      "properties": {
        "temperature": {
          "type": "string",
          "enum": ["OK", "UNAVAILABLE", "DISCONNECTED", "OUT_OF_RANGE", "STALE"]
        },
        "current": {
          "type": "string",
          "enum": ["OK", "UNAVAILABLE", "DISCONNECTED", "OUT_OF_RANGE", "STALE"]
        },
        "vibration": {
          "type": "string",
          "enum": ["OK", "UNAVAILABLE", "DISCONNECTED", "OUT_OF_RANGE", "STALE"]
        }
      }
    },
    "inference": {
      "type": "object",
      "required": ["status", "health_status", "confidence"],
      "properties": {
        "status": {
          "type": "string",
          "enum": ["PREDICTED", "MODEL_UNAVAILABLE", "INPUT_INVALID", "SKIPPED"]
        },
        "health_status": {
          "type": "string",
          "enum": ["healthy", "warning", "critical", "unknown"]
        },
        "confidence": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 1.0
        },
        "probabilities": {
          "type": ["object", "null"],
          "properties": {
            "healthy": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
            "warning": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
            "critical": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
          }
        },
        "model_version": {
          "type": ["string", "null"]
        },
        "inference_time_ms": {
          "type": ["integer", "null"],
          "minimum": 0
        }
      }
    },
    "diagnostics": {
      "type": "object",
      "properties": {
        "wifi_rssi_dbm": { "type": ["integer", "null"] },
        "free_heap_bytes": { "type": ["integer", "null"] },
        "uptime_seconds": { "type": ["integer", "null"] }
      }
    }
  }
}
```

---

## 3. Ingestion & Validation Rules

1. **Duplicate Rejection**: The backend maintains a unique compound index on `(device_id, event_id)` in MongoDB. If an MQTT retry delivers a previously ingested `event_id`, the write operation is safely ignored without raising an error.
2. **Timestamp Bound Checks**:
   - Packets timestamped $> 5$ minutes into the future are rejected as clock-skew errors.
   - Packets timestamped $> 24$ hours in the past are accepted only into historical audit collections, not live dispatch.
3. **Device-to-Motor Association**:
   - The backend checks whether `device_id` is currently registered and bound to `motor_id`.
   - If a device attempts to publish data for an unassigned motor ID, the message is rejected and logged as a security anomaly.
4. **Consistency Enforcement**:
   - If `sensor_status.temperature != "OK"`, then `sensors.temperature_c` **must** be `null`.
   - If any sensor value is `null`, `inference.status` must be `"INPUT_INVALID"` or `"SKIPPED"`, with `inference.health_status = "unknown"`.

---

## 4. Example Payloads

### 4.1 Valid Hardware Telemetry Payload
```json
{
  "schema_version": "1.0.0",
  "event_id": "8d3e9112-9c17-483d-9d41-e946a0c5b5f2",
  "device_id": "esp32-node-001",
  "motor_id": "mtr-775-001",
  "source": "hardware",
  "seq": 1042,
  "timestamp": "2026-10-09T13:15:30.124Z",
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

### 4.2 Valid Simulator Telemetry Payload (Elevated Degradation)
```json
{
  "schema_version": "1.0.0",
  "event_id": "7fa2b6d1-4f1a-4d92-bb82-f5e13cb81a91",
  "device_id": "sim-node-002",
  "motor_id": "mtr-775-002",
  "source": "simulator",
  "seq": 540,
  "timestamp": "2026-10-09T13:15:31.000Z",
  "sensors": {
    "temperature_c": 38.8,
    "current_a": 1.72,
    "vibration_g_rms": 0.165
  },
  "sensor_status": {
    "temperature": "OK",
    "current": "OK",
    "vibration": "OK"
  },
  "inference": {
    "status": "PREDICTED",
    "health_status": "warning",
    "confidence": 0.892,
    "probabilities": {
      "healthy": 0.075,
      "warning": 0.892,
      "critical": 0.033
    },
    "model_version": "sim-physics-v1",
    "inference_time_ms": 1
  },
  "diagnostics": {
    "wifi_rssi_dbm": null,
    "free_heap_bytes": null,
    "uptime_seconds": 540
  }
}
```

### 4.3 Degraded Hardware Payload (Disconnected Vibration Sensor)
```json
{
  "schema_version": "1.0.0",
  "event_id": "c1f8329b-85d0-4bf6-9b57-195ee040b2a7",
  "device_id": "esp32-node-001",
  "motor_id": "mtr-775-001",
  "source": "hardware",
  "seq": 1043,
  "timestamp": "2026-10-09T13:15:31.124Z",
  "sensors": {
    "temperature_c": 34.3,
    "current_a": 1.14,
    "vibration_g_rms": null
  },
  "sensor_status": {
    "temperature": "OK",
    "current": "OK",
    "vibration": "DISCONNECTED"
  },
  "inference": {
    "status": "INPUT_INVALID",
    "health_status": "unknown",
    "confidence": 0.0,
    "probabilities": null,
    "model_version": "ei-motoguard-v1.0.1",
    "inference_time_ms": null
  },
  "diagnostics": {
    "wifi_rssi_dbm": -62,
    "free_heap_bytes": 184512,
    "uptime_seconds": 1043
  }
}
```

### 4.4 Example Invalid Payload & Rejection Reason
```json
{
  "schema_version": "1.0.0",
  "event_id": "bad-id-not-uuid",
  "device_id": "esp32-node-001",
  "motor_id": "mtr-775-001",
  "source": "hardware",
  "seq": 1044,
  "timestamp": "2026-10-09T13:15:32Z",
  "sensors": {
    "temperature_c": 195.0,
    "current_a": -2.5,
    "vibration_g_rms": 0.0
  },
  "sensor_status": {
    "temperature": "OK",
    "current": "OK",
    "vibration": "OK"
  },
  "inference": {
    "status": "PREDICTED",
    "health_status": "healthy",
    "confidence": 0.9
  }
}
```
**Rejection Violations**:
1. `event_id` is not a valid UUIDv4.
2. `sensors.temperature_c` (195.0°C) exceeds maximum physical bounds (120.0°C).
3. `sensors.current_a` (-2.5A) is negative; ACS712 DC current cannot be below 0.0A.
