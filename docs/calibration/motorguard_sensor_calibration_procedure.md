# MotorGuard — Industrial-Grade Sensor Calibration Procedure

**Document ID:** `SOP-CALIB-2026-10-19-01`  
**Standard Operating Procedure:** ESP32 + RS-775 DC Motor Condition Monitoring Node  
**Hardware Revision:** Node v1.0.1  
**Applies to:** ACS712-20A Hall Current Sensor, ADXL345 3-Axis Accelerometer, DHT11 Ambient Sensor, Optional DS18B20 Casing Contact Probe  
**Classification:** Engineering Standard Operating Procedure (SOP)

---

## 1. Safety Mandate and Operational Boundaries

> [!CAUTION]
> **ELECTRICAL & MECHANICAL SAFETY NOTICE:**  
> - A 775-class brushed permanent-magnet DC motor generates high rotational speeds ($> 12,000\,\text{RPM}$) and significant torque. Securely clamp the motor chassis to a rigid bench fixture before energizing. Never hold the motor by hand during testing.
> - Software monitoring and Edge Impulse AI models are informational diagnostic systems, **NOT certified life-safety or fire-prevention mechanisms**.
> - An inline **fast-acting 5A DC fuse** or regulated bench power supply current limit is mandatory.
> - **DO NOT deliberately stall the motor or perform dead-short tests.** At 12V stall, an RS-775 motor can draw in excess of $20 - 30\,\text{A}$, which will instantly vaporize PCB traces, melt wiring insulation, and damage the ACS712 sensor.

---

## 2. Step-by-Step Calibration Procedures

### Procedure 1: Identifying Actual Hardware Components

Before applying power, visually inspect and catalog the exact physical hardware installed on the test bench:

1. **Motor Nameplate & Visual Inspection:**
   - Confirm motor dimensions: $42\,\text{mm}$ diameter, $66\,\text{mm}$ length (775 frame).
   - Check rear cooling fan: verify internal centrifugal fan is present and unblocked.
   - Measure armature terminal DC resistance with a calibrated multimeter ($R_{arm}$ typically ranges between $0.4\,\Omega$ and $2.5\,\Omega$). Record $R_{arm}$ in the calibration log.
2. **Current Sensor IC Marking:**
   - Inspect the 8-pin SOIC chip on the current breakout board.
   - Confirm marking: `ACS712T ELC-20A` (or `05B` / `30A`). If `05B` is found, nominal sensitivity is $185\,\text{mV/A}$; if `30A`, $66\,\text{mV/A}$; if `20A`, $100\,\text{mV/A}$.
   - **Do not proceed with 20A constants if the IC marking differs.**
3. **Accelerometer Model & Orientation:**
   - Confirm sensor breakout is an Analog Devices `ADXL345`.
   - Identify axis orientation: Note the direction of the $+X, +Y, +Z$ arrows printed on the PCB silkscreen relative to the motor axis (e.g. $+Z$ normal to motor flux ring, $+X$ parallel to shaft axis).
4. **Temperature Sensor Variant:**
   - Confirm DHT11 (blue casing) is mounted in ambient air, not glued to the motor casing.

---

### Procedure 2: Checking the ACS712 and Voltage Divider

The ESP32 ADC cannot safely tolerate $5.0\,\text{V}$ inputs. The ACS712 requires $5.0\,\text{V}$ $V_{CC}$ and outputs $2.5\,\text{V}$ at $0.0\,\text{A}$. A passive resistive voltage divider ($R_1 = 10\,\text{k}\Omega, R_2 = 20\,\text{k}\Omega$) is installed between ACS712 `OUT` and ESP32 `GPIO 34`.

```
ACS712 (OUT) ----[ R1: 10k ]----+----[ R2: 20k ]---- GND
                                |
                         ESP32 GPIO 34 (ADC1_CH6)
```

1. **Bench Resistance Measurement (Unpowered):**
   - Disconnect the circuit from power.
   - Measure $R_1$ between ACS712 `OUT` and ESP32 `GPIO 34` pin. Record measured value (nominal $10.0\,\text{k}\Omega$).
   - Measure $R_2$ between `GPIO 34` and `GND`. Record measured value (nominal $20.0\,\text{k}\Omega$).
   - Calculate measured divider ratio:
     $$k_{div} = \frac{R_2}{R_1 + R_2}$$
2. **Effective Sensitivity Calculation:**
   - Calculate effective sensitivity at the ADC pin:
     $$S_{pin} = S_{sensor} \times k_{div} = 0.100\,\frac{\text{V}}{\text{A}} \times k_{div}$$
   - For nominal resistors ($k_{div} = 0.6667$), $S_{pin} = 0.06667\,\text{V/A} = 66.67\,\text{mV/A}$.

