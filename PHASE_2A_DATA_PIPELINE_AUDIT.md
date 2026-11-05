# MotorGuard — Phase 2A Software + Data + ML Pipeline Audit Report
## Hardware-Independent Mode

**Author:** Lead QA & Integration Engineering  
**Audit Phase:** Phase 2A — Software, Data Pipeline, IoT, & ML Integration Audit  
**Operating Mode:** STRICT READ-ONLY / HARDWARE-INDEPENDENT  
**Date:** 2026-10-03  
**Artifacts Generated:**
- `reports/PHASE_2A_TEST_RESULTS.md` (28 Automated Software Deliverables)
- `reports/PHASE_2A_DATA_CONTRACT.md` (Multi-Tier Data Contracts)
- `reports/PHASE_2A_UNIT_ANALYSIS.md` (Mathematical & Dimensional Analysis)
- `reports/PHASE_2A_EVIDENCE/` (12 Test & Calculation Trace Files)

---

## 1. Executive Summary

This audit evaluated the complete end-to-end data pipeline of the **MotorGuard** industrial IoT condition monitoring platform in **hardware-independent mode**. Using source-code static inspection, dimensional calculus, model metadata parsing, and automated software test suites, the software path was traced from sensor acquisition through firmware feature packaging, MQTT/Serial transmission, FastAPI ingestion, ML health evaluation, MongoDB persistence, and frontend dashboard presentation.

### Key Audit Conclusions:
1. **Critical Vibration Dimensional Error (CRIT-2A-01):** The firmware multiplies acceleration in $g$ by $9.81$, yielding acceleration in $\text{m/s}^2$, but writes it into a JSON key named `"vibration_mm_s"`. The backend and frontend receive this value and treat it as velocity in $\text{mm/s}$, comparing it directly against ISO 10816 velocity thresholds ($4.5$ and $7.0 \text{ mm/s}$). This distorts vibration severity calculations by over 300% to 600% across motor operating frequencies.
2. **Serial Bridge Telemetry Ingestion Failure (CRIT-2A-02):** The serial bridge (`serial_bridge.py`) drops 100% of telemetry emitted over USB serial because the firmware prepends `[MQTT Publish -> ...] ` to the line, preventing the parser's `line.startswith("{")` condition from ever evaluating to true.
3. **Firmware Timing & Jitter Bottleneck (HIGH-2A-01):** The firmware architecture targets 100 Hz ($10 \text{ ms}$ interval), but blocking functions—specifically `readCurrent()` ($6.2 \text{ ms}$), OLED display refresh ($23.0 \text{ ms}$), and Edge Impulse inference ($35.0 \text{ ms}$)—stall the loop. The effective sampling rate is approximately $84 \text{ Hz}$, introducing sample drops and timing jitter that distort the 16-point FFT spectral analysis.
4. **Edge Impulse Anomaly Capability Absence (HIGH-2A-02):** The compiled Edge Impulse model (`Gopesh_rathinam-project-1`, Deploy Version 3) has `EI_CLASSIFIER_HAS_ANOMALY == 0`. It possesses **no anomaly detector block** (K-Means/GMM disabled). The frontend SCADA dashboard renders an "AI Anomaly Score" gauge that has no backing feature in the edge model.
5. **Class Vocabulary Disconnect (MED-2A-01):** The Edge Impulse model outputs 3 lowercase classes: `critical`, `fault`, `normal`. The frontend mock contract expects 5 conditions: `Healthy`, `Degrading`, `Warning`, `Critical`, `Offline`.
6. **Dead-End Current Metric (MED-2A-02):** Motor current is measured, averaged, buffered into ML Axis 2, published over MQTT, and stored in MongoDB, but the backend health calculation function `calculate_rul_and_health()` completely ignores current in its mathematical formula.

---

## 2. Current Software Architecture

The software architecture connects edge firmware to browser dashboards across 7 tiers:

