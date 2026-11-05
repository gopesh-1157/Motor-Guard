# ⚠️ HARDWARE SAFETY NOTICE: ESP32 GPIO 34 & ACS712 OVERVOLTAGE RISK

**Document Identifier:** HSN-HW-001  
**Target Hardware:** ESP32 Dev Module (GPIO 34 / ADC1_CH6) & Allegro ACS712 Current Sensor  
**System:** Motor-Guard Condition Monitoring Node  
**Date:** October 2, 2026  
**Status:** **HARDWARE ACTION REQUIRED** (Physical Verification Pending)

---

## 1. Electrical Hazard Description

The **Allegro ACS712** Hall-effect current sensor requires a **5.0 V VCC** supply for linear Hall-element excitation. Its quiescent output voltage is centered at:
$$V_{\text{out, zero}} = 0.5 \times V_{\text{CC}} = 2.50\text{ V}$$

Under dynamic AC motor current or electrical fault surges, the output voltage swings linearly according to the variant's sensitivity:
- **ACS712-05B (185 mV/A):** Swings from 0.5 V (-10 A peak) to **4.5 V** (+10 A peak).
- **ACS712-20A (100 mV/A):** Swings from 0.5 V to **4.5 V**.
- **ACS712-30A (66 mV/A):** Swings from 0.5 V to **4.5 V**.

### Microcontroller Maximum Rating Violation
According to the official **Espressif ESP32 Datasheet (Section 4.1 "Absolute Maximum Ratings")**:
- **Input Voltage ($V_{\text{IN}}$) Absolute Maximum:** $V_{\text{DD}} + 0.3\text{ V} = \mathbf{3.60\text{ V}}$.

Connecting ACS712 OUT directly to ESP32 **GPIO 34** exposes the silicon to voltages up to **4.5 V – 5.0 V**, violating the absolute maximum limit by **1.4 V (39% overvoltage)**.

### Operational Risks:
1. **Permanent ADC Multiplexer Damage:** Degradation or destruction of ESP32 ADC1 channel multiplexer.
2. **CMOS Latch-Up:** High injected substrate current can trigger parasitic thyristor latch-up, destroying the microcontroller.
3. **Measurement Clipping:** ESP32 ADC at standard 11 dB attenuation saturates at ~3.10 V – 3.30 V, clipping all high-current readings above ~3.5 A.

---

## 2. Mandatory Hardware Remediation: Passive Resistor Voltage Divider

To scale the 0.0 V – 5.0 V sensor output safely into the 0.0 V – 3.3 V ESP32 input range, a passive resistor divider **must be physically installed**:

```text
               ACS712 Current Sensor Module
                    ┌──────────────┐
                    │ OUT (0–5.0V) │
                    └──────┬───────┘
                           │
                           │
                         ┌─┴─┐
                         │   │  R_TOP = 10.0 kΩ (1% Metal Film)
                         │   │
                         └─┬─┘
                           │
                           ├─────────────────────► ESP32 GPIO 34 (ADC1_CH6)
                           │                       Input: 0.0V – 3.33V Safe
                         ┌─┴─┐
                         │   │  R_BOTTOM = 20.0 kΩ (1% Metal Film)
                         │   │
                         └─┬─┘
                           │
                           │
                    ┌──────┴───────┐
                    │  Common GND  │
                    └──────────────┘
```

### Voltage Scaling Equation:
$$V_{\text{ADC}} = V_{\text{SENSOR}} \times \frac{R_{\text{BOTTOM}}}{R_{\text{TOP}} + R_{\text{BOTTOM}}} = V_{\text{SENSOR}} \times \frac{20\,\text{k}\Omega}{10\,\text{k}\Omega + 20\,\text{k}\Omega} = V_{\text{SENSOR}} \times \frac{2}{3}$$

- **At Zero Current ($V_{\text{SENSOR}} = 2.50\text{ V}$):**
  $$V_{\text{ADC, zero}} = 2.50\text{ V} \times \frac{2}{3} = \mathbf{1.667\text{ V}}$$
- **At Maximum Peak Fault ($V_{\text{SENSOR}} = 5.00\text{ V}$):**
  $$V_{\text{ADC, max}} = 5.00\text{ V} \times \frac{2}{3} = \mathbf{3.333\text{ V}} \quad (\le 3.60\text{ V Safe Operating Area})$$

> **CRITICAL WARNING:** Do NOT reverse $R_{\text{TOP}}$ and $R_{\text{BOTTOM}}$. Reversing the resistors ($R_{\text{TOP}} = 20\,\text{k}\Omega$, $R_{\text{BOTTOM}} = 10\,\text{k}\Omega$) would deliver only 1.67 V max and shift the zero-point to 0.83 V, truncating positive AC cycles.

---

## 3. Physical Verification Checklist for Plant Engineers

Before powering on the physical ESP32 motor node:

- [ ] **Verification 1:** Confirm ACS712 module VCC is connected to regulated 5.0 V, NOT 3.3 V (the ACS712 internal Hall element cannot operate linearly on 3.3 V).
- [ ] **Verification 2:** Physically inspect breadboard or PCB to verify $R_{\text{TOP}} = 10\,\text{k}\Omega$ connects between ACS712 OUT and GPIO 34.
- [ ] **Verification 3:** Physically inspect to verify $R_{\text{BOTTOM}} = 20\,\text{k}\Omega$ connects between GPIO 34 and Common GND.
- [ ] **Verification 4 (DMM Measurement):** Power the ACS712 without motor current. Measure voltage at GPIO 34 with a digital multimeter. **Measured voltage must be $1.65\text{ V} \pm 0.05\text{ V}$**.
- [ ] **Verification 5 (Peak Measurement):** Inject rated motor load. Verify peak voltage at GPIO 34 never exceeds $3.30\text{ V}$.

---

## 4. Software Calibration Alignment (Deferred to Post-Hardware Verification)

Once physical installation of the $2/3$ divider is confirmed by multimeter measurement:
1. In `firmware/esp32_motor_node.ino`, the zero-voltage baseline shifts from $2.50\text{ V}$ to $1.667\text{ V}$.
2. Effective sensitivity shifts from $S$ to $S \times \frac{2}{3}$ (e.g., $185\text{ mV/A} \times \frac{2}{3} = 123.33\text{ mV/A}$).
3. **Current Phase Status:** Firmware scaling is **intentionally unchanged** in Phase 0 because software-only changes cannot protect un-divided hardware. Updating firmware math before physical installation would cause false sensor readings on existing un-divided hardware.

---

**Hardware Action Status:** **HARDWARE ACTION REQUIRED** (Physical divider installation must precede physical deployment).