---

### Procedure 3: Establishing Zero-Current Calibration

Zero-current calibration establishes the resting baseline voltage $V_{zero}$ when the motor is electrically disconnected.

1. **Pre-Calibration Verification:**
   - Verify motor power supply switch is **OFF** and no current is flowing through the ACS712 primary terminals.
2. **Capture Boot Calibration Sequence:**
   - Power up the ESP32 via USB. Open Serial Monitor at 115200 baud.
   - Firmware collects 500 samples over 1.0 second, computing mean pin voltage $V_{pin}$ and sample spread $\Delta V_{pin}$.
3. **Acceptance Criteria:**
   - Measured resting pin voltage must satisfy:
     $$1.30\,\text{V} \le V_{pin} \le 2.05\,\text{V} \quad (\text{Nominal: } 1.667\,\text{V})$$
   - Peak-to-peak spread must satisfy:
     $$\Delta V_{pin} = V_{pin\_max} - V_{pin\_min} < 0.20\,\text{V}$$
4. **Handling Rejection:**
   - If $V_{pin}$ is outside the window (e.g. $< 0.15\,\text{V}$ indicating wire break or $> 3.15\,\text{V}$ indicating short), the firmware marks `currentCalibrated = false` and reverts to nominal $2.50\,\text{V}$ sensor ($1.667\,\text{V}$ pin).
   - Check wiring connections and re-run calibration by sending `'c'` over serial or power-cycling.

---

### Procedure 4: Comparing Current Against a Reference Instrument

1. **Test Rig Setup:**
   - Connect a regulated 12V DC bench supply, external calibrated Digital Multimeter (DMM set to 10A DC series ammeter mode), the ACS712 sensor, and the 775 motor in series.
2. **Measurement Protocol:**
   - Start calibration logger:
     ```bash
     python scripts/calibration_logger.py --phase no_load --ref-current 0.45 --output data/baseline_runs.csv
     ```
   - Step 1: No-load spin at 12V. Record DMM reading ($I_{ref} \approx 0.35 - 0.55\,\text{A}$) and node telemetry current $I_{meas}$.
   - Step 2: Apply light mechanical braking torque using a friction brake or calibrated fan load to draw approximately $1.50\,\text{A}$. Update `--ref-current 1.50`.
   - Step 3: Increase load to continuous rated condition ($2.50\,\text{A}$). Update `--ref-current 2.50`.
3. **Error Analysis:**
   - Run offline analysis:
     ```bash
     python scripts/calibration_logger.py --analyze data/baseline_runs.csv --report data/calib_report.json
     ```
   - Verify Mean Absolute Error (MAE):
     $$\text{MAE} = \frac{1}{N} \sum_{i=1}^N |I_{meas,i} - I_{ref,i}| \le 0.10\,\text{A}$$
   - Verify Percentage Error $\le 5\%$ across loads $> 1.0\,\text{A}$.

---

### Procedure 5: Validating ADXL345 Acquisition Timing

1. **I2C Bus Configuration:**
   - Verify ADXL345 is connected to I2C Bus 0 (`GPIO 21 SDA`, `GPIO 22 SCL`) with $4.7\,\text{k}\Omega$ pull-up resistors.
   - Confirm full-scale range is configured to $\pm 16\,\text{g}$ (`ADXL345_RANGE_16_G`).
2. **Sampling Pacing Verification:**
   - The firmware acquires 128 samples spaced by $1250\,\mu\text{s}$ ($800\,\text{Hz}$ rate).
   - Measure GPIO toggle on an oscilloscope or verify total acquisition window duration:
     $$T_{window} = 128 \times 1250\,\mu\text{s} = 160\,\text{ms}$$
   - Confirm sample acquisition completes without I2C timeout errors (`adxlOnline == true`).

---

### Procedure 6: Collecting Healthy Vibration Baselines

1. **Mounting Requirements:**
   - Fasten the ADXL345 breakout securely to the motor casing flux ring using an aluminum clamp or rigid screw mount. **Do not use double-sided foam tape or zip ties**, as polymer dampening filters out structural vibration harmonics.
2. **Baseline Collection:**
   - Run the motor at rated 12V DC no-load for 5 minutes until bearing lubricant reaches steady operating temperature.
   - Run calibration logger:
     ```bash
     python scripts/calibration_logger.py --phase no_load --max-records 200 --output data/healthy_vibration_baseline.csv
     ```