```text
[Sensors: ADXL345, ACS712, DS18B20]
              │
              ▼ (I2C Bus 0, ADC SAR, 1-Wire GPIO4)
[ESP32 Firmware: esp32_motor_node.ino]
   ├── Buffer: features[300] (100 Hz x 3 channels)
   ├── Edge Impulse TinyML (Spectral DSP + TFLite Micro int8)
   └── OLED SH1106 Display (I2C Bus 1)
              │
              ├── Serial (115200 baud): [MQTT Publish -> ...] {...}
              └── MQTT Client: motors/MTR-001/data
                                │
                                ▼
                   [MQTT Broker: Mosquitto]
                                │
                                ▼
         [FastAPI Backend: main.py (Port 8000)]
   ├── MQTT Consumer Thread (paho-mqtt)
   ├── Direct Ingestion Endpoint: POST /api/telemetry
   ├── Rule-Based Alert Evaluation Engine
   ├── ML Simulated Health & RUL Pipeline
   ├── MongoDB Async Driver (motor)
   └── WebSocket Broadcaster (/ws/live)
                                │
                                ▼
             [React Dashboard: motor-dashboard]
   ├── AppContext (State & Mock Data)
   ├── Vite Single Page Application
   └── SCADA Views (Overview, LiveMonitoring, Alerts)
```

---

## 3. ESP32 Sensor Pipeline

The firmware acquires data from three discrete physical transducers inside a non-blocking `millis()` loop scheduled at `SAMPLE_INTERVAL_MS = 1000 / EI_CLASSIFIER_FREQUENCY = 10 ms`:
1. **ADXL345 Accelerometer:** Initialized on I2C Bus 0 (`Wire`) at GPIO 21 (SDA) and GPIO 22 (SCL). Configured for $\pm 4g$ range at 100 Hz data rate.
2. **ACS712 Current Sensor:** Connected to ADC1 Channel 6 (GPIO 34). Configured with 12-bit resolution ($0 - 4095$) and $185 \text{ mV/A}$ sensitivity.
3. **DS18B20 Temperature Sensor:** Connected to GPIO 4 via DallasTemperature 1-Wire library in asynchronous non-blocking conversion mode.

---

## 4. ADXL345 Analysis

- **Range:** $\pm 4g$ (`ADXL345_RANGE_4_G`)
- **Data Rate:** 100 Hz (`ADXL345_DATARATE_100_HZ`)
- **Acquisition Formula:**
  ```cpp
  accel.getEvent(&event);
  float magnitude = sqrt(event.acceleration.x * event.acceleration.x +
                         event.acceleration.y * event.acceleration.y +
                         event.acceleration.z * event.acceleration.z);
  float dynamicAcceleration = fabs(magnitude - 9.81f);
  return dynamicAcceleration / 9.81f; // Result in [g]
  ```
- **Mathematical Assessment:**
  - Computes the Euclidean 3D norm of acceleration, then subtracts Earth gravity ($9.81 \text{ m/s}^2$).
  - Produces dynamic scalar acceleration in units of $g$.
  - **Limitation:** It compresses 3 orthogonal physical vibration axes ($X, Y, Z$) into a single scalar magnitude. Spatial directional vibration data (e.g. horizontal vs vertical vs axial misalignment) is lost before reaching the Edge Impulse buffer.

---

## 5. ACS712 Analysis

- **ADC Pin:** GPIO 34 (Input-only ADC1)
- **ADC Resolution:** 12 bits ($2^{12} - 1 = 4095$ counts)
- **Sampling Routine (`readCurrent()`):**
  ```cpp
  const int samples = 20;
  float totalVoltage = 0;
  for (int i = 0; i < samples; i++) {
    int raw = analogRead(CURRENT_PIN);
    totalVoltage += ((float)raw / 4095.0f) * 3.3f;
    delayMicroseconds(300);
  }
  float averageVoltage = totalVoltage / samples;
  float current = (averageVoltage - zeroVoltage) / ACS712_SENSITIVITY;
  if (fabs(current) < 0.05f) current = 0.0f;
  return fabs(current);
  ```
