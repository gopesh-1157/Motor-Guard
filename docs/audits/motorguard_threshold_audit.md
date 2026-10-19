# MotorGuard — Comprehensive Threshold, Calibration & Architecture Audit

**Document:** `docs/audits/motorguard_threshold_audit.md`  
**Audit Date:** October 19, 2026  
**Auditor Roles:** Senior Embedded Systems Engineer, ESP32 Firmware Specialist, IoT Architect, ML Engineer, Backend Developer, QA/Security Auditor  
**Runtime Mode:** GRAVITAS Engineering Reliability Runtime (Evidence-Backed, Grounded)  
**Target Hardware:** 775-class 12 V brushed permanent-magnet DC motor (Johnson Electric / Mabuchi RS-775), ESP32-WROOM-32, ACS712-20A Hall-effect current sensor with voltage divider on GPIO 34, ADXL345 3-axis digital accelerometer on I2C Bus 0 (GPIO 21/22), DHT11 ambient air temperature/humidity sensor on GPIO 4, SH1106 OLED on I2C Bus 1 (GPIO 32/33).

---

## 1. Executive Summary & Grounding Baseline

This audit inspects the current repository state across firmware, edge machine learning, backend ingestion, MongoDB data models, alert rules, simulator, and frontend presentation.

### Verified Session Baseline (Observed Evidence)
* **Backend Test Suite (`pytest tests`):** **120 passed**, 0 failed, 1 warning (Starlette test client deprecation) in **27.34s**.
* **Frontend Production Build (`npm run build`):** **0 errors**, completed in **1.77s** (`tsc -b && vite build`).
* **Git Status:** 39 modified tracked files, 9 untracked files preserved; zero commits, zero pushes.

---

## 2. File Paths and Line References

| Architectural Layer | File Path | Key Line Ranges | Description |
| :--- | :--- | :--- | :--- |
| **ESP32 Firmware** | `firmware/MotorGuard_ESP32_Inference.ino` | 125–138, 289–350, 352–441, 486–618, 624–701, 944–983 | ACS712 reading, zero calibration, ADXL345 sampling, Edge Impulse inference, safety cutoffs |
| **Nested Firmware Copy** | `firmware/MotorGuard_ESP32_Inference/MotorGuard_ESP32_Inference.ino` | 108–117, 270–330, 480–600 | Duplicate, out-of-sync copy missing OLED and multi-network mode updates |
| **Edge Impulse Model** | `firmware/ei-motoguard-motor-health-arduino-1.0.1-impulse-#1.zip` | `model_variables.h`, `model_metadata.h` | 3-feature raw tabular impulse: `temperature_C`, `vibration_g`, `current_A` |
| **Backend Schemas** | `backend/app/schemas/telemetry.py` | 7–32, 34–38, 46–53, 61–85 | `SensorsPayload`, `InferencePayload`, `TelemetryMessage` |
| **Backend Motor Models** | `backend/app/schemas/motor.py` | 119–145, 183, 218–223 | `HealthThresholds`, `MotorOut` |
| **Gateway Settings** | `backend/app/schemas/settings.py` | 13–83, 85–100 | `OperationalLimitsBase`, physical monotonicity validators |
| **Alert Rules Engine** | `backend/app/services/alert_service.py` | 65–125, 142–260 | Priority threshold resolution, hysteresis normalization, auto-resolution |
| **Motor Registry Service**| `backend/app/services/motor_service.py` | 100–145, 148–205, 330–445 | `calculate_motor_health()`, dynamic status resolution, default seed profiles |
| **Simulator** | `simulator/simulator.py` | 107–127, 187–199 | Virtual motor profiles, HIL baseline coupling |
| **Frontend Diagnostics**| `frontend/src/components/MotorDetailModal.tsx` | 228–296, 380 | Modal inspection cards, threshold evaluation strings |
| **Frontend Settings** | `frontend/src/components/SettingsView.tsx` | 5–20, 200–260 | Persisted operational threshold UI |
| **Datasets** | `data/physics_informed_synthetic_dataset_775_motor_edge_impulse_4col.csv`, `data/775_motor_edge_impulse_ml_ready.csv` | Headers, 100k rows | Synthetic dataset provenance |

---

## 3. Confirmed Defects

