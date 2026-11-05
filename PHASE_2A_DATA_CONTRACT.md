# MotorGuard — Phase 2A End-to-End Data Contract Specification

**Status:** AUDIT COMPLETE — CONTRACT BREACHES DOCUMENTED  
**Mode:** Hardware-Independent Architecture Verification  
**Date:** 2026-10-03  

---

## 1. Architectural Dataflow Overview

The MotorGuard system operates across seven distinct data-processing tiers:

```text
[ADXL345 / ACS712 / DS18B20]
              ↓ (I2C / ADC / 1-Wire)
[ESP32 Firmware Internal Buffer]
       ↙                     ↘
(100 Hz ML Window)       (1 Hz Serial / MQTT JSON)
       ↓                             ↓
[Edge Impulse TinyML]         [FastAPI Backend (/api/telemetry)]
       ↓                             ↓
(Class & Confidence)          (Enriched Health & RUL)
       ↘                             ↓
       [FastAPI Telemetry Processing Engine]
              ↙                      ↘
   [MongoDB Persistence]      [WebSocket Broadcaster (/ws/live)]
                                     ↓
                              [React Dashboard UI]
```

---

## 2. Multi-Tier Schema & Contract Specification

### Tier 1: Firmware Internal Sensor & ML Input Buffer
- **Source:** `firmware/esp32_motor_node/esp32_motor_node.ino`
- **Buffer:** `features[300]` (Float array)
- **Shape:** 100 sample frames $\times$ 3 channels = 300 floats

| Channel Index | Channel Name | Physical Quantity | Raw Sensor Unit | Buffer Unit | Sampling Interval |
|---|---|---|---|---|---|
| `Axis 0` | `temperature_C` | Temperature | °C (DS18B20) | °C | 1000 ms (repeated 100x) |
| `Axis 1` | `vibration_g` | Dynamic Vibration Accel | $\text{m/s}^2$ (ADXL345) | $g$ ($a_{\text{dyn}} / 9.81$) | 10 ms (target) / ~12 ms (actual) |
| `Axis 2` | `current_A` | Motor Current | ADC Raw (ACS712) | Amperes ($A$) | 10 ms (target) / ~12 ms (actual) |

---

### Tier 2: Firmware Output Telemetry (MQTT & Serial)
- **Source:** `firmware/esp32_motor_node/esp32_motor_node.ino:283-305`
- **MQTT Topic:** `motors/MTR-001/data`
- **Serial Output:** `[MQTT Publish -> motors/MTR-001/data] { ... }`
- **Rate:** 1.0 Hz (Every 1000 ms)

```json
{
  "motor_id": "MTR-001",
  "temperature_c": 35.50,
  "current_a": 0.420,
  "vibration_g": 0.1280,
  "vibration_mm_s": 1.256,
  "ai_class": "normal",
  "ai_confidence": 0.950,
  "energy_wh": 12.3456
}
```

| Field | Type | Expected Physical Unit | Actual Formula in Code | Contract Status |
|---|---|---|---|---|
| `motor_id` | String | Identifier (`MTR-XXX`) | `#define MOTOR_ID "MTR-001"` | **VALID** |
| `temperature_c` | Float | Degrees Celsius (°C) | `temperature_C` | **VALID** |
| `current_a` | Float | Amperes ($A$) | `readCurrent()` (average of 20 samples) | **VALID** |
| `vibration_g` | Float | Acceleration in $g$ | `readVibration()` | **VALID** |
| `vibration_mm_s` | Float | Velocity in $\text{mm/s}$ | `vibration * 9.81f` | **BREACH** (Actually $\text{m/s}^2$ acceleration!) |
| `ai_class` | String | Edge Impulse Class | `ai_class.c_str()` (`critical`, `fault`, `normal`) | **VALID** |
| `ai_confidence` | Float | Probability ($0.0 - 1.0$) | `highestScore` | **VALID** |
| `energy_wh` | Float | Watt-hours ($\text{Wh}$) | Energy accumulator | **VALID** |

---

### Tier 3: Serial Bridge Parser Contract
- **Source:** `backend_example/serial_bridge.py`
- **Expected Input:** Direct JSON line (`{ ... }`) or Regex pattern `Motor ID : ...`
- **Contract Breach:** Firmware prepends `[MQTT Publish -> motors/MTR-001/data] `. Parser does not match `line.startswith("{")`. **100% telemetry dropped on USB Serial.**

---

### Tier 4: FastAPI Telemetry Ingestion Contract
- **Source:** `backend_example/main.py:422-438`
- **Endpoint:** `POST /api/telemetry` & `POST /api/test/sensor-data`
- **Contract Input Payload:** Dict / Pydantic schema

