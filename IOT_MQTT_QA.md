# 🛡️ IoT & MQTT Communication Pipeline Quality Assurance Audit Report

**Project**: Motor Health Monitoring & Predictive Maintenance System  
**Audit Scope**: Embedded Firmware (`firmware/`), Serial Bridge (`backend_example/serial_bridge.py`), Backend MQTT Consumer (`backend_example/main.py`), and Technical Documentation (`firmware/README.md`)  
**Auditor**: AGENT 5 — IoT / MQTT Specialist  
**Mode**: Read-Only Audit & Verification  
**Date**: October 2026  
**Status**: ⚠️ **CRITICAL DEFECTS & ARCHITECTURAL GAPS IDENTIFIED**

---

## 1. Executive Summary

This audit evaluates the complete IoT communication pipeline of the Motor Guard system, covering sensor signal acquisition, on-device Edge Impulse TinyML inference, Wi-Fi networking, MQTT transport, USB-UART serial bridging, backend ingestion, and bi-directional control telemetry.

### Key Audit Findings Summary:
| Audit Domain | Status | Severity | Primary Risk |
|---|---|---|---|
| **PubSubClient Buffer Size** | ❌ Defect | **Critical** | Default `MQTT_MAX_PACKET_SIZE` (128 bytes) drops the 165–185 byte JSON payload silently on standard library setups. |
| **Documentation Disparity** | ❌ Divergent | **High** | `README.md` documents MPU6050, `SIMULATION_MODE`, ArduinoJson, and AC RMS; firmware implements ADXL345, hardware-only, `snprintf`, and DC averaging. |
| **ACS712 Current Zero-Calibration** | ⚠️ Flaw | **High** | Assumes motor is OFF at boot; rebooting under motor load zeros out baseline, corrupting current and energy calculations. |
| **Bi-Directional Motor Control** | ❌ Broken Link | **High** | Backend provides `POST /api/motors/{id}/control` publishing to `motors/{id}/cmd`, but firmware never subscribes or handles commands. |
| **Serial Bridge Parsing Mismatch** | ❌ Incompatible | **Medium** | `serial_bridge.py` regexes expect formatted multi-line key-value pairs or raw JSON; firmware prints tagged debug strings `[MQTT Publish -> ...]`. |
| **DS18B20 1-Wire Conversion** | ✅ Valid | **Low** | Properly uses non-blocking asynchronous conversion (`setWaitForConversion(false)`), protecting Edge Impulse timing. |
| **Backend Thread Safety** | ✅ Valid | **Low** | Safely dispatches Paho MQTT thread messages to asyncio loop via `asyncio.run_coroutine_threadsafe`. |

---

## 2. End-to-End IoT Communication Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          ESP32 MOTOR NODE                              │
│                                                                        │
│  [ADXL345]   ──(I2C: 21/22)──┐                                         │
│  [ACS712]    ──(ADC: GPIO34)─┼─> [Edge Impulse DSP & Classifier]       │
│  [DS18B20]   ──(1-Wire: 4)───┘           │                             │
│  [SH1106 OLED] ─(I2C: 32/33) ◄───────────┤                             │
│                                          ▼                             │
│                                [publishTelemetry()]                    │
│                                          │                             │
└──────────────┬───────────────────────────┴─────────────────────────────┘
               │ (MQTT over Wi-Fi / TCP 1883)
               │ Topic: motors/MTR-001/data
               ▼
┌──────────────────────────────────────────┐
│         MQTT BROKER (Mosquitto)          │
│         Port: 1883 | QoS: 0              │
└──────────────┬───────────────────────────┘
               │ Topic: motors/+/data
               ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   FASTAPI BACKEND (main.py)                            │
│                                                                        │
│  [paho.mqtt on_message]                                                │
│         │ (asyncio.run_coroutine_threadsafe)                           │
│         ▼                                                              │
│  [process_telemetry_payload()]                                         │
│         ├─> [Scikit-Learn ML Health & RUL Pipeline]                    │
│         ├─> [Threshold Alert Evaluation]                               │
│         ├─> [MongoDB Async Persistence: telemetry & alerts]            │
│         └─> [WebSocket Broadcaster: /ws/live]                          │
└──────────────────────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
                              [React Web Dashboard]
