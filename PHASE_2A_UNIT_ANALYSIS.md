# MotorGuard — Phase 2A Physical & Mathematical Unit Analysis

**Audit Type:** Mathematical & Dimensional Verification (Hardware-Independent)  
**Target Architecture:** ADXL345 $\rightarrow$ ACS712 $\rightarrow$ DS18B20 $\rightarrow$ ESP32 $\rightarrow$ Backend $\rightarrow$ Dashboard  
**Date:** 2026-10-03  

---

## 1. Executive Summary of Unit Inconsistencies

During the Phase 2A audit, a critical physical dimensional error was identified in the firmware telemetry pipeline:
- **The firmware multiplies acceleration in $g$ by $9.81$, yielding acceleration in $\text{m/s}^2$, but writes it into a JSON key named `"vibration_mm_s"` (velocity).**
- The backend and frontend receive this value and treat it as **ISO 10816 vibration velocity in $\text{mm/s}$**, comparing it directly against $4.5 \text{ mm/s}$ and $7.0 \text{ mm/s}$ thresholds.
- Mathematically, acceleration cannot be converted to velocity simply by scalar multiplication without integrating over time or dividing by angular frequency ($2\pi f$).
- Furthermore, quiescent zero reference for the ACS712 current sensor hardcodes $2.50 \text{ V}$ in software, whereas the hardware safety notice mandates a $10\text{ k}\Omega / 20\text{ k}\Omega$ voltage divider that scales quiescent zero down to $1.667 \text{ V}$.

---

## 2. Vibration Unit Deep-Dive

### 2.1 Sensor Physical Output: ADXL345
- **Driver:** `Adafruit_ADXL345_Unified accel`
- **Output:** `sensors_event_t event.acceleration.x, y, z` in $\text{m/s}^2$.
- **Magnitude Formula:**
  $$\text{magnitude} = \sqrt{a_x^2 + a_y^2 + a_z^2} \quad [\text{m/s}^2]$$
- **Gravity Subtraction:**
  $$a_{\text{dyn}} = |\text{magnitude} - 9.81| \quad [\text{m/s}^2]$$
- **Normalization to $g$:**
  $$a_g = \frac{a_{\text{dyn}}}{9.81} \quad [g]$$

### 2.2 Telemetry Conversion Flaw
In `firmware/esp32_motor_node/esp32_motor_node.ino:296-297`:
```cpp
"\"vibration_g\":%.4f,"
"\"vibration_mm_s\":%.3f,"
...
vibration,
vibration * 9.81f,
```

#### Dimensional Analysis:
$$[\text{vibration}] = g$$
$$[\text{vibration} \times 9.81] = [g] \times \left[\frac{\text{m/s}^2}{g}\right] = \text{m/s}^2 \quad (\text{ACCELERATION})$$
$$[\text{vibration\_mm\_s}] = \text{mm/s} \quad (\text{VELOCITY})$$

$$\text{m/s}^2 \neq \text{mm/s} \quad ([L \cdot T^{-2}] \neq [L \cdot T^{-1}])$$

### 2.3 Mathematical Error Quantification
For a sinusoidal vibration component at frequency $f$ (e.g. motor rotational speed at $3000 \text{ RPM} \rightarrow f = 50 \text{ Hz}$):
$$a(t) = A_0 \sin(2\pi f t)$$
$$v(t) = \int a(t) dt = - \frac{A_0}{2\pi f} \cos(2\pi f t)$$
$$V_{\text{peak}} = \frac{A_{\text{peak}}}{2\pi f} \quad [\text{m/s}] = \frac{1000 \cdot A_{\text{peak}}}{2\pi f} \quad [\text{mm/s}]$$

For an acceleration of $1.0 \text{ m/s}^2$ ($0.102 g$) at $50 \text{ Hz}$:
- **True Velocity Peak:** $V_{\text{peak}} = \frac{1000 \times 1.0}{2\pi \times 50} = \mathbf{3.18 \text{ mm/s}}$
- **True RMS Velocity:** $V_{\text{RMS}} = \frac{3.18}{\sqrt{2}} = \mathbf{2.25 \text{ mm/s}}$
- **Firmware Computed Output:** $0.102 \times 9.81 = \mathbf{1.00 \text{ 'mm/s'}}$ (Over 125% error depending on frequency!)

At $f = 10 \text{ Hz}$:
- **True Velocity Peak:** $V_{\text{peak}} = \frac{1000 \times 1.0}{2\pi \times 10} = \mathbf{15.92 \text{ mm/s}}$ (Severe machine danger!)
- **Firmware Computed Output:** $\mathbf{1.00 \text{ 'mm/s'}}$ (Reports completely normal machine!)

### 2.4 Complete Unit Mapping Matrix