| Field | Ingestion Fallback | Required? | Usage in Backend |
|---|---|---|---|
| `motor_id` | Defaults to `"MTR-001"` | Optional | Cache key & MongoDB filter |
| `temperature_c` | Defaults to `30.0` | Optional | Used in `calculate_rul_and_health` & `evaluate_alerts` |
| `vibration_mm_s` | Falls back to `vibration_g * 9.81` | Optional | Primary metric for health score & alert thresholds |
| `current_a` | Defaults to `0.0` | Optional | Persisted to DB; **IGNORED by ML health formula!** |
| `anomaly_score` | Defaults to `0.0` | Optional | Degrades health by `- (anomaly * 30.0)` |
| `ai_class` | Defaults to `"NORMAL"` | Optional | Metadata passthrough |
| `ai_confidence` | Defaults to `0.95` | Optional | Metadata passthrough |

---

### Tier 5: MongoDB Document Schema Contract
- **Collections:** `telemetry`, `alerts`, `users`

#### `telemetry` Collection Document:
```json
{
  "_id": "ObjectId(...)",
  "motor_id": "MTR-001",
  "temperature_c": 35.50,
  "current_a": 0.420,
  "vibration_g": 0.1280,
  "vibration_mm_s": 1.256,
  "ai_class": "normal",
  "ai_confidence": 0.950,
  "energy_wh": 12.3456,
  "health_score": 91.8,
  "failure_probability": 0.09,
  "rul_days": 165,
  "server_timestamp": "2026-10-03T15:00:00.000Z"
}
```

#### `alerts` Collection Document:
```json
{
  "_id": "ObjectId(...)",
  "id": "ALT-1790930000",
  "motor_id": "MTR-001",
  "motor_name": "Main Compressor Motor",
  "severity": "critical",
  "sensor": "Vibration",
  "message": "Critical vibration detected (> 7.0 mm/s) - Bearing failure risk",
  "value": 7.82,
  "threshold": 7.0,
  "timestamp": "2026-10-03T15:00:00.000Z",
  "status": "active"
}
```

---

### Tier 6: Edge Impulse Model Specification Contract
- **Model Project:** `Gopesh_rathinam-project-1` (Deploy Version 3)
- **Input Dimensions:** 100 samples $\times$ 3 axes = 300 raw floats
- **Sampling Frequency:** 100 Hz ($\Delta t = 10 \text{ ms}$)
- **DSP Block:** Spectral Analysis (16-point FFT, 3 peaks, wavelets) $\rightarrow$ 39 features
- **NN Learning Block:** TFLite Micro Quantized int8 $\rightarrow$ 3 class probabilities
- **Compiled Classes:**
  1. `critical`
  2. `fault`
  3. `normal`
- **Anomaly Detection:** **DISABLED / NOT PRESENT** (`EI_CLASSIFIER_HAS_ANOMALY == 0`)

---

### Tier 7: React Frontend UI Contract
- **Source:** `motor-dashboard/src/data/mockData.js` & `pages/`

| Metric / Property | Frontend Mock Expectation | Backend / Model Actual | Contract Breach |
|---|---|---|---|
| AI Condition Class | `Healthy`, `Degrading`, `Warning`, `Critical`, `Offline` | `critical`, `fault`, `normal` | **CLASS MISMATCH** |
| Anomaly Score | Numeric float $0.0 - 1.0$ (gauge displayed) | No anomaly block ($0.0$) | **FEATURE GAP** |
| Vibration Metric | Velocity RMS in $\text{mm/s}$ ($0 - 15 \text{ mm/s}$) | Acceleration $\text{m/s}^2$ labeled as $\text{mm/s}$ | **UNIT MISMATCH** |
| Vibration Warning | $> 5.0 \text{ mm/s}$ | $> 4.5 \text{ mm/s}$ | **THRESHOLD SKEW** |
| Temperature Warning | $> 70^\circ\text{C}$ | Backend has NO warning alert | **MISSING ALERT** |
| Motor ID | `MTR-001` to `MTR-006` | Firmware only transmits `MTR-001` | Multi-node gap |

---

## 3. Summary of Contract Breaches

1. **Dimensional Integrity:** Firmware computes $g \times 9.81$ ($\text{m/s}^2$) and populates `"vibration_mm_s"`. Backend tests this value against ISO 10816 velocity limits in $\text{mm/s}$.
2. **Serial Stream Ingestion:** Serial bridge parser expects raw JSON `{...}`; firmware emits `[MQTT Publish -> ...] {...}`.
3. **ML Class Vocabulary:** Model outputs lowercase `critical`, `fault`, `normal`; frontend requires capitalized conditions (`Healthy`, `Degrading`, etc.).
4. **Anomaly Feature Reality:** Frontend SCADA renders TinyML Anomaly Score gauge; deployed model contains zero anomaly detection capability.
5. **Current Signal Dead-End:** Current is sampled at 100 Hz, averaged at 6 ms, published to MQTT, and saved to MongoDB, but backend `calculate_rul_and_health()` never uses `current` in its health calculation formula.