```

---

## 3. Firmware Deep-Dive Audit (`esp32_motor_node.ino`)

### 3.1 Duplicate File Verification
The repository contains two firmware files:
1. `firmware/esp32_motor_node.ino` (384 lines, 12,300 bytes)
2. `firmware/esp32_motor_node/esp32_motor_node.ino` (384 lines, 12,300 bytes)

*Verification Result*: Byte-for-byte identical (`Compare-Object` returned zero differences). Having duplicate files in the root of `firmware/` and within `firmware/esp32_motor_node/` creates maintenance drift risk if an engineer edits one and leaves the other untouched.

---

### 3.2 Wi-Fi Connection & Reconnect Logic
```cpp
// Lines 222-228, 330-336
void connectWiFi() {
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.printf("[WiFi] Connecting to %s...\n", WIFI_SSID);
  }
}
```
* **Credentials**: Hardcoded in source code: `WIFI_SSID = "Gopesh "` (note trailing space!) and `WIFI_PASSWORD = "gopesh1157"`. No runtime configuration portal or provisioning mechanism (e.g., WiFiManager).
* **Loop Reconnection Behavior**: In `loop()`, reconnection is attempted non-blockingly every 10,000 ms (`now - lastWiFiReconnectAttempt > 10000`).
* **Stack State Vulnerability**: Calling `WiFi.begin(...)` repeatedly every 10 seconds without calling `WiFi.disconnect()` when association fails can cause memory leaks and stack state thrashing in the ESP-IDF Wi-Fi driver.
* **Lack of Exponential Backoff**: Uses fixed 10-second polling without backoff, flooding RF channels if the router is rebooting.

---

### 3.3 MQTT Client Configuration & Buffer Size Vulnerability

#### The Critical Defect: `MQTT_MAX_PACKET_SIZE` Overflow
In Nick O'Leary's **PubSubClient** (the industry-standard Arduino library used on line 8), the default buffer size is:
```cpp
// PubSubClient.h
#define MQTT_MAX_PACKET_SIZE 128   // In version <= 2.7, 128 bytes; in 2.8+, 256 bytes default
```
Now evaluate the payload generated in `esp32_motor_node.ino` (lines 248–266):
```cpp
char payload[320];
snprintf(payload, sizeof(payload),
  "{\"motor_id\":\"%s\","
  "\"temperature_c\":%.2f,"
  "\"current_a\":%.3f,"
  "\"vibration_g\":%.4f,"
  "\"vibration_mm_s\":%.3f,"
  "\"ai_class\":\"%s\","
  "\"ai_confidence\":%.3f,"
  "\"energy_wh\":%.4f}",
  MOTOR_ID, temperature_C, current, vibration,
  vibration * 9.81f, ai_class.c_str(), ai_confidence, energy_Wh
);
```

#### Byte Count Calculation:
```text
{"motor_id":"MTR-001","temperature_c":35.50,"current_a":0.420,"vibration_g":0.1280,"vibration_mm_s":1.256,"ai_class":"NORMAL","ai_confidence":0.950,"energy_wh":12.3456}
```
* **Payload length**: ~165 – 185 bytes (depending on float widths and `ai_class` label length).
* **MQTT Framing overhead**: Fixed header (1 byte), remaining length (1–2 bytes), topic name `"motors/MTR-001/data"` (21 bytes), topic length prefix (2 bytes) = **26 bytes overhead**.
* **Total MQTT packet size**: **~191 to 211 bytes**.

#### Failure Mechanism:
When `PubSubClient::publish(topic, payload)` is invoked:
```cpp
// Inside PubSubClient.cpp
if (MQTT_MAX_PACKET_SIZE < 5 + 2 + strlen(topic) + plength) {
    // Too large!
    return false;
}
```
* On any environment where `PubSubClient` has `MQTT_MAX_PACKET_SIZE = 128` (default on many package distributions and older builds), **`mqttClient.publish()` returns `false` and sends 0 bytes**.
* **Silent Failure**: The firmware does NOT check the boolean return value:
  ```cpp
  mqttClient.publish(MQTT_TOPIC, payload); // Return value ignored!
  Serial.printf("[MQTT Publish -> %s] %s\n", MQTT_TOPIC, payload);
  ```
  The serial monitor reports `[MQTT Publish -> ...]`, deceiving the operator into believing transmission succeeded while nothing was emitted over the wire.
* **Required Fix**: Add `mqttClient.setBufferSize(512);` inside `setup()`.

---

### 3.4 Telemetry Serialization: `snprintf` vs `ArduinoJson`
* `firmware/esp32_motor_node.ino` relies exclusively on `snprintf` using a static 320-byte stack buffer (`char payload[320]`).
* **Pros**: Eliminates heap fragmentation, deterministic stack usage, no dynamic allocations.
* **Risks**:
  1. `ai_class.c_str()` is injected directly without string escaping (`\"`). If the Edge Impulse classifier outputs a label containing spaces, backslashes, or quotes, it generates corrupt, unparseable JSON.
  2. Fixed format makes schema extensions brittle.