### Defect 1 (Severity: P0 — Safety & Data Integrity)
**Coupling and Mutual Overwriting of ML Predictions and Safety Cutoffs**
* **Location:** `firmware/MotorGuard_ESP32_Inference.ino:584–591` and `604–617`
* **Finding:**
  1. When Edge Impulse runs (`USE_EDGE_IMPULSE_LIB 1`), the firmware executes the model, but immediately overwrites the output variable `healthStatus` if physical thresholds are breached:
     ```cpp
     if (curr >= OVERCURRENT_LIMIT_A || temp >= 75.0f || vib >= 0.80f) {
       healthStatus = "critical";
     }
     ```
     This destroys the ground-truth prediction of the neural network, making model accuracy impossible to evaluate on real hardware.
  2. In the `#else` fallback path (`USE_EDGE_IMPULSE_LIB 0`), the code fabricates fake neural network probabilities:
     ```cpp
     confCritical = 0.95f; confWarning = 0.04f; confHealthy = 0.01f; topConfidence = 0.95f;
     ```
     This violates the core principle of zero fabrication.
  3. The telemetry payload schema (`TelemetryMessage`) combines both concepts into a single `inference.health_status` field. It lacks independent representation for:
     * Sensor Diagnostics (connectivity, valid/invalid, calibrated/uncalibrated, fresh/stale)
     * Raw ML Model Output (predicted class, actual confidence score, model version)
     * Deterministic Safety State (rule-based overcurrent, overtemperature, vibration status, trip reasons)
     * Overall System Health State (transparent synthesis where safety always takes precedence)

### Defect 2 (Severity: P0 — Measurement Correctness & Safety)
**ACS712 Current Measurement Calibration Flaws & Deadband Rectification**
* **Location:** `firmware/MotorGuard_ESP32_Inference.ino:127–130, 289–333`
* **Finding:**
  1. **Unconditional Boot Calibration:** `calibrateACS712()` assumes the motor is 100% OFF during microcontroller startup. If the ESP32 encounters a brownout, watchdog reset, or reboot while the 775 motor is spinning under load (e.g. drawing 2.5 A), that active current becomes the new `zeroPointVolts` ($2.5\,\text{V} + 0.25\,\text{V} = 2.75\,\text{V}$). On subsequent samples, a real load of 2.5 A measures as 0 A, and a severe 4.5 A overload only measures as 2.0 A, completely blinding the safety trip!
  2. **Deadband Zeroing:** `CURRENT_DEADBAND_A = 0.20f` forces any reading under 0.20 A to `0.0f`. While intended to suppress ADC noise, an unloaded high-efficiency 775 motor often idles near 0.35–0.45 A. Combined with offset drift, legitimate low-current readings are falsely clamped to 0.00 A.
  3. **Rectification via `fabs()`:** Absolute value `fabs(current)` converts negative offset drift into phantom forward current without bidirectional diagnosis.
  4. **Unverified 3.820 V Offset:** A previously proposed zero offset of 3.820 V is physically impossible on a 3.3 V ESP32 ADC pin and would correspond to $+13.2\,\text{A}$ on a 5 V ACS712-20A ($2.5\,\text{V} + 1.32\,\text{V}$). This value was either fabricated or measured at an invalid node.

### Defect 3 (Severity: P0 — Physical Meaning Misrepresentation)
**DHT11 Air Temperature Misrepresented as Motor Casing/Winding Temperature**
* **Location:** `backend/app/schemas/telemetry.py:8–13`, `firmware/MotorGuard_ESP32_Inference.ino:335–349`
* **Finding:**
  1. The DHT11 is an ambient air humidity/temperature sensor with a plastic ventilated grill, designed for ambient room measurements (0–50°C, $\pm 2^\circ\text{C}$ accuracy, 1.5s time constant).
  2. In `backend/app/schemas/telemetry.py:12`, `temperature_c` is documented as `"Chassis temperature in Celsius"`.
  3. The DHT11 cannot measure motor armature, winding, or internal brush temperature. Describing air readings as motor chassis temperature gives false safety assurance.
  4. The system lacks a dedicated field for contact casing temperature (e.g. DS18B20 or thermocouple) and fails to mark casing temperature as **Unconfigured** when only a DHT11 is present.