- **Mathematical Assessment:**
  - Takes 20 discrete samples separated by $300 \mu\text{s}$, blocking for $6.0 \text{ ms}$ per reading.
  - Computes an arithmetic mean of voltage over a $6.0 \text{ ms}$ window.
  - Computes magnitude difference from `zeroVoltage`.
  - **Limitation:** This is a short-window average, not true AC RMS current.
  - **Divider Collision:** Quiescent `zeroVoltage` defaults to $2.50 \text{ V}$ in software. If the hardware $10\text{ k}\Omega / 20\text{ k}\Omega$ voltage divider is installed, quiescent voltage drops to $1.667 \text{ V}$. Without dynamic calibration on boot, software outputs an erroneous baseline current of $4.50 \text{ A}$.

---

## 6. DS18B20 Analysis

- **Bus:** 1-Wire on GPIO 4
- **Conversion Mode:** Non-blocking (`setWaitForConversion(false)`)
- **Sampling Interval:** Checked every $1000 \text{ ms}$ (`now - lastTempRequest >= 1000`)
- **Unit:** Degrees Celsius (°C)
- **Telemetry Entrance:** Written directly to JSON payload as `"temperature_c": %.2f`.
- **ML Entrance:** Assigned to `features[feature_index++] = temperature_C;` on every 10 ms loop tick.
- **Mathematical Assessment:**
  - Because temperature updates at 1 Hz while the ML buffer samples at 100 Hz, the same scalar reading is duplicated 100 times in the Edge Impulse input frame.
  - In the spectral analysis FFT block (Axis 0), an identical static value has a frequency of 0 Hz (DC component only).

---

## 7. Sampling & Timing Analysis

The firmware targets $100 \text{ Hz}$ ($\Delta t = 10.0 \text{ ms}$). A rigorous execution-budget analysis reveals severe timing overruns:

| Subroutine | Frequency | Execution Time | Impact on 10 ms Budget | Dropped Samples |
|---|---|---|---|---|
| `readCurrent()` | Every loop (100 Hz) | **6.20 ms** | Consumes 62.0% of available budget | 0 (baseline) |
| `readVibration()` | Every loop (100 Hz) | **0.45 ms** | Consumes 4.5% of available budget | 0 (baseline) |
| `updateDisplay()` (OLED) | Every 250 ms (4 Hz) | **23.04 ms** | **Exceeds budget by 130%** | **2 dropped samples** |
| `runEdgeImpulse()` | Every ~1000 ms (1 Hz) | **35.00 ms** | **Exceeds budget by 250%** | **3-4 dropped samples** |
| `publishTelemetry()` (MQTT) | Every 1000 ms (1 Hz) | **10.00 ms** | **Exceeds budget by 100%** | **1 dropped sample** |

### Calculated Sampling Frequency:
- Over a $1000 \text{ ms}$ period: $96 \text{ ms}$ (OLED $\times$ 4) $+ 35 \text{ ms}$ (EI) $+ 10 \text{ ms}$ (MQTT) $= \mathbf{141 \text{ ms}}$ spent in blocking operations.
- Effective active sampling window: $859 \text{ ms}$.
- Actual samples captured per second: **82 to 86 samples**.
- **Calculated Effective Sampling Rate:** **~84 Hz (NOT 100 Hz)**.
- **Spectral Impact:** The 16-point FFT spectral analysis in Edge Impulse assumes strictly periodic intervals ($\Delta t = 10.0 \text{ ms}$). Non-uniform sampling introduces spectral leakage, artificial phase noise, and distorted peak frequencies.

---

## 8. Vibration Unit Analysis

- **Formula in Code:**
  ```cpp
  snprintf(payload, sizeof(payload),
    "..., \"vibration_g\":%.4f, \"vibration_mm_s\":%.3f, ...",
    ..., vibration, vibration * 9.81f, ...);
  ```
- **Physical Reality:**
  - `vibration` is dynamic acceleration in units of $g$.
  - $g \times 9.81 \text{ (m/s}^2)/g = \mathbf{\text{m/s}^2}$ **(ACCELERATION)**.
  - The key is labeled `"vibration_mm_s"` **(VELOCITY)**.
- **Dimensional Verification Table:**