---

### 3.5 Sensor Drivers & Hardware Interfacing

#### A. Accelerometer Disparity: ADXL345 vs MPU6050
* **Code Implementation**:
  ```cpp
  #include <Adafruit_Sensor.h>
  #include <Adafruit_ADXL345_U.h>
  Adafruit_ADXL345_Unified accel = Adafruit_ADXL345_Unified(12345);
  ```
  Uses standard I2C bus 0 on GPIO 21 (SDA) and GPIO 22 (SCL). Configures $\pm 4g$ range at 100 Hz. Computes vector magnitude $\sqrt{x^2+y^2+z^2}$, subtracts $1g$ ($9.81 \text{ m/s}^2$), and converts to $g$.
* **Documentation Disparity**:
  The `firmware/README.md` repeatedly instructs the user to wire an **MPU6050** sensor. An engineer wiring an MPU6050 will receive `[ERROR] ADXL345 accelerometer not detected!` on boot.

#### B. ACS712 Current Sensor: Calibration & Sampling Flaws
1. **Critical Boot Assumption**:
   ```cpp
   void calibrateCurrentSensor() {
     Serial.println("Calibrating ACS712... Keep motor OFF.");
     delay(2000);
     const int samples = 500;
     float total = 0;
     for (int i = 0; i < samples; i++) {
       int raw = analogRead(CURRENT_PIN);
       total += ((float)raw / 4095.0f) * 3.3f;
       delay(2);
     }
     zeroVoltage = total / samples;
   }
   ```
   * **Boot Lockout & False Zero**: If the ESP32 suffers a transient brownout, watchdog reset, or power cycle while the industrial motor is running, the calibration runs while current is flowing. The baseline `zeroVoltage` is set to the *load voltage*. When current stops, the sensor reads a negative offset (clamped to positive by `fabs`), yielding completely erroneous current readings and invalid energy accumulation.
   * **Blocking Boot Delay**: Takes $2000\text{ ms} + (500 \times 2\text{ ms}) = 3000\text{ ms}$ of pure blocking delay during boot.
2. **Sampling Resolution & ESP32 ADC Non-Linearity**:
   * GPIO 34 (ADC1_CH6) is sampled with 12-bit resolution (`4095.0f * 3.3f`).
   * The ESP32 ADC has significant non-linearity below $0.15\text{ V}$ and above $3.10\text{ V}$, with $\pm 50\text{ mV}$ offset error unless calibrated using `esp_adc_cal_characterize()`.
3. **DC Averaging vs AC RMS**:
   * In `readCurrent()`, 20 samples with $300\,\mu\text{s}$ delay are taken ($6\text{ ms}$ total window).
   * For AC current ($50\text{ Hz} = 20\text{ ms}$ period), a $6\text{ ms}$ DC average yields unpredictable values depending on which part of the sine wave is sampled.
   * While suitable for pure DC motors, this directly contradicts `README.md` Section 7 which claims *"True AC RMS computed across 100 samples spanning a full 20ms AC cycle"*.

#### C. DS18B20 Temperature Sensor: Asynchronous Non-Blocking Conversion
* Lines 308–310 & 132–144:
  ```cpp
  tempSensor.setWaitForConversion(false);
  tempSensor.requestTemperatures();
  ```
  The DS18B20 12-bit temperature conversion takes up to $750\text{ ms}$. Calling `requestTemperatures()` synchronously would block the ESP32 CPU and completely ruin the Edge Impulse sample loop rate (`1000 / EI_CLASSIFIER_FREQUENCY`).
* The firmware correctly decouples this: it queries the previously converted temperature and triggers the next conversion non-blockingly every $1000\text{ ms}$.
* Includes sanity bounds validation (`tempReading != DEVICE_DISCONNECTED_C && tempReading > -50.0f && tempReading < 125.0f`).

---

## 4. Documentation Discrepancy Matrix (`firmware/README.md` vs Actual Code)