| Variable Name | Code Formula | True Physical Dimension | Current Label | Correct Physical Unit | Status |
|---|---|---|---|---|---|
| `vibration_g` | `dynamicAcceleration / 9.81` | Dimensionless ($g$) | `vibration_g` | $g$ ($1g \approx 9.81 \text{ m/s}^2$) | **CORRECT** |
| `vibration_mm_s` | `vibration * 9.81f` | Acceleration ($[L/T^2]$) | `vibration_mm_s` | $\text{m/s}^2$ | **INCORRECT (Mislabeled)** |
| `temperature_c` | `tempSensor.getTempCByIndex(0)` | Temperature | `temperature_c` | Degrees Celsius (°C) | **CORRECT** |
| `current_a` | `(V_avg - V_zero) / 0.185` | Electric Current | `current_a` | Amperes ($A$) | **CORRECT (Formula)** |
| `energy_wh` | `energy_Wh += (12.0 * I) * dt` | Energy / Work | `energy_wh` | Watt-hours ($\text{Wh}$) | **CORRECT** |
| `ai_confidence` | Normalized `highestScore` | Probability | `ai_confidence` | Unitless ($0.0 - 1.0$) | **CORRECT** |

---

## 3. Current Sensor Unit & Scaling Deep-Dive

### 3.1 ACS712 Transfer Function
For the ACS712-05B (5A bidirectional Hall-effect sensor):
$$V_{\text{out}}(I) = V_{\text{quiescent}} + (\text{Sensitivity} \times I)$$
- Nominal Sensitivity: $185 \text{ mV/A} = 0.185 \text{ V/A}$
- Nominal Quiescent Voltage ($I = 0 \text{ A}$): $V_{\text{CC}} / 2 = 2.50 \text{ V}$

### 3.2 ESP32 ADC Transfer Function
The ESP32 SAR ADC has 12-bit resolution ($0 - 4095$) with a $3.3 \text{ V}$ full-scale reference:
$$V_{\text{pin}} = \frac{\text{raw}}{4095.0} \times 3.3 \text{ V}$$

### 3.3 Voltage Divider Scaling Collision
The ACS712 operates at $5.0 \text{ V}$, while ESP32 GPIO 34 is not 5V-tolerant.
As documented in Phase 0 (`reports/HARDWARE_SAFETY_NOTICE.md`), a $10\text{ k}\Omega / 20\text{ k}\Omega$ voltage divider must attenuate the signal by $2/3$:
$$V_{\text{pin}} = V_{\text{out}} \times \left(\frac{20\text{ k}\Omega}{10\text{ k}\Omega + 20\text{ k}\Omega}\right) = \frac{2}{3} V_{\text{out}}$$
- Quiescent voltage at ESP32 pin: $2.50 \text{ V} \times \frac{2}{3} = \mathbf{1.667 \text{ V}}$
- Effective sensitivity at ESP32 pin: $0.185 \text{ V/A} \times \frac{2}{3} = \mathbf{0.1233 \text{ V/A}}$

#### Current Firmware Implementation:
```cpp
const float ACS712_SENSITIVITY = 0.185f; // Hardcoded unscaled sensitivity!
float zeroVoltage = 2.50f;               // Hardcoded 5V unscaled quiescent voltage!
```
- If the hardware divider is wired:
  - At $I = 0 \text{ A}$, $V_{\text{pin}} = 1.667 \text{ V}$.
  - Firmware computes: $I = |1.667 - 2.50| / 0.185 = \mathbf{4.50 \text{ A}}$!
  - The firmware will report an imaginary **4.5 Amperes** continuously while the motor is completely OFF!
  - `calibrateCurrentSensor()` dynamically measures `zeroVoltage = total / samples`, which corrects `zeroVoltage` to $1.667 \text{ V}$ on boot *only if the motor is off*, but the sensitivity remains unscaled ($0.185$ instead of $0.1233$), resulting in a systematic **33% underestimation of live current**.

---

## 4. Recommendations for Phase 2B Implementation

1. **Vibration Metric Decoupling:**
   - Transmit dynamic acceleration as `vibration_g` (or `vibration_m_s2`).
   - For true velocity in `vibration_mm_s`, implement digital integration:
     $$v(t) = \sum a(t) \Delta t$$
     or compute spectral velocity in the Edge Impulse DSP block.
2. **Current Scaling Parameters:**
   - Define a voltage divider scaling factor macro in firmware:
     ```cpp
     #define VOLTAGE_DIVIDER_RATIO (20.0f / (10.0f + 20.0f)) // 0.6667
     const float ACS712_SENSITIVITY = 0.185f * VOLTAGE_DIVIDER_RATIO;
     ```
3. **Backend Schema Alignment:**
   - Update `calculate_rul_and_health()` to ingest current as an active electrical stress parameter ($I > \text{OVERCURRENT\_LIMIT}$).