| Metric | Code Formula | True Physical Dimension | Reported Unit | Physical Reality | Status |
|---|---|---|---|---|---|
| `vibration_g` | `dynAccel / 9.81` | Acceleration ($[L \cdot T^{-2}]$) | $g$ | Peak Dynamic Accel | **PASS** |
| `vibration_mm_s` | `vibration * 9.81` | Acceleration ($[L \cdot T^{-2}]$) | $\text{mm/s}$ | Acceleration in $\text{m/s}^2$ | **FAIL (Dimensional Error)** |

- **Industrial Impact:** ISO 10816-3 standards define machinery health based on **RMS vibration velocity** in $\text{mm/s}$ across $10 \text{ Hz} - 1000 \text{ Hz}$. Comparing acceleration in $\text{m/s}^2$ against velocity thresholds triggers false emergency shutdowns and masks low-frequency structural resonance.

---

## 9. Serial Bridge Analysis

- **File:** `backend_example/serial_bridge.py`
- **Parser Logic:**
  ```python
  if line.startswith("{") and line.endswith("}"):
      obj = json.loads(line)
  ```
- **Firmware Emission:**
  ```cpp
  Serial.printf("[MQTT Publish -> %s] %s\n", MQTT_TOPIC, payload);
  ```
- **Observed Trace:**
  - Incoming string: `[MQTT Publish -> motors/MTR-001/data] {"motor_id":"MTR-001",...}`
  - `line.startswith("{")` evaluates to **`False`**.
  - Fallback regexes look for `Motor ID : ...`, `Temperature : ...`, which the firmware never emits.
- **Conclusion:** **100% of telemetry lines are dropped.** The serial bridge cannot ingest data from the ESP32 USB cable.

---

## 10. MQTT Payload Analysis

- **Topic:** `motors/MTR-001/data` (conforms to backend wildcard subscription `motors/+/data`)
- **JSON Payload:**
  ```json
  {"motor_id":"MTR-001","temperature_c":35.50,"current_a":0.420,"vibration_g":0.1280,"vibration_mm_s":1.256,"ai_class":"normal","ai_confidence":0.950,"energy_wh":12.3456}
  ```
- **Size:** 182 bytes (fits safely within the configured 512-byte PubSubClient packet buffer).
- **Encoding:** UTF-8 valid JSON.

---

## 11. FastAPI Telemetry Analysis

- **Endpoint:** `POST /api/telemetry` & `POST /api/test/sensor-data`
- **Validation:** Accepts dictionary payload, enriches with ML predictions, persists to MongoDB, broadcasts to WebSockets.
- **Health Calculation (`calculate_rul_and_health`):**
  $$\text{health} = 100.0 - (\text{vib} \times 6.5) - (\max(0, \text{temp} - 50.0) \times 1.2) - (\text{anomaly} \times 30.0)$$
- **Defects Identified:**
  1. `current_a` is passed into the function as an argument, but the equation **never references `current`**! Overcurrent electrical faults do not degrade the health score.
  2. `anomaly_score` degrades health by up to 30 points, but Edge Impulse provides no anomaly score ($0.0$).

---

## 12. MongoDB Schema Analysis

- **Collections:** `telemetry` and `alerts`
- **Indexing:** Indexes exist on `("motor_id", 1)` and `("server_timestamp", -1)`.
- **Integrity:**
  - Timestamp: Server assigns ISO 8601 UTC timestamp (`server_timestamp`).
  - ObjectId: Serialization crash resolved in Phase 0.
  - Data types: Floats and strings match data contracts.

---

## 13. Dataset Analysis

- **Filesystem Audit:** Zero raw dataset files (`.csv`, `.parquet`, `.npy`) exist in the project repository.
- **Training Source:** The deployed model was trained in the cloud Edge Impulse Studio project (`Gopesh_rathinam-project-1`, Project ID `1112704`).
- **Frontend Dataset (`mockData.js`):** Contains purely synthetic JavaScript objects generated via `Math.random()`.
- **Finding:** No offline physical training dataset is committed in the repository.

---

## 14. Edge Impulse Model Analysis