| Feature / Parameter | `firmware/README.md` Specification | Actual Firmware Code (`esp32_motor_node.ino`) | Severity | Impact |
|---|---|---|---|---|
| **Vibration Sensor** | **MPU6050** (`Wire` built-in) | **ADXL345** (`Adafruit_ADXL345_U.h`) | **Critical** | Hardware wiring mismatch; device halts accelerometer initialization. |
| **Simulation Mode** | `#define SIMULATION_MODE true` documented as default | **Completely Missing** (No simulation flag or code exists) | **High** | Users unable to test firmware without physical sensors attached. |
| **JSON Library** | `ArduinoJson (>= 6.21.0 or 7.x)` required | Uses standard `snprintf()` buffer | **Medium** | Unnecessary library dependency declared in documentation. |
| **OLED Display** | Not mentioned anywhere | `Adafruit_SH1106G` dual-I2C bus subsystem on GPIO 32/33 | **Medium** | Hardware build instructions omit mandatory screen wiring. |
| **Status Indicator LED** | `GPIO 2 (LED)` (HIGH = MQTT Connected) | Not defined, initialized, or toggled in code | **Low** | Hardware visual feedback does not function. |
| **ACS712 Variant & Method** | ACS712-30A (`66 mV/A`), True AC RMS over 20ms | ACS712-05B (`185 mV/A`), DC average over 6ms | **High** | Inaccurate current measurement if AC induction motor is monitored. |
| **Published JSON Payload** | `{"motor_id", "temperature_c", "vibration_mm_s", "current_a", "anomaly_score"}` | `{"motor_id", "temperature_c", "current_a", "vibration_g", "vibration_mm_s", "ai_class", "ai_confidence", "energy_wh"}` | **High** | Schema mismatch; firmware does not emit `anomaly_score`. |
| **Edge Impulse Pipeline** | Claims raw vibration buffer yields `anomaly_score` | Features buffer packs temp, vibration, and current; yields discrete `ai_class` and `ai_confidence` | **Medium** | Architectural confusion regarding TinyML model output type. |

---

## 5. Serial Bridge Deep-Dive Audit (`backend_example/serial_bridge.py`)

The serial bridge is intended to read ESP32 serial data over a USB COM port and relay it via HTTP POST to `http://localhost:8000/api/telemetry`.

### 5.1 COM Port Auto-Detection & Baud Rate
* **Auto-detection**: Lines 18–29 search `serial.tools.list_ports.comports()` for known USB-UART descriptors (`cp210`, `ch340`, `ch341`, `ftdi`, `uart`, `usb-serial`, `esp32`).
* **Fallback**: Gracefully falls back to the first detected port or `"COM7"`.
* **Baud Rate**: Set to `115200` (`DEFAULT_BAUD`), exactly matching `Serial.begin(115200)` in firmware.

---

### 5.2 The Parser Breakdown: Regex vs Serial Output Disparity
`serial_bridge.py` defines two parsing strategies:
1. **Strategy A (Direct JSON)**:
   ```python
   if line.startswith("{") and line.endswith("}"):
       obj = json.loads(line)
   ```
2. **Strategy B (Regex Multi-line Text)**:
   ```python
   re_motor = re.compile(r"Motor ID\s*:\s*([A-Za-z0-9_\-]+)", re.I)
   re_temp  = re.compile(r"Temperature\s*:\s*([0-9\.\-]+)", re.I)
   re_curr  = re.compile(r"Current\s*:\s*([0-9\.\-]+)", re.I)
   re_vib   = re.compile(r"Vibration\s*:\s*([0-9\.\-]+)", re.I)
   ```

#### The Incompatibility:
Examine the actual serial print emitted by `esp32_motor_node.ino` (line 269):
```cpp
Serial.printf("[MQTT Publish -> %s] %s\n", MQTT_TOPIC, payload);
```
The resulting serial output line is:
```text
[MQTT Publish -> motors/MTR-001/data] {"motor_id":"MTR-001","temperature_c":30.00,...}
```
* **Strategy A Fails**: `line.startswith("{")` evaluates to **`False`** because the line starts with `[MQTT Publish ->`.
* **Strategy B Fails**: The firmware never outputs `Motor ID :`, `Temperature :`, or separator lines (`----------------`). Those strings were only conceptual examples in `README.md`.
* **Consequence**: `serial_bridge.py` prints `| [MQTT Publish -> ...] ` to stdout but **fails to parse or dispatch any telemetry to the backend**.

---