3. **Baseline Feature Derivation:**
   - Analyze dataset:
     ```bash
     python scripts/calibration_logger.py --analyze data/healthy_vibration_baseline.csv
     ```
   - Calculate Healthy Baseline Mean RMS ($\mu_{vib}$) and Standard Deviation ($\sigma_{vib}$).
   - Set Provisional Warning Limit:
     $$\text{Warn Limit} = \mu_{vib} + 3\sigma_{vib}$$
   - Set Provisional Critical Limit:
     $$\text{Crit Limit} = \mu_{vib} + 6\sigma_{vib}$$

---

### Procedure 7: Checking Ambient Temperature (DHT11)

1. **Placement & Purpose:**
   - Verify DHT11 is positioned in the ambient air path inside or near the motor electronics enclosure.
   - Clearly document that DHT11 measures **ambient enclosure air temperature**, NOT motor internal winding or casing temperature.
2. **Functional Validation:**
   - Verify ambient temperature reads between $15^\circ\text{C}$ and $35^\circ\text{C}$ under normal room conditions.
   - Verify minimum read interval of $1.5\,\text{seconds}$ is respected.
   - Disconnect DHT11 data pin to verify sensor disconnection handling: firmware must flag `dhtOnline = false`, emit `ambient_temperature_c = NAN`, and backend must trigger `SENSOR_DISCONNECTED` alert without crashing.

---

### Procedure 8: Calibrating an Optional Contact Temperature Sensor

If an optional surface contact sensor (such as a Dallas DS18B20 1-Wire digital thermometer or NTC 100k thermistor) is installed:

1. **Physical Attachment:**
   - Bond the sensor directly to the motor stator flux ring or rear bearing housing using thermally conductive epoxy (e.g. Arctic Alumina) or a mechanical spring clamp with thermal grease.
2. **Reference Comparison:**
   - Attach a calibrated Type-K thermocouple connected to a laboratory thermometer directly adjacent to the contact probe.
   - Run motor under moderate load until casing warms from $25^\circ\text{C}$ to $55^\circ\text{C}$.
   - Record readings every $5^\circ\text{C}$ interval.
   - Calculate static offset:
     $$\Delta T_{offset} = T_{ref} - T_{probe}$$
   - Record thermal response delay time constant ($\tau \approx 63.2\%$ response to step change).

---

### Procedure 9: Recording Operating Conditions

For every calibration or baseline run, systematically record operating metadata:

- **Run ID:** Unique tag (e.g. `CALIB-20261019-01`).
- **Operating Phase:** `resting`, `no_load`, `moderate_load`, or `transient_startup`.
- **Supply Voltage:** Measured DC bus voltage at motor driver input (e.g. $12.0\,\text{V}$).
- **Shaft Coupling:** `free_shaft`, `fan_load`, or `dynamometer_brake`.
- **Mounting Stiffness:** Rigid aluminum test stand, rubber grommets, or loose mount.

---

### Procedure 10: Approving Motor-Specific Thresholds

1. **Validation Checks:**
   - Ensure Warning Limit $<$ Critical Limit for all parameters.
   - Current Warning: Must be $\ge$ steady-state continuous current and $<$ driver safe continuous rating.
   - Current Critical: Must be $\le 85\%$ of power supply trip limit.
   - Vibration Limits: Based on statistical $3\sigma$ / $6\sigma$ empirical baseline from Procedure 6.
2. **Backend Submission:**
   - Update threshold configuration via authenticated REST API:
     ```bash
     curl -X PUT http://localhost:8000/api/v1/motors/MTR-775-001/limits \
       -H "Authorization: Bearer <ADMIN_TOKEN>" \
       -H "Content-Type: application/json" \
       -d '{
         "current_warning_a": 2.60,
         "current_critical_a": 3.20,
         "current_hard_limit_a": 4.25,
         "vibration_warning_g": 0.15,
         "vibration_critical_g": 0.35,
         "calibration_status": "measured_and_calibrated",
         "provenance": "Empirical bench dyno run CALIB-20261019-01"
       }'
     ```

---

### Procedure 11: Repeating Calibration After Hardware or Mounting Changes

Calibration must be repeated whenever:
1. The motor is removed, unbolted, or remounted (mounting stiffness changes resonant frequency and vibration baseline).
2. The current sensor PCB, resistor divider, or ESP32 board is replaced.
3. The motor driver or DC power supply is swapped.
4. Brush wear, commutator oxidation, or bearing replacement occurs.

---

### Procedure 12: Recording Calibration Status & Profile Versions

Every motor asset record in MongoDB stores the authoritative calibration history:
- `calibration_status`: `manufacturer_verified`, `measured_and_calibrated`, `provisional`, or `unconfigured`.
- `provenance`: Human-readable audit trail referencing the calibration run ID, laboratory notebook page, or dynamometer log.
- `last_calibration_timestamp`: UTC timestamp of the completed procedure.
- `version`: Incrementing integer version tracking threshold revisions.