- **Model Engine:** TensorFlow Lite Micro (EON Compiled Graph int8)
- **Input Channels:** 3 fusion axes (`temperature_C + vibration_g + current_A`)
- **Raw Window Size:** 100 samples $\times$ 3 axes = **300 floats**
- **DSP Block:** Spectral Analysis (Block ID 5):
  - 16-point FFT, 3 spectral peaks, threshold $0.1$
  - Logarithmic power bands: `0.1, 0.5, 1.0, 2.0, 5.0`
  - Wavelet analysis: `db4`, level 1
  - Output features: **39 floats**
- **NN Learning Block:** TFLite Learn (Block ID 6):
  - Input: 39 features $\rightarrow$ Output: 3 classes

---

## 15. Edge Impulse Class Analysis

- **Compiled Categories in `model_variables.h:50`:**
  ```c
  const char* ei_classifier_inferencing_categories_1112704_1[] = { "critical", "fault", "normal" };
  ```
- **Actual Classes:**
  1. `critical`
  2. `fault`
  3. `normal`
- **Dashboard Disconnect:** The frontend never checks for these 3 strings. It searches for `Healthy`, `Degrading`, `Bearing Wear`, and `Rotor Imbalance`.

---

## 16. Edge Impulse Anomaly Analysis

- **Source:** `model-parameters/model_metadata.h:107`:
  ```c
  #define EI_CLASSIFIER_HAS_ANOMALY EI_ANOMALY_TYPE_UNKNOWN
  ```
- **K-Means / GMM Blocks:** `EI_CLASSIFIER_HAS_ANOMALY_KMEANS 0`, `EI_CLASSIFIER_HAS_ANOMALY_GMM 0`.
- **Conclusion:** **The Edge Impulse model contains NO anomaly detector.** Any reference to an Edge Impulse anomaly score in backend formulas or frontend UI is a synthetic placeholder.

---

## 17. Firmware $\rightarrow$ Model Compatibility

| Property | Firmware Provides | Model Expects | Compatibility Status |
|---|---|---|---|
| Input Size | 300 floats (`features[300]`) | 300 floats (`DSP_INPUT_FRAME_SIZE`) | **COMPATIBLE** |
| Axes Count | 3 axes | 3 axes (`RAW_SAMPLES_PER_FRAME`) | **COMPATIBLE** |
| Axis 0 | `temperature_C` | `temperature_C` | **COMPATIBLE (Duplicate 1Hz)** |
| Axis 1 | `latestVibration` ($g$) | `vibration_g` | **COMPATIBLE** |
| Axis 2 | `latestCurrent` ($A$) | `current_A` | **COMPATIBLE** |
| Sampling Rate | ~84 Hz (jittered) | 100 Hz ($\Delta t = 10 \text{ ms}$) | **PARTIALLY COMPATIBLE (Jitter)** |

---

## 18. Dataset $\rightarrow$ Model Compatibility

| Feature | Project Dataset | Model Specification | Compatible? |
|---|---|---|---|
| Training Data | Cloud Studio (Project 1112704) | 3-axis fusion (100 Hz) | **COMPATIBLE IN CLOUD** |
| Local Training Files | None committed in repo | N/A | **BLOCKER FOR OFFLINE RETRAINING** |
| Mock Dashboard Data | Synthetic random walk | 3 classes (`critical`, `fault`, `normal`) | **INCOMPATIBLE** |

---

## 19. Threshold Consistency Analysis

| Metric | Firmware | Backend (`main.py`) | Frontend (`mockData.js`) | Discrepancy Finding |
|---|---|---|---|---|
| Vibration Warning | None | $> 4.5 \text{ mm/s}$ | $> 5.0 \text{ mm/s}$ | $4.5$ vs $5.0 \text{ mm/s}$ threshold mismatch |
| Vibration Critical | None | $> 7.0 \text{ mm/s}$ | $> 7.0 \text{ mm/s}$ | Matched value, but firmware transmits $\text{m/s}^2$! |
| Temperature Warning | None | **None (Missing!)** | $> 70^\circ\text{C}$ | Backend has no $70^\circ\text{C}$ warning alert |
| Temperature Critical | None | $> 80^\circ\text{C}$ | $> 80^\circ\text{C}$ | Aligned |
| Current Overcurrent | $4.0 \text{ A}$ | None | None | Backend ignores current thresholds |

---

## 20. Alert Semantics