### 5.3 Error Handling & Port Resilience
* **Port Contention (Arduino IDE open)**:
  Lines 150–155 catch `serial.SerialException` and check for `"PermissionError"` or `"Access is denied"`. It cleanly logs:
  `[!] Cannot open COMx: PORT IS BUSY! -> Please CLOSE the Serial Monitor in Arduino IDE` and retries after 3 seconds without crashing.
* **Backend Unreachable**:
  Lines 43–47 catch `urllib.error.URLError` and print `[!] Backend offline or error: {e.reason}`. The streaming loop continues uninterrupted.

---

## 6. Backend MQTT Subscriber Audit (`backend_example/main.py`)

### 6.1 Topic Matching
* Backend Subscription: `MQTT_TOPIC_SUB = "motors/+/data"` (line 45).
* Firmware Publication: `MQTT_TOPIC = "motors/MTR-001/data"` (line 22).
* Wildcard evaluation: `motors/+/data` matches single-level token `MTR-001`. Topic matching is verified correct.

---

### 6.2 Callback Thread Safety & Event Loop Dispatch
Paho MQTT runs its network loop in a background thread spawned by `mqtt_client.loop_start()`.
FastAPI and MongoDB Motor operate asynchronously inside the `asyncio` event loop.

Lines 240–251 demonstrate correct asynchronous bridging:
```python
def on_mqtt_message(client, userdata, msg):
    try:
        raw_payload = msg.payload.decode("utf-8")
        data = json.loads(raw_payload)
        global server_loop
        if server_loop and server_loop.is_running():
            asyncio.run_coroutine_threadsafe(process_telemetry_payload(data), server_loop)
        else:
            logger.warning("Event loop not available for MQTT processing.")
    except Exception as e:
        logger.error(f"Error handling MQTT message: {e}")
```
* **Thread Safety**: `asyncio.run_coroutine_threadsafe()` safely submits the coroutine to the main event loop thread without blocking the Paho network loop.
* **Resilience**: Any decoding or JSON parsing exception is caught and logged, preventing thread termination.

---

### 6.3 Missing Bi-Directional Control Link
In `backend_example/main.py`:
```python
# Lines 402-408
@app.post("/api/motors/{motor_id}/control", tags=["Motors"])
def send_motor_control(motor_id: str, command: str):
    """Publish control command back to ESP32 (e.g. EMERGENCY_SHUTDOWN or RESET_RELAY)"""
    topic = f"motors/{motor_id}/cmd"
    payload = json.dumps({"command": command, "issued_at": datetime.now(timezone.utc).isoformat()})
    mqtt_client.publish(topic, payload)
    return {"status": "command_published", "topic": topic, "command": command}
```
* **Firmware Verification**:
  * Does `esp32_motor_node.ino` call `mqttClient.subscribe()`? **NO.**
  * Does `esp32_motor_node.ino` call `mqttClient.setCallback()`? **NO.**
  * Does `esp32_motor_node.ino` declare any relay, GPIO actuator, or command handling? **NO.**
* **Risk Assessment**: High safety risk. The backend API implies active actuator or emergency trip capability, but the firmware is strictly a simplex transmitter. Issuing an `EMERGENCY_SHUTDOWN` command reports success to the frontend user while the physical motor remains completely unmanaged.

---

## 7. Failure Modes & Resiliency Analysis

### 7.1 Broker Disconnection & Reconnection
* **Firmware**: If MQTT broker goes down, `reconnectMQTT()` is attempted every 5000 ms. Sensor sampling, OLED screen rendering, and TinyML inference continue uninterrupted. Telemetry packets are dropped during outage.
* **Backend**: Uses Paho's `connect_async()` and `loop_start()`. Paho handles automatic reconnection with exponential backoff transparently. If the broker is offline at startup, FastAPI logs a warning and operates in standalone mode without crashing.

### 7.2 Message Drop & QoS Levels
* **Firmware Publish QoS**: Default QoS 0 (fire-and-forget). No local flash or RAM circular buffer to store unsent telemetry during network loss.
* **Backend Subscribe QoS**: Default QoS 0.
* **Impact**: Acceptable for 1 Hz high-frequency status streaming, but edge fault events or state transitions may be permanently lost during RF packet drops.

### 7.3 Out-of-Order Delivery & Timestamping
* **Firmware**: Does not include a hardware timestamp in the MQTT payload.
* **Backend**: Injects `server_timestamp = datetime.now(timezone.utc).isoformat()` upon message arrival.
* **Impact**: If network latency fluctuates or messages buffer in cellular/gateway routers, the time of ingestion is recorded rather than the actual time of physical event occurrence.

