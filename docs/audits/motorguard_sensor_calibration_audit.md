# MotorGuard — Industrial-Inspired Sensor Calibration & Threshold Audit

**Document ID:** `AUDIT-CALIB-2026-10-19-01`  
**Target System:** MotorGuard (ESP32 Node `esp32-node-001`, Motor Asset `MTR-775-001`)  
**Hardware Profile:** 775 Brushed Permanent-Magnet DC Motor (12 V DC)  
**Primary Sensors:** ACS712-20A (Current), ADXL345 (Vibration), DHT11 (Ambient Air Temp/Humidity)  
**Reference Benchmark:** Leap Sensors Phase IV Motor Monitor Transceiver Node  
**Git Branch:** `security/hardening-and-rbac`  
**Verification Baseline:** Backend Pytest Suite (137 tests passing), Frontend Vite Production Build (0 errors)

---

## 1. Reference Datasheet: What May and May Not Be Inferred

The Leap Sensors Phase IV Motor Monitor Transceiver Node represents an industrial wireless condition-monitoring solution. While it provides an architectural reference for edge processing, configurable alert thresholds, and multi-sensor diagnostics, its published specifications are manufacturer-stated ratings for its specific hardware platform and cannot be directly transferred or assumed for MotorGuard.

### Comparative Engineering Matrix

| Dimension | Leap Sensors Phase IV Reference Node | MotorGuard System Implementation | Engineering & Calibration Implications |
| :--- | :--- | :--- | :--- |
| **Current Sensor** | Split-core AC current transformer clamp (0–10 V output standard, 1% FSR accuracy stated) | Inline Hall-effect Allegro ACS712ELCTR-20A-T ($\pm 20\,\text{A}$ bidirectional, nominal $100\,\text{mV/A}$) | **Inapplicable:** AC clamp monitors 50/60 Hz AC induction motors. MotorGuard monitors DC armature current. AC RMS scaling does not apply to DC offset and unidirectional current. |
| **ADC Resolution & Input Range** | 24-bit dedicated instrumentation ADC with dual 0–10 V differential inputs | ESP32 integrated 12-bit Successive Approximation Register (SAR) ADC ($0 - 3.3\,\text{V}$, 11 dB attenuation) | **Dynamic Range & Linearity Gap:** ESP32 SAR ADC has $\sim 10.5$ ENOB, non-linearities at $< 0.15\,\text{V}$ and $> 3.15\,\text{V}$, and $V_{ref}$ drift. Requires calibration curve; cannot match 24-bit precision. |
| **Voltage Attenuation** | Direct 0–10 V industrial instrumentation input stage | External passive 2-resistor voltage divider ($R_1 = 10\,\text{k}\Omega, R_2 = 20\,\text{k}\Omega$, nominal ratio $k_{div} \approx 0.6667$) | Resistor tolerance ($1\%$ or $5\%$) directly scales sensitivity. Must be calibrated empirically. |
| **Vibration Bandwidth & Dynamic Range** | Triaxial MEMS module, DC to 5,000 Hz stated bandwidth, $\pm 8\,\text{g}$ RMS range | Analog Devices ADXL345 triaxial MEMS accelerometer on I2C bus | **Bandwidth Limit:** ADXL345 maximum selectable ODR is $3200\,\text{Hz}$ (Nyquist $1600\,\text{Hz}$); configured firmware loop sustains $800\,\text{Hz}$ (Nyquist $400\,\text{Hz}$). High-frequency gear/bearing harmonics above $400\,\text{Hz}$ cannot be captured. |
| **Temperature Sensing** | Type-K thermocouple standard with dedicated cold-junction compensation ($\pm 0.5^\circ\text{C}$ stated accuracy) | DHT11 capacitive humidity and resistive temperature sensor mounted in air | **Measurement Target Mismatch:** Thermocouple measures contact casing/winding temperature. DHT11 measures ambient air inside enclosure. DHT11 has $\pm 2^\circ\text{C}$ accuracy, $1.5\,\text{s}$ latency, and cannot track rapid thermal stall runaway. |
| **Offline Storage** | Up to 110,000 timestamped readings in non-volatile flash | 32-message ring buffer in ESP32 volatile SRAM (`OFFLINE_QUEUE_CAPACITY 32`) | MotorGuard buffers transient Wi-Fi drops (tens of seconds). Long-term offline logging requires persistent flash or SD card. |
| **Wireless Architecture** | Wireless Thread / IPv6 mesh protocol | 802.11 b/g/n Wi-Fi station connecting to Mosquitto MQTT broker | Wi-Fi consumes significantly higher peak current ($150 - 240\,\text{mA}$) during transmission bursts, causing ADC ground bounce if layout is unshielded. |