### Defect 4 (Severity: P0 — Configuration Inconsistency)
**Conflicting and Proliferating Threshold Definitions Across Subsystems**
* **Location:** Multiple files across firmware, backend, database models, and frontend
* **Finding:** At least 6 contradictory sets of thresholds exist in the codebase:
  * `schemas/motor.py` (`HealthThresholds`): Temp warn = 45.0°C, crit = 50.0°C; Curr warn = 3.0A, crit = 4.0A; Vib warn = 0.5g, crit = 1.0g
  * `schemas/settings.py` (`OperationalLimitsBase`): Temp warn = 50.0°C, crit = 65.0°C; Curr warn = 3.5A, crit = 4.0A; Vib warn = 0.20g, crit = 0.80g
  * `config.py`: Default curr = 4.0A, temp = 50.0°C, vib RMS = 0.100g, peak vib = 0.350g
  * `firmware/MotorGuard_ESP32_Inference.ino`: Curr warn = 3.0A, crit = 4.0A; Temp warn = 50.0°C, crit = 75.0°C; Vib warn = 0.20g, crit = 0.80g
  * `seed_demo.py`: Rated curr = 2.5A, overcurrent = 4.0A, max temp = 50.0°C, max vib = 0.200g
  * `MotorDetailModal.tsx`: Hardcoded presentation strings: 50.0°C, 4.00A, 0.200g
  * None of these thresholds carry provenance, calibration status, or motor hardware profile tracking.

### Defect 5 (Severity: P0 — ML Data Validity)
**Synthetic Dataset Provenance with Impossible Physics Labeled as "Healthy"**
* **Location:** `data/physics_informed_synthetic_dataset_775_motor_edge_impulse_4col.csv`, `data/775_motor_edge_impulse_ml_ready.csv`
* **Finding:**
  1. The files are synthetically generated.
  2. In `physics_informed_synthetic_dataset_775_motor_edge_impulse_4col.csv`, rows 2 and 4 have `current_A = 5.95 A` and `current_A = 7.46 A` labeled as `"healthy"`! For an RS-775 rated at 2.5 A nominal load, continuous operation at 7.5 A represents severe stall or overload that will melt the windings.
  3. The Edge Impulse model in `ei-motoguard-motor-health-arduino-1.0.1-impulse-#1.zip` was trained on this synthetic distribution (`fusion_string = "temperature_C + vibration_g + current_A"`).
  4. Reported 98%+ validation accuracy in training reflects overfitting to synthetic noise distributions, not verified real-motor fault detection.

### Defect 6 (Severity: P1 — Signal Processing Rigor)
**ADXL345 Acceleration RMS Formula Deviation**
* **Location:** `firmware/MotorGuard_ESP32_Inference.ino:426–430`
* **Finding:**
  1. The standard dynamic vibration RMS formula with per-axis DC gravity removal is:
     $$\text{vibration\_rms\_g} = \sqrt{\frac{1}{N}\sum_{i=1}^N \left[(x_i - \bar{x})^2 + (y_i - \bar{y})^2 + (z_i - \bar{z})^2\right]}$$
  2. Line 430 calculates:
     `m.totalRMS = (dynMotionRMS > acRMS) ? dynMotionRMS : acRMS;`
     where `dynMotionRMS` is calculated relative to $|\vec{a}| - 1.0\,\text{g}$. This conflates low-frequency orientation shifts with rotational mechanical vibration.

---

## 4. Potential Defects Requiring Hardware Verification

| Ref | Item | Suspected Risk | Verification Required |
| :--- | :--- | :--- | :--- |
| **HW-01** | ACS712 Variant | Code assumes ACS712-20A (100 mV/A). If hardware uses ACS712-05B (185 mV/A) or ACS712-30A (66 mV/A), current is scaled wrong by 1.85× or 0.66×. | Inspect IC package marking (`05B`, `20A`, or `30A`). |
| **HW-02** | Voltage Divider Resistors | Code assumes $R_1 = 10\,\text{k}\Omega$, $R_2 = 20\,\text{k}\Omega$ ($V_{\text{out}}/V_{\text{in}} = 0.6667$). | Measure resistance across divider network with multimeter. |
| **HW-03** | ADC Non-Linearity on GPIO 34 | ESP32 ADC exhibits non-linearity below 150 mV and above 3100 mV even with `ADC_11db`. | Characterize with calibrated DC bench supply at 0.5V to 3.0V. |
| **HW-04** | 775 Motor Rated Current | RS-775 motors vary widely from 1.5 A (Johnson Electric) to 5.0 A (high-speed Mabuchi). Code assumes 2.5 A rated. | Verify motor manufacturer label and datasheet stall current. |
| **HW-05** | Motor Power Supply Limit | Bench supply capacity restricts maximum observable stall current. | Verify supply voltage and current limit. |

---

## 5. Conflicting Threshold Matrix