### 7.4 Malformed Payload Handling
* In `process_telemetry_payload()`:
  ```python
  vib = float(data.get("vibration_mm_s", data.get("vibration_g", 0.0)))
  ```
  If a corrupt field contains non-numeric string data (e.g., `"vibration_mm_s": "NaN"` or `"None"`), `float()` raises `ValueError`. While logged by `on_mqtt_message`, the message is abandoned and not persisted or forwarded.

---

## 8. Actionable Remediation Plan & Code Fixes

### Fix 1: Resolve PubSubClient Buffer Size Overflow (Firmware)
Add buffer expansion and publication status checking in `esp32_motor_node.ino`:
```cpp
// In setup():
mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
mqttClient.setBufferSize(512); // CRITICAL: Expands buffer beyond 128-byte default

// In publishTelemetry():
bool success = mqttClient.publish(MQTT_TOPIC, payload);
if (!success) {
  Serial.println("[ERROR] MQTT Publish failed! Buffer size or connection issue.");
} else {
  Serial.printf("[MQTT Publish -> %s] %s\n", MQTT_TOPIC, payload);
}
```

### Fix 2: Safeguard ACS712 Calibration Against In-Flight Boots (Firmware)
Validate calibration range and provide a fallback if booted under motor load:
```cpp
void calibrateCurrentSensor() {
  Serial.println("Calibrating ACS712... Keep motor OFF.");
  const int samples = 100;
  float total = 0;
  for (int i = 0; i < samples; i++) {
    total += ((float)analogRead(CURRENT_PIN) / 4095.0f) * 3.3f;
    delay(5);
  }
  float detectedZero = total / samples;
  // If zeroVoltage deviates more than 15% from nominal (e.g., 2.5V or 1.65V), reject calibration
  if (fabs(detectedZero - 2.50f) > 0.40f) {
    Serial.println("[WARNING] Abnormally high current during boot! Using nominal 2.50V zero reference.");
    zeroVoltage = 2.50f;
  } else {
    zeroVoltage = detectedZero;
  }
}
```

### Fix 3: Fix Serial Bridge Parsing (Backend Example)
Update `backend_example/serial_bridge.py` to extract embedded JSON from debug strings:
```python
# Check for direct JSON or embedded JSON inside log strings
json_candidate = line
if "{" in line and line.endswith("}"):
    json_candidate = line[line.find("{"):]

try:
    obj = json.loads(json_candidate)
    if "motor_id" in obj:
        if post_telemetry(obj):
            print(f"  >>> [DASHBOARD SYNC OK] JSON reading sent: Motor {obj.get('motor_id')}")
        continue
except json.JSONDecodeError:
    pass
```

### Fix 4: Align Documentation with Actual Hardware (`README.md`)
1. Change MPU6050 references to **ADXL345**.
2. Add `Adafruit_ADXL345_U` and `Adafruit_SH110X` to Required Arduino Libraries table.
3. Update pinout diagram to reflect dual I2C buses (Bus 0: 21/22 for ADXL345; Bus 1: 32/33 for SH1106 OLED).
4. Update payload schema documentation to match `ai_class`, `ai_confidence`, and `energy_wh`.
5. Remove misleading claims regarding `SIMULATION_MODE` until synthetic data generation is implemented in firmware.

---

## 9. QA Sign-Off & Verdict

| Verification Item | Result | Notes |
|---|---|---|
| **Firmware Wi-Fi & MQTT Architecture** | ⚠️ Conditional Pass | Functional logic present; requires buffer expansion (`setBufferSize(512)`). |
| **Sensor Implementation** | ⚠️ Conditional Pass | ADXL345 and DS18B20 implemented well; ACS712 zero calibration needs fail-safe. |
| **Documentation Alignment** | ❌ Fail | Discrepancies exist across sensor models, libraries, schemas, and modes. |
| **Serial Bridge Integration** | ❌ Fail | Cannot parse firmware serial output without substring JSON trimming. |
| **Backend Ingestion & Thread Safety** | ✅ Pass | Excellent thread-safe event loop dispatch and schema enrichment. |
| **Bi-Directional Command Loop** | ❌ Fail | Firmware has no subscription or handler for control commands. |

**Final Recommendation**: Address the PubSubClient buffer configuration and serial bridge regex immediately before deploying to production testbeds.