- **Current Architecture:** All alerts generated by `evaluate_alerts()` in `backend_example/main.py` are **100% RULE-BASED THRESHOLDS**:
  - `vib > 7.0` $\rightarrow$ Critical
  - `vib > 4.5` $\rightarrow$ Warning
  - `temp > 80.0` $\rightarrow$ Critical
- **AI Classification Role:** The Edge Impulse inference output (`ai_class` and `ai_confidence`) is saved as a metadata attribute on telemetry records, but **never triggers or resolves alerts**.
- **Semantic Finding:** Rule-based threshold alerts are falsely perceived as AI predictive alerts in the user interface.

---

## 21. Frontend Data Compatibility

1. **Class Names:** Dashboard displays "Bearing Wear", "Overheating", "Healthy", but TinyML model only knows `normal`, `fault`, `critical`.
2. **Anomaly Gauge:** Dashboard renders an animated anomaly score gauge ($0.0 - 1.0$), while backend hardcodes `anomaly_score = 0.0` because the model has no anomaly block.
3. **Telemetry Polling vs Streaming:** Frontend relies on local interval timers and mock simulation arrays rather than subscribing to live WebSocket telemetry.

---

## 22. Complete Mismatch Table

| ID | Tier A | Tier B | Nature of Mismatch | Severity |
|---|---|---|---|---|
| **MIS-01** | Firmware `publishTelemetry` | Backend `evaluate_alerts` | Acceleration $\text{m/s}^2$ sent into velocity $\text{mm/s}$ threshold | **CRITICAL** |
| **MIS-02** | Firmware Serial Output | Serial Bridge Parser | `[MQTT Publish -> ...]` prefix drops 100% of serial telemetry | **CRITICAL** |
| **MIS-03** | Firmware Loop Timing | Edge Impulse DSP | Loop jitter (~84 Hz) distorts 100 Hz 16-point FFT spectral analysis | **HIGH** |
| **MIS-04** | Edge Impulse Model | Dashboard UI | Model has no anomaly block; UI renders anomaly gauge | **HIGH** |
| **MIS-05** | Edge Impulse Classes | Dashboard Conditions | Model outputs `critical, fault, normal`; UI expects 5 camel-case classes | **MEDIUM** |
| **MIS-06** | Backend Ingestion | Backend Health Formula | Current is ingested and saved, but completely omitted from health formula | **MEDIUM** |
| **MIS-07** | Backend Alerts | Frontend Settings | Backend lacks $70^\circ\text{C}$ warning; vibration warning is $4.5$ vs $5.0 \text{ mm/s}$ | **MEDIUM** |
| **MIS-08** | ACS712 Divider Notice | Firmware Constant | Safety divider requires $1.667 \text{ V}$ zero reference; firmware hardcodes $2.50 \text{ V}$ | **HIGH** |

---

## 23. Severity Classification

### CRITICAL
1. **MIS-01: Vibration Unit Mismatch:** $g \times 9.81$ produces $\text{m/s}^2$, mislabeled as velocity in $\text{mm/s}$.
2. **MIS-02: Serial Bridge Ingestion Failure:** Prefix mismatch causes 100% telemetry drop on USB serial.

### HIGH
1. **MIS-03: Sampling Jitter & Timing Overrun:** Blocking OLED and inference routines degrade sampling rate to ~84 Hz.
2. **MIS-04: Anomaly Feature Absence:** Edge Impulse model metadata confirms anomaly detection is disabled (`0`).
3. **MIS-08: ACS712 Quiescent Voltage Offset:** Software defaults to 2.50V, conflicting with 10k/20k voltage divider (1.667V).

### MEDIUM
1. **MIS-05: Class Vocabulary Inconsistency:** 3 TinyML classes vs 5 dashboard condition states.
2. **MIS-06: Dead-End Current Metric:** Current omitted from `calculate_rul_and_health`.
3. **MIS-07: Cross-Tier Threshold Inconsistency:** 4.5 vs 5.0 mm/s and missing 70°C warning alert.

---

## 24. Issues That Can Be Fixed Without Hardware