| Source / Location | Curr Warn | Curr Crit | Temp Warn | Temp Crit | Vib Warn | Vib Crit | Provenance |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`firmware/...ino`** | 3.0 A | 4.0 A | 50.0 °C | 75.0 °C | 0.20 g | 0.80 g | Hardcoded C++ constants |
| **`schemas/settings.py`** | 3.5 A | 4.0 A | 50.0 °C | 65.0 °C | 0.20 g | 0.80 g | Provisional gateway limits |
| **`schemas/motor.py`** | 3.0 A | 4.0 A | 45.0 °C | 50.0 °C | 0.50 g | 1.00 g | Default motor asset schema |
| **`config.py`** | 3.4 A (calc) | 4.0 A | 50.0 °C | 75.0 °C (calc)| 0.100 g | 0.400 g (calc)| App environment defaults |
| **`seed_demo.py`** | — | 4.0 A | 50.0 °C | — | 0.200 g | — | Demo database seed |
| **`MotorDetailModal.tsx`**| 4.00 A | — | 50.0 °C | — | 0.200 g | — | Hardcoded UI strings |

### Audit of Previously Proposed Values
* **2.60 A (Warning) / 3.20 A (Critical) / 4.25 A (Hard Ceiling):** These were proposed in preliminary documents but never calibrated against real RS-775 load curves. They are marked **Provisional / Unvalidated**.
* **DHT11 Air Limits 42°C / 46°C:** Proposed based on ambient operating environment, but conflated with motor limits.
* **Vibration 1.45 g:** Proposed in earlier notes without mounting vibration analysis.

---

## 6. Edge Impulse Model & Runtime Feature Mismatch

* **Model File:** `firmware/ei-motoguard-motor-health-arduino-1.0.1-impulse-#1.zip`
* **Input Dimension:** 3 scalar float values (`nn_input_frame_size = 3`)
* **Expected Feature Order (from `model_variables.h:134`):**
  1. Index 0: `temperature_C`
  2. Index 1: `vibration_g`
  3. Index 2: `current_A`
* **Labels:** 3 classes: `critical`, `healthy`, `warning`
* **Sampling Rate in Metadata:** `interval_ms = 1` (tabular, not time-series spectral FFT).
* **Firmware Runtime Vector:**
  * Firmware lines 515–517 feed `ei_features[0] = temp; ei_features[1] = vib; ei_features[2] = curr;`.
  * The order matches the model metadata.
  * **Gap:** The model was trained on synthetic data where 7.5A was labeled "healthy". Feeding real sensor data into this model produces unpredictable classifications until retrained on ground-truth bench data.

---

## 7. Recommended Corrections Ordered by Severity

1. **P0 — Structural Separation of ML Inference from Rule-Based Safety:**
   * Extend `TelemetryMessage` to decouple `inference` (ML predictions, confidence, model version) from `safety` (rule-based evaluation, trip reasons, configuration version) and `sensors` (diagnostics, air temp, case temp, calibration status).
   * Update firmware to report raw model outputs without overwriting them with safety cutoffs.
   * Ensure safety alert engine treats rule-based trips as inviolable, regardless of ML predictions.
2. **P0 — ACS712 Measurement & Calibration Overhaul:**
   * Bound boot calibration: reject zero-offset calibration if $V_{\text{offset}}$ deviates by $> 150\,\text{mV}$ from expected $V_{cc}/2 \times \text{divider}$ ($1.667\,\text{V} \pm 0.15\,\text{V}$).
   * Eliminate arbitrary zero deadband (`0.20 A`).
   * Preserve signed bidirectional current; report magnitude and direction.
   * Provide explicit calibration status (`uncalibrated`, `calibrated`, `error`).
3. **P0 — Authoritative Motor Threshold Provenance Model:**
   * Enhance motor threshold schema with provenance tracking (`manufacturer_verified`, `measured_and_calibrated`, `provisional`, `unconfigured`).
   * Enforce validation: reject `warning >= critical`.
   * Display calibration badges in UI (e.g. "Provisional", "Calibrated").
4. **P1 — Standardized Dynamic Vibration RMS Formula:**
   * Enforce $\text{vibration\_rms\_g} = \sqrt{\text{mean}(x_{\text{dyn}}^2 + y_{\text{dyn}}^2 + z_{\text{dyn}}^2)}$ across 128 samples with mean subtraction per axis.
5. **P1 — Temperature Classification & Sensor Diagnostics:**
   * Explicitly label DHT11 reading as `ambient_temperature_c`.
   * Provide `case_temperature_c` as Optional/Unconfigured unless a contact probe is physically verified.
6. **P1 — Regression Test Suite Expansion:**
   * Add test coverage for all 17 mandatory verification scenarios in `tests/integration/test_operational_limits.py`.