### Summary of What May NOT Be Inferred
1. Do not assume the AC clamp accuracy (1% FSR) applies to the ACS712 DC current sensor.
2. Do not assume the 5,000 Hz vibration bandwidth applies to the ADXL345 I2C implementation.
3. Do not assume the thermocouple accuracy ($\pm 0.5^\circ\text{C}$) applies to the DHT11 ambient sensor.
4. Do not assume 110,000 offline storage capacity on the ESP32.
5. Do not use Leap Sensors industrial thresholds as production limits for an uncharacterized 775 DC motor.

---

## 2. Repository Files Inspected

The following files were inspected to establish actual code behavior and formulas:

| Component | File Path | Lines Inspected | Observed Focus |
| :--- | :--- | :--- | :--- |
| **Firmware** | [firmware/MotorGuard_ESP32_Inference.ino](file:///c:/Users/gopes/Downloads/MotorGuard/firmware/MotorGuard_ESP32_Inference.ino) | 40–165, 305–485, 830–980 | Pin mappings, ADC zero-offset calibration, vibration feature extraction, telemetry payload construction |
| **Firmware Duplicate** | [firmware/MotorGuard_ESP32_Inference/MotorGuard_ESP32_Inference.ino](file:///c:/Users/gopes/Downloads/MotorGuard/firmware/MotorGuard_ESP32_Inference/MotorGuard_ESP32_Inference.ino) | Entire file | Parity check with root firmware |
| **Backend Schemas** | [backend/app/schemas/telemetry.py](file:///c:/Users/gopes/Downloads/MotorGuard/backend/app/schemas/telemetry.py) | 1–150 | TelemetryIn, SensorsPayload, SensorStatusPayload, SafetyPayload |
| **Backend Schemas** | [backend/app/schemas/motor.py](file:///c:/Users/gopes/Downloads/MotorGuard/backend/app/schemas/motor.py) | 30–175 | SensorDHT11Config, SensorADXL345Config, SensorACS712Config, HealthThresholds, CalibrationStatus |
| **Backend Schemas** | [backend/app/schemas/alert.py](file:///c:/Users/gopes/Downloads/MotorGuard/backend/app/schemas/alert.py) | 1–65 | AlertTriggerType enum, severity definitions |
| **Alert Engine** | [backend/app/services/alert_service.py](file:///c:/Users/gopes/Downloads/MotorGuard/backend/app/services/alert_service.py) | 90–380 | Sensor diagnostic alerts, hard-limit fast-trip, hysteresis, ML non-suppression |
| **Calibration Script** | [scripts/calibration_logger.py](file:///c:/Users/gopes/Downloads/MotorGuard/scripts/calibration_logger.py) | 1–250 | MQTT/REST ingestion, CSV schema, reference data collection |
| **Frontend Types** | [frontend/src/types.ts](file:///c:/Users/gopes/Downloads/MotorGuard/frontend/src/types.ts) | 50–125 | TypeScript interfaces for thresholds, telemetry, and diagnostics |
| **Frontend UI** | [frontend/src/components/MotorDetailModal.tsx](file:///c:/Users/gopes/Downloads/MotorGuard/frontend/src/components/MotorDetailModal.tsx) | 410–520 | Live sensor display, calibration status badge, dynamic threshold bounds |

---

## 3. Existing Measurement Formulas & Actual Sensor Configurations

### A. Current Measurement Chain

- **Sensor Model:** Allegro ACS712ELCTR-20A-T.
- **Sensor Supply:** $V_{CC} = 5.0\,\text{V}$.
- **Zero-Current Output at Sensor:** $V_{out}(0\,\text{A}) = V_{CC} / 2 = 2.50\,\text{V}$.
- **Sensitivity:** $S_{sensor} = 100\,\text{mV/A} = 0.100\,\text{V/A}$.
- **Voltage Divider:** $R_1 = 10\,\text{k}\Omega$ (series), $R_2 = 20\,\text{k}\Omega$ (pulldown to GND).
  $$k_{div} = \frac{R_2}{R_1 + R_2} = \frac{20\,\text{k}\Omega}{10\,\text{k}\Omega + 20\,\text{k}\Omega} = \frac{2}{3} \approx 0.6667$$
- **Effective Sensitivity at ADC Pin:**
  $$S_{pin} = S_{sensor} \times k_{div} = 0.100\,\frac{\text{V}}{\text{A}} \times \frac{2}{3} = 0.06667\,\frac{\text{V}}{\text{A}} = 66.67\,\frac{\text{mV}}{\text{A}}$$
- **Conversion Math:**
  $$V_{pin} = \frac{\text{analogReadMilliVolts(34)}}{1000.0}$$
  $$V_{acs} = \frac{V_{pin}}{k_{div}}$$
  $$I = \frac{|V_{acs} - V_{zero\_sensor}|}{S_{sensor}} \equiv \frac{|V_{pin} - V_{zero\_pin}|}{S_{pin}}$$
- **Zero Calibration Bounds in Code:**
  - Valid resting pin voltage: $1.30\,\text{V} \le V_{pin} \le 2.05\,\text{V}$ (equivalent to $1.95\,\text{V} \le V_{acs} \le 3.07\,\text{V}$).
  - Maximum sample spread: $\Delta V_{pin} = V_{pin\_max} - V_{pin\_min} < 0.20\,\text{V}$.
  - Fallback on violation: $V_{zero} = 2.50\,\text{V}$, `currentCalibrated = false`.
- **Sampling Behavior:** 120 samples damped over $\approx 30\,\text{ms}$, instantaneous peak tracked in `currentPeakAmps`. Noise floor deadband: $0.05\,\text{A}$. Wire-break / short detection: $V_{pin} < 0.15\,\text{V}$ or $V_{pin} > 3.15\,\text{V} \implies \text{NAN}$.

### B. Vibration Measurement Chain

- **Sensor Model:** Analog Devices ADXL345.
- **Configured Range:** $\pm 16\,\text{g}$ full scale (`ADXL345_RANGE_16_G`).
- **Configured Output Data Rate (ODR):** $800\,\text{Hz}$ (`ADXL345_DATARATE_800_HZ`).
- **Acquisition Mechanism:** 128 sequential samples paced via `micros()` delay at $1250\,\mu\text{s}$ interval ($160\,\text{ms}$ window).
- **Unit Conversion:** $a_g = a_{\text{m/s}^2} / 9.80665$.
- **Dynamic Feature Extraction:**
  - Per-axis mean calculated: $\bar{x}, \bar{y}, \bar{z}$.
  - Dynamic components extracted: $x_{dyn} = x - \bar{x}, y_{dyn} = y - \bar{y}, z_{dyn} = z - \bar{z}$.
  - Authoritative 3-Axis Dynamic RMS:
    $$\text{dynamic\_rms\_g} = \sqrt{\frac{1}{N} \sum_{i=1}^N (x_{dyn,i}^2 + y_{dyn,i}^2 + z_{dyn,i}^2)}$$
  - Peak dynamic vector magnitude: $\text{peak\_g} = \max_i \sqrt{x_{dyn,i}^2 + y_{dyn,i}^2 + z_{dyn,i}^2}$.
  - Crest factor: $\text{crest\_factor} = \text{peak\_g} / \text{dynamic\_rms\_g}$.

### C. Temperature Measurement Chain

- **Sensor Model:** DHT11.
- **Sampling Interval:** Enforced minimum $1.5\,\text{seconds}$ between reads.
- **Valid Range:** $-20^\circ\text{C}$ to $120^\circ\text{C}$ (values outside or NaN flagged as `dhtOnline = false`, telemetry reports `ambient_temperature_c = NAN`).
- **Semantic Distinction:** Labeled strictly as `ambient_temperature_c`. `case_temperature_c` is maintained as `null` / unconfigured.

---

## 4. Current Threshold Definitions & Historical Unverified Values

Every threshold in the codebase has been identified, traced to its origin, and categorized:

| Threshold Parameter | Code Value | Categorization | Historical Provenance & Audit Analysis |
| :--- | :---: | :--- | :--- |
| **Current Warning** | `2.60 A` | **Provisional** | Derived from early design notes assuming $\sim 70\%$ of an assumed 3.8A continuous rating. **Not verified on a dynamometer.** |
| **Current Critical** | `3.20 A` | **Provisional** | Assumed thermal continuous limit for RS-775WC. Validated only as a software boundary, not verified against specific motor winding insulation. |
| **Current Hard Ceiling** | `4.25 A` | **Provisional** | Fast-trip limit set below typical 5A bench supply trip point. Prevents power supply brownout during testing. |
| **Assumed Rated Current** | `3.0 A` | **Provisional** | Found in default `HealthThresholds`. Generic 775 motors vary between 1.5A and 6.0A depending on winding gauge (turns per slot). |
| **Assumed Driver Limit** | `10.0 A` | **Provisional** | Based on typical dual H-bridge (L298N or BTS7960) peak specs, unconfirmed by schematic. |
| **Assumed Supply Limit** | `5.0 A` | **Provisional** | Standard laboratory bench supply current-limit setting. |
| **Vibration Warning** | `0.15 g` | **Provisional** | Aligned with ISO 10816 Class I small machine baseline ($1.8\,\text{mm/s}$ at $3000\,\text{RPM}$). |
| **Vibration Critical** | `0.35 g` | **Provisional** | ISO 10816 Class I boundary for unacceptable vibration. Dependent on mount rigidity. |
| **Historical Vibration Proposal (1.45 g)** | `1.45 g` | **Unvalidated Proposal** | Present in legacy synthetic datasets as peak vibration during loose-mounting simulation. Unsuitable as continuous RMS threshold. |
| **Case Temperature Warning (65°C)** | `65.0 °C` | **Unconfigured** | Class B winding allows $130^\circ\text{C}$; casing is typically $30 - 40^\circ\text{C}$ lower. Requires contact probe. |
| **Case Temperature Critical (75°C)** | `75.0 °C` | **Unconfigured** | Requires contact probe. Currently marked `null` in active telemetry. |
| **DHT11 Air Temp Warning (42°C)** | `42.0 °C` | **Provisional** | Internal electronics enclosure temperature threshold. |
| **DHT11 Air Temp Critical (46°C)** | `46.0 °C` | **Provisional** | Proximity to DHT11 maximum manufacturer operating limit ($50^\circ\text{C}$). |
| **Historical Zero Offset (3.820 V)** | `3.820 V` | **Rejected / Invalid** | Physically impossible on 3.3V ESP32 ADC pin. Rejected; nominal zero is $1.667\,\text{V}$ ($2.50\,\text{V}$ sensor). |

---

## 5. Suspected and Confirmed Defects

### Confirmed Defects (Addressed & Guarded)
1. **[CONFIRMED - P0] ML Healthy Prediction Suppressing Safety Alerts:** Previously, if the ML model output `predictedClass = "normal"`, it could mask or auto-resolve rule-based alerts. The synthetic dataset includes rows with $I = 5.95\,\text{A}$ labeled as `"normal"`. **Resolution:** Fully decoupled in firmware `evaluateSafetyRules()` and backend `alert_service.py`. A healthy ML prediction can never resolve or clear safety alerts.
2. **[CONFIRMED - P0] Unbounded Zero Calibration at Boot:** If the ESP32 rebooted while the motor was spinning, the running current was calibrated as zero offset. **Resolution:** Bounded to pin voltage $[1.30\,\text{V}, 2.05\,\text{V}]$ and sample spread $< 0.20\,\text{V}$. If violated, flagged `UNCALIBRATED`.
3. **[CONFIRMED - P1] Current Noise Deadband Suppressing Low No-Load Running:** Deadband was previously $0.20\,\text{A}$, which forced healthy no-load draw ($0.35 - 0.50\,\text{A}$) to appear close to zero. **Resolution:** Lowered deadband to $0.05\,\text{A}$ (measured ADC noise floor).
4. **[CONFIRMED - P1] Static Tilt Conflated with Dynamic Vibration:** Previous formula subtracted scalar $1.0\,\text{g}$ from total vector magnitude instead of subtracting per-axis mean. **Resolution:** Implemented true per-axis mean subtraction and dynamic vector RMS.
5. **[CONFIRMED - P1] Conflation of Air Temperature with Winding Temperature:** DHT11 was evaluated against motor casing thermal limits. **Resolution:** Labeled strictly as `ambient_temperature_c`; `case_temperature_c` marked `null` / unconfigured.

### Suspected Defects / Hardware Facts Requiring Physical Verification
1. **[HW-01] Resistor Tolerances in Voltage Divider:** Nominal $10\,\text{k}\Omega$ and $20\,\text{k}\Omega$ resistors with $5\%$ tolerance can cause effective sensitivity to vary between $63.3\,\text{mV/A}$ and $70.2\,\text{mV/A}$. Physical measurement required.
2. **[HW-02] ESP32 Internal Reference Voltage Drift:** ESP32 eFuse $V_{ref}$ calibration varies by up to $\pm 6\%$ without per-unit calibration.
3. **[HW-03] ADXL345 Mounting Mechanical Resonance:** If mounted with foam tape or flexible brackets, vibration is heavily damped above $100\,\text{Hz}$. A rigid metallic mount is required.
4. **[HW-04] True 775 Motor Model Specification:** The "775" designation only describes the frame diameter ($42\,\text{mm}$) and length ($66\,\text{mm}$). Armature resistance ranges from $0.4\,\Omega$ to $3.5\,\Omega$ depending on winding turns.

---

## 6. Baseline Test Results

All existing unit, integration, and security tests were executed prior to additional calibration tooling:
- **Pytest Suite:** `pytest tests` $\to$ **137 passed in 28.57s** (100% pass rate).
- **Frontend Build:** `npm run build` $\to$ **Built in 1.68s with 0 errors**.
- **Docker Environment:** Docker CLI not present in host environment; container execution recorded as **NOT RUN (Environment Limited)**.