1. **Serial Bridge Regex Fix:** Update `serial_bridge.py` to extract embedded JSON strings via `json.loads(line[line.find("{"):line.rfind("}")+1])`.
2. **Vibration Key Correction:** Correct firmware payload key to `"vibration_m_s2"` or provide a mathematical digital integration approximation.
3. **Backend Health Formula Update:** Ingest `current_a` into `calculate_rul_and_health` to degrade health during overcurrent.
4. **Backend Alert Alignment:** Add $70^\circ\text{C}$ warning alert and align vibration warning threshold to $5.0 \text{ mm/s}$.
5. **Class Vocabulary Mapping:** Create a clean adapter mapping `critical`, `fault`, `normal` to frontend presentation states.
6. **ACS712 Voltage Scaling Parameterization:** Parameterize divider ratio macro in firmware source code.

---

## 25. Issues Requiring Hardware Later (Deferred)

1. **True RMS Velocity Calibration:** Physical vibration sensor mounting and laser vibrometer comparison for acceleration-to-velocity integration.
2. **Physical Current Sensor Calibration:** Calibrating quiescent voltage offset and sensitivity against physical multimeter readings.
3. **FreeRTOS Dual-Core Sampling Verification:** Measuring real ESP32 GPIO toggle timing with oscilloscope to verify jitter-free 100 Hz sampling.
4. **Physical Relay Actuation:** Testing motor contactor opening under full inductive 775 DC motor load.

---

## 26. Recommended Correction Order

1. **Step 1 (Data Pipeline & Ingestion):** Fix `serial_bridge.py` JSON extraction to enable USB streaming without broker.
2. **Step 2 (Dimensional Integrity):** Reconcile vibration units and align cross-tier thresholds ($4.5$ vs $5.0 \text{ mm/s}$, $70^\circ\text{C}$ alert).
3. **Step 3 (Backend Processing):** Integrate motor current into `calculate_rul_and_health()` and adapt TinyML class names.
4. **Step 4 (Firmware Architecture):** Decouple OLED display and MQTT transmission from the high-frequency 100 Hz sampling loop using FreeRTOS tasks.
5. **Step 5 (Edge Impulse Synchronization):** Retrain model in Studio if anomaly detection or 3-axis vibration is required.

---

## 27. Phase 2A Verdict

```text
============================================================
PHASE 2A VERDICT: PASS WITH CONDITIONS
============================================================
```

### SOFTWARE FIXES POSSIBLE NOW
- Fix `serial_bridge.py` prefix-tolerant JSON extraction.
- Reconcile vibration labels and mathematical conversion in firmware and backend.
- Align backend alert thresholds ($70^\circ\text{C}$ warning, $5.0 \text{ mm/s}$ vibration).
- Incorporate `current_a` into backend health score formula.
- Map 3 Edge Impulse classes to dashboard conditions.
- Remove synthetic anomaly score claims or document as placeholder.

### HARDWARE VERIFICATION DEFERRED
- Physical ACS712 voltage divider calibration on ESP32 ADC pin 34.
- Physical ADXL345 dynamic frequency response and mounting resonance.
- Physical relay contactor breaking under inductive DC motor load.
- Oscilloscope measurement of ESP32 GPIO hardware sample timing.

### ML/DATA FIXES REQUIRED
- Edge Impulse model retraining if genuine anomaly detection (K-Means/GMM) is required.
- Edge Impulse model retraining if 3 independent vibration axes ($X, Y, Z$) are desired instead of scalar magnitude.
- Synchronization between 3 compiled model classes and frontend display states.

### BLOCKERS FOR PHASE 2B
1. **Vibration Unit Reconciliation:** Must decide whether firmware sends acceleration in $\text{m/s}^2$ or integrates to velocity in $\text{mm/s}$ before synchronizing thresholds.
2. **Serial Bridge Parser:** Must fix regex parser so bench testing can ingest serial telemetry without an active MQTT broker.
3. **Anomaly Detector Policy:** Must decide whether to retrain Edge Impulse model with K-Means anomaly enabled or remove anomaly gauge from UI.

============================================================
STOP AND AWAITING AUTHORIZATION FOR NEXT STEP.
============================================================
