# MotorGuard — Hardware Electrical Safety & TinyML Validation Specification

## 1. Electrical Conditioning & Sensor Safety

### 1.1 ACS712 (20A) Hall-Effect Current Sensor
The ACS712-20A requires a 5.0 V DC supply. Connecting its output directly to an ESP32 ADC pin creates a severe electrical hazard that can destroy the microcontroller.

```
       [ ACS712 20A Module ]
           VCC = +5.0V
           GND = GND
           OUT (0 - 4.5V)
                |
                +----+
                     |
                    [R1] = 10k Ohm (1%)
                     |
                     +-----> Pin GPIO 34 (ESP32 ADC1_CH6, max 3.0V)
                     |
                    [R2] = 20k Ohm (1%)
                     |
                    GND (Common Ground)
```

#### Physical Electrical Parameters:
- **Supply Voltage ($V_{CC}$)**: $5.00\text{ V}$
- **Quiescent Zero-Current Output**: $V_{out(0)} = \frac{V_{CC}}{2} = 2.50\text{ V}$
- **Sensor Sensitivity ($S$)**: $100\text{ mV/A} = 0.100\text{ V/A}$
- **Maximum Sensor Voltage (at 20A)**: $2.50\text{ V} + (20\text{ A} \times 0.100\text{ V/A}) = 4.50\text{ V}$
- **ESP32 ADC Pin Safe Limit**: $3.30\text{ V}$ (Linear range: $0.1\text{ V} - 2.6\text{ V}$ with 11dB attenuation)

#### Voltage Divider Conditioning & Effective Sensitivity:
- Resistors: $R_1 = 10\text{ k}\Omega$, $R_2 = 20\text{ k}\Omega$
- Divider Ratio: $K = \frac{R_2}{R_1 + R_2} = \frac{20}{10 + 20} = 0.6667$
- Output at Zero Current: $2.50\text{ V} \times 0.6667 = 1.667\text{ V}$
- Output at 20A Full Scale: $4.50\text{ V} \times 0.6667 = 3.00\text{ V}$ ($< 3.30\text{ V}$ safe ceiling)
- **Effective Sensitivity at ESP32 ADC**: Because the voltage divider scales the sensor output by $0.6667$, the native $100\text{ mV/A}$ sensor sensitivity becomes an effective **$66.7\text{ mV/A}$** ($0.0667\text{ V/A}$) at the ESP32 pin. The firmware current calculation must divide measured voltage delta by $0.0667\text{ V/A}$ (or divide by $K$ first: $V_{pin} / K$).

#### Software Alert vs. Physical Emergency Stop Warning:
> [!WARNING]
> A software-defined alert or dashboard warning (e.g. overcurrent trip at 4.0 A or temperature above 50°C) is a **condition monitoring alert**, NOT a physical safety emergency stop. If automatic motor shutdown under fault conditions is required, an independent, certified hardware protection mechanism (such as an inline fuse, thermal breaker, or hardware relay interlock) must be integrated.

#### Firmware Calibration Requirement:
Because resistor tolerances (1%) and $V_{CC}$ variations shift the exact zero point, the firmware **must** execute an automatic 1000-sample calibration cycle during boot:
```cpp
// ACS712 Bootstrapping Rule: Motor must remain de-energized during boot calibration
for (int i = 0; i < 1000; i++) {
  voltageSum += (analogReadMilliVolts(CURRENT_PIN) / 1000.0f) / VOLTAGE_DIVIDER_RATIO;
  delay(2);
}
zeroPointVolts = voltageSum / 1000.0f;
```

---

### 1.2 ADXL345 3-Axis Accelerometer (Vibration Analysis)
- **Interface**: I2C bus (SDA: GPIO 21, SCL: GPIO 22) operating at 100 kHz.
- **Range**: $\pm 4g$ ($g = 9.80665\text{ m/s}^2$).
- **Data Rate**: $100\text{ Hz}$ output data rate.
- **Sample Window**: $100$ samples collected over $1000\text{ ms}$ ($1.0\text{ s}$).

#### Dynamic RMS Acceleration Calculation:
Raw accelerometer readings contain a static Earth gravity DC component ($1.0g$ downwards depending on mounting orientation). To extract pure vibration:
1. Calculate the mean DC acceleration across all samples:
   $$\bar{a}_x = \frac{1}{N}\sum_{i=1}^N a_{x,i}, \quad \bar{a}_y = \frac{1}{N}\sum_{i=1}^N a_{y,i}, \quad \bar{a}_z = \frac{1}{N}\sum_{i=1}^N a_{z,i}$$
2. Subtract the DC bias from each sample:
   $$a_{dyn,x,i} = a_{x,i} - \bar{a}_x, \quad a_{dyn,y,i} = a_{y,i} - \bar{a}_y, \quad a_{dyn,z,i} = a_{z,i} - \bar{a}_z$$
3. Compute the dynamic vector magnitude:
   $$|a_{dyn,i}| = \sqrt{a_{dyn,x,i}^2 + a_{dyn,y,i}^2 + a_{dyn,z,i}^2}$$
4. Calculate Root Mean Square (RMS) vibration in units of $g$:
   $$\text{RMS}_{vibration} = \sqrt{\frac{1}{N}\sum_{i=1}^N |a_{dyn,i}|^2}$$

---

### 1.3 DHT11 Temperature Sensor
- **Interface**: Single-bus digital communication on GPIO 4.
- **Measurement Range**: $0^\circ\text{C}$ to $50^\circ\text{C}$ ($\pm 2^\circ\text{C}$ accuracy).
- **Update Frequency**: Maximum 0.5 Hz - 1.0 Hz (do not poll faster than every 1000 ms).
- **Fault Detection**: If `dht.readTemperature()` returns `NAN`, the firmware sets `sensor_status.temperature = "UNAVAILABLE"` and bypasses AI inference.

---

## 2. Edge Impulse TinyML Model Validation

### 2.1 Model Profile (Verified from Exported Project `#1133176`)
- **Library Name**: `MotoGuard_Motor_Health_inferencing.h`
- **Model Type**: TensorFlow Lite Micro (EON Compiled) Fully-Connected Neural Network.
- **Input Dimension**: Exactly **3 scalar features** (`EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE = 3`):
  - Index 0: `temperature_C` (DHT11, $^\circ\text{C}$)
  - Index 1: `vibration_g` (ADXL345 Dynamic RMS, $g$)
  - Index 2: `current_A` (ACS712 Armature Current, Amps)
- **Output Labels**:
  - `critical` (Index 0)
  - `healthy` (Index 1)
  - `warning` (Index 2)

### 2.2 Critical Safety Boundaries & Model Caveats
1. **Synthetic Data Warning**: The model was trained on synthetic datasets (`775_motor_edge_impulse_ml_ready.csv`). While mathematically sound for testing the pipeline, **synthetic data cannot guarantee real-world physical failure detection** (such as commutator pitting, brush arcing, or bearing spalling). Physical diagnostic claims require empirical run-to-failure testing.
2. **Deterministic Overrides**: AI probabilities **never** override deterministic electrical and thermal safety cutoffs:
   - If $I \ge 4.0\text{ A}$ (rated overcurrent limit), trigger emergency alert regardless of AI prediction.
   - If $T \ge 50.0^\circ\text{C}$ (motor thermal ceiling), trigger emergency thermal trip.
3. **Explicit Fallback Mode**: If any sensor reading is invalid or the model library is absent, the firmware and backend explicitly output `inference.status = "INPUT_INVALID"` or `"MODEL_UNAVAILABLE"` with `health_status = "unknown"`.
